"""Retrieval modes compared in the eval.

dense            BGE-M3 dense vectors only
sparse           BGE-M3 learned keyword weights only
hybrid           both, merged by reciprocal rank fusion (RRF) inside one Qdrant query
routed           dense, restricted to the jurisdictions the question names (all four if it names none)
translate_dense  baseline for the cross-language question: translate the query into all four
                 languages first, run dense search per translation, merge with RRF
<mode>_rerank    that mode's top 20 re-scored by a multilingual cross-encoder. Shipped: routed_rerank
"""
import re
import unicodedata
from functools import lru_cache

from qdrant_client import models

from rulebook.embed import encode_query
from rulebook.index import client
from rulebook.llm import ask_json

FIRST_STAGES = ("dense", "sparse", "hybrid", "routed", "translate_dense")
MODES = FIRST_STAGES + tuple(f"{m}_rerank" for m in FIRST_STAGES)
CANDIDATES = 20

# How a question names a jurisdiction, matched lower-case with accents stripped: country names and
# adjectives in English and Greek (the two question languages), plus the laws' and regulators' names.
JURISDICTIONS = {
    "UK": r"\buk\b|\bbritain|\bbritish|\bunited kingdom|\bgambling commission|\blccp\b|βρεταν|ηνωμενο βασιλειο",
    "DE": r"\bgerman|\bdeutschland|\bglustv\b|\bggl\b|γερμαν",
    "FI": r"\bfinland|\bfinnish|\bsuomi\b|\brahapelilaki|φινλανδ",
    "EL": r"\bgreece|\bgreek|\bhellenic|\beeep\b|ελλαδ|ελλην|εεεπ",
}

TRANSLATE_SYSTEM = "You translate questions about gambling regulation into English, German, Finnish and Greek."
TRANSLATE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["en", "de", "fi", "el"],
                    "properties": {lang: {"type": "string"} for lang in ("en", "de", "fi", "el")}}


@lru_cache(1)
def reranker():
    from FlagEmbedding import FlagReranker

    return FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=False)


def jurisdictions(question: str) -> list[str]:
    """The jurisdictions a question names. Empty means none, and routed search then covers all four."""
    text = "".join(c for c in unicodedata.normalize("NFD", question.lower()) if not unicodedata.combining(c))
    return [j for j, pattern in JURISDICTIONS.items() if re.search(pattern, text)]


def _hits(points) -> list[dict]:
    return [{**p.payload, "score": p.score} for p in points]


def _dense(collection: str, text: str, limit: int, only: list[str] | None = None) -> list[dict]:
    dense, _ = encode_query(text)
    where = models.Filter(must=[models.FieldCondition(key="jurisdiction", match=models.MatchAny(any=only))]) if only else None
    return _hits(client().query_points(collection, query=dense.tolist(), using="dense", limit=limit,
                                       query_filter=where).points)


def rrf(rankings: list[list[dict]], k: int = 60) -> list[dict]:
    scores, first = {}, {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking):
            scores[hit["chunk_id"]] = scores.get(hit["chunk_id"], 0) + 1 / (k + rank + 1)
            first.setdefault(hit["chunk_id"], hit)
    return [{**first[c], "score": s} for c, s in sorted(scores.items(), key=lambda kv: -kv[1])]


def rerank(question: str, hits: list[dict]) -> list[dict]:
    if not hits:
        return hits
    scores = reranker().compute_score([[question, h["text"]] for h in hits], normalize=True)
    return [{**h, "score": float(s)} for h, s in sorted(zip(hits, scores), key=lambda x: -x[1])]


def search(question: str, collection: str, mode: str = "routed_rerank", k: int = 10) -> list[dict]:
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; one of {MODES}")
    if mode.endswith("_rerank"):
        return rerank(question, search(question, collection, mode.removesuffix("_rerank"), CANDIDATES))[:k]
    if mode == "dense":
        return _dense(collection, question, k)
    if mode == "routed":
        return _dense(collection, question, k, jurisdictions(question))
    if mode == "translate_dense":
        variants = ask_json(f"Translate into English, German, Finnish and Greek:\n\n{question}", TRANSLATE_SYSTEM,
                            TRANSLATE_SCHEMA)
        rankings = [_dense(collection, q, CANDIDATES) for q in {question, *variants.values()}]
        return rrf(rankings)[:k]
    dense, sparse = encode_query(question)
    sparse_q = models.SparseVector(indices=list(sparse), values=list(sparse.values()))
    if mode == "sparse":
        return _hits(client().query_points(collection, query=sparse_q, using="sparse", limit=k).points)
    fused = client().query_points(
        collection,
        prefetch=[models.Prefetch(query=dense.tolist(), using="dense", limit=CANDIDATES),
                  models.Prefetch(query=sparse_q, using="sparse", limit=CANDIDATES)],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=k,
    ).points
    return _hits(fused)
