"""Two chunking strategies, compared in the eval.

section - one chunk per legal section, headed with its citation; long sections are split at
          paragraph breaks (and very long paragraphs by tokens).
fixed   - each document read as one token stream and cut into fixed windows with overlap,
          ignoring structure. A window is credited to the section that owns most of its tokens.
"""
import json
import os
from collections import Counter
from functools import lru_cache
from itertools import groupby

from rulebook import DATA

MAX_TOKENS = int(os.environ.get("RULEBOOK_CHUNK_TOKENS", 512))
OVERLAP = 64
JURISDICTIONS = ("uk", "de", "fi", "el")


@lru_cache(1)
def tokenizer():
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained("BAAI/bge-m3")


def token_ids(text: str) -> list[int]:
    return tokenizer()(text, add_special_tokens=False)["input_ids"]


def load_sections(jurisdictions=JURISDICTIONS) -> list[dict]:
    out = []
    for j in jurisdictions:
        path = DATA / "sections" / f"{j}.jsonl"
        if path.exists():
            out += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return out


def citation(section: dict) -> str:
    return f"{section['doc']} {section['ref']} {section.get('title') or ''}".strip()


def _chunk(section: dict, n: int, text: str, strategy: str, section_id: str | None = None) -> dict:
    sid = section_id or section["id"]
    return {"chunk_id": f"{strategy}:{sid}#{n}", "section_id": sid, "jurisdiction": section["jurisdiction"],
            "lang": section["lang"], "doc": section["doc"], "ref": section["ref"],
            "url": section.get("url", ""), "text": text, "strategy": strategy}


def _windows(ids: list[int], size: int, overlap: int) -> list[slice]:
    step = size - overlap
    return [slice(i, i + size) for i in range(0, max(len(ids) - overlap, 1), step)]


def section_chunks(sections: list[dict], max_tokens: int = MAX_TOKENS) -> list[dict]:
    chunks = []
    for s in sections:
        head = citation(s)
        budget = max(max_tokens - len(token_ids(head)) - 4, 16)
        pieces, current = [], []
        for para in s["text"].split("\n\n"):
            ids = token_ids(para)
            if len(ids) > budget:  # a paragraph that alone overflows: cut it by tokens
                if current:
                    pieces.append("\n\n".join(current))
                    current = []
                pieces += [tokenizer().decode(ids[w]) for w in _windows(ids, budget, 0)]
                continue
            if current and len(token_ids("\n\n".join(current + [para]))) > budget:
                pieces.append("\n\n".join(current))
                current = []
            current.append(para)
        if current:
            pieces.append("\n\n".join(current))
        chunks += [_chunk(s, i, f"{head}\n\n{p}", f"section{max_tokens}") for i, p in enumerate(pieces)]
    return chunks


def fixed_chunks(sections: list[dict], size: int = MAX_TOKENS, overlap: int = OVERLAP) -> list[dict]:
    chunks = []
    for _, group in groupby(sections, key=lambda s: s["doc"]):
        group = list(group)
        ids, owner = [], []
        for s in group:
            t = token_ids(s["text"] + "\n\n")
            ids += t
            owner += [s["id"]] * len(t)
        by_id = {s["id"]: s for s in group}
        for n, w in enumerate(_windows(ids, size, min(overlap, size // 2))):
            main = Counter(owner[w]).most_common(1)[0][0]
            chunks.append(_chunk(by_id[main], n, tokenizer().decode(ids[w]), f"fixed{size}", main))
    return chunks


def make_chunks(strategy: str, sections: list[dict] | None = None) -> list[dict]:
    sections = load_sections() if sections is None else sections
    kind, size = strategy.rstrip("0123456789"), int(strategy.lstrip("abcdefghijklmnopqrstuvwxyz") or MAX_TOKENS)
    return section_chunks(sections, size) if kind == "section" else fixed_chunks(sections, size)
