"""Run the experiments and write the results tables to eval/results/.

  python -m eval.run                    retrieval experiments on the dev split
  python -m eval.run --split test       final numbers on the held-out questions
  python -m eval.run --generate         also answer every question and judge the answers (Claude calls)
  python -m eval.run --gate             CI: exit 1 if shipped recall@10 drops > 1 point below eval/baseline.json
  python -m eval.run --gate --update-baseline
  python -m eval.run --reuse            rescore the saved run against the current labels; no search, no Claude
  python -m eval.run --reuse --generate re-answer the saved shipped retrieval (after a prompt change)
"""
import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from eval.metrics import mrr, ndcg_at, percentile, ranked_sections, recall_at
from rulebook.answer import answer, judge
from rulebook.chunking import MAX_TOKENS, make_chunks
from rulebook.index import ensure
from rulebook.search import search

HERE = Path(__file__).parent
SHIPPED = (f"section{MAX_TOKENS}", "routed_rerank")
# CI gates the first stage of the shipped pipeline: the reranker only reorders its top 20, and on a
# CPU runner reranking every dev question would take over an hour.
GATED = (f"section{MAX_TOKENS}", "routed")
TABLES = {
    "1. Chunking": [("fixed512", "dense"), ("section512", "dense"), ("fixed512", "routed"), ("section512", "routed")],
    "2. Retrieval": [("section512", "dense"), ("section512", "sparse"), ("section512", "hybrid"),
                     ("section512", "routed"), ("section512", "routed_rerank")],
    "3. Cross-language: multilingual embeddings vs translating the query": [("section512", "dense"),
                                                                            ("section512", "translate_dense")],
}
GATE_DROP = 1.0  # recall@10 points


def load_questions(split: str) -> list[dict]:
    lines = (HERE / "questions.jsonl").read_text(encoding="utf-8").splitlines()
    qs = [json.loads(line) for line in lines if line.strip()]
    return [q for q in qs if split == "all" or q["split"] == split]


def score(row: dict, gold: list[str]) -> dict:
    """Retrieval metrics for one question; recomputable from the saved ranking when labels change."""
    for key in ("r5", "r10", "mrr", "ndcg10"):
        row.pop(key, None)
    if gold:
        row |= {"r5": recall_at(row["ranked"], gold, 5), "r10": recall_at(row["ranked"], gold, 10),
                "mrr": mrr(row["ranked"], gold), "ndcg10": ndcg_at(row["ranked"], gold, 10)}
    return row


def run_retrieval(questions: list[dict], collection: str, mode: str) -> list[dict]:
    ensure(collection)
    rows = []
    for q in questions:
        t = time.perf_counter()
        hits = search(q["question"], collection, mode, k=10)
        rows.append(score({"qid": q["qid"], "ms": (time.perf_counter() - t) * 1000, "hits": [h["chunk_id"] for h in hits],
                           "ranked": ranked_sections(hits), "_hits": hits}, q["answer_ids"]))
    return rows


def load_saved(split: str, questions: list[dict]) -> tuple[dict, list[dict] | None]:
    """The saved run, rescored against the current labels. Shipped rows get their chunks back for answering."""
    saved = json.loads((HERE / "results" / f"{split}.json").read_text(encoding="utf-8"))
    gold = {q["qid"]: q["answer_ids"] for q in questions}
    runs = {tuple(key.split("|")): [score(r, gold[r["qid"]]) for r in rows] for key, rows in saved["retrieval"].items()}
    chunks = {c["chunk_id"]: c for c in make_chunks(SHIPPED[0])}
    for r in runs[SHIPPED]:
        r["_hits"] = [chunks[i] for i in r["hits"]]
    gen = saved["generation"]
    for g in gen or []:
        g["answerable"] = bool(gold[g["qid"]])
        g["cites_gold"] = bool(set(g["cited"]) & set(gold[g["qid"]]))
    return runs, gen


def summarize(rows: list[dict]) -> dict:
    scored = [r for r in rows if "r10" in r]
    if not scored:
        return {"n": 0}
    mean = lambda key: statistics.mean(r[key] for r in scored)  # noqa: E731
    return {"n": len(scored), "recall@5": 100 * mean("r5"), "recall@10": 100 * mean("r10"), "mrr": mean("mrr"),
            "ndcg@10": mean("ndcg10"), "p95_ms": percentile([r["ms"] for r in rows], 95)}


def answer_lang(q: dict) -> str:
    langs = {a.split(":")[0] for a in q["answer_ids"]}
    return langs.pop() if len(langs) == 1 else ("none" if not langs else "mixed")


def run_generation(questions: list[dict], rows: list[dict]) -> list[dict]:
    by_qid = {r["qid"]: r for r in rows}

    def one(q: dict) -> dict:
        hits = by_qid[q["qid"]]["_hits"]
        res = answer(q["question"], hits)
        cited = {c["section_id"] for c in res["citations"]}
        return {"qid": q["qid"], "type": q["type"], "answerable": bool(q["answer_ids"]), "refused": res["refused"],
                "cited": sorted(cited), "cites_gold": bool(cited & set(q["answer_ids"])), "answer": res["answer"],
                "total_ms": by_qid[q["qid"]]["ms"] + res["llm_ms"], **judge(res, hits)}

    with ThreadPoolExecutor(3) as pool:  # the subscription's rate limits, not the CPU, set this
        return list(pool.map(one, questions))


def summarize_generation(gen: list[dict]) -> dict:
    unans = [g for g in gen if not g["answerable"]]
    ans = [g for g in gen if g["answerable"]]
    vals = lambda key: [g[key] for g in ans if g[key] is not None]  # noqa: E731
    return {
        "correct_refusals": f"{sum(g['refused'] for g in unans)}/{len(unans)}",
        "false_refusals": f"{sum(g['refused'] for g in ans)}/{len(ans)}",
        "faithfulness": 100 * statistics.mean(vals("faithfulness")) if vals("faithfulness") else None,
        "citation_precision": 100 * statistics.mean(vals("citation_precision")) if vals("citation_precision") else None,
        "cites_a_gold_section": 100 * statistics.mean(g["cites_gold"] for g in ans if not g["refused"]) if ans else None,
        "p50_total_ms": percentile([g["total_ms"] for g in gen], 50),
        "p95_total_ms": percentile([g["total_ms"] for g in gen], 95),
    }


def fmt(s: dict) -> str:
    if not s.get("n"):
        return "| – | – | – | – | – |"
    return (f"| {s['n']} | {s['recall@5']:.1f}% | {s['recall@10']:.1f}% | {s['mrr']:.3f} | {s['ndcg@10']:.3f} "
            f"| {s['p95_ms']:.0f} |")


HEAD = "| Config | n | Recall@5 | Recall@10 | MRR | nDCG@10 | p95 ms |\n|---|---|---|---|---|---|---|"


def report(split: str, questions: list[dict], runs: dict, gen: list[dict] | None) -> str:
    out = [f"# Results — {split} split ({len(questions)} questions, "
           f"{sum(1 for q in questions if q['answer_ids'])} answerable)", "",
           "Modes: `dense` BGE-M3 dense vectors · `sparse` its learned keyword weights · `hybrid` both, fused by RRF · "
           "`routed` dense search restricted to the jurisdictions the question names (all four if none) · "
           "`_rerank` cross-encoder over the top 20 · `translate_dense` the question translated into all four "
           f"languages, one dense search each, fused by RRF. Shipped: `{SHIPPED[0]} · {SHIPPED[1]}`.", ""]
    qs = {q["qid"]: q for q in questions}
    for title, configs in TABLES.items():
        out += [f"## {title}", "", HEAD]
        for c in configs:
            out.append(f"| {c[0]} · {c[1]} " + fmt(summarize(runs[c])))
        if title.startswith("3."):
            out += ["", "Cross-language questions only:", "", HEAD]
            for c in configs:
                rows = [r for r in runs[c] if qs[r["qid"]]["type"] == "crosslingual"]
                out.append(f"| {c[0]} · {c[1]} " + fmt(summarize(rows)))
            out += ["", "translate_dense latency includes the translation call, so it is not comparable."]
        out.append("")
    shipped = runs[SHIPPED]
    for title, key in [("question type", lambda q: q["type"]), ("question language", lambda q: q["lang"]),
                       ("language of the answer", answer_lang)]:
        out += [f"## Shipped config ({SHIPPED[0]} · {SHIPPED[1]}) by {title}", "", HEAD.replace("Config", title)]
        groups = sorted({key(q) for q in questions})
        for g in groups:
            out.append(f"| {g} " + fmt(summarize([r for r in shipped if key(qs[r["qid"]]) == g])))
        out.append("")
    if gen:
        s = summarize_generation(gen)
        out += ["## Answers (shipped config, top 5 chunks to the model)", "",
                "| Metric | Value |", "|---|---|"]
        out += [f"| {k.replace('_', ' ')} | {v:.1f} |" if isinstance(v, float) else f"| {k.replace('_', ' ')} | {v} |"
                for k, v in s.items()]
        out += ["", "Answer time is the original model call through `claude -p`, which adds CLI start-up "
                    "(about 2–3 s) that an API call would not have."]
    return "\n".join(out) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    p.add_argument("--generate", action="store_true")
    p.add_argument("--gate", action="store_true")
    p.add_argument("--update-baseline", action="store_true")
    p.add_argument("--reuse", action="store_true",
                   help="no search: rescore the saved run against the current labels (with --generate, re-answer it)")
    p.add_argument("--rerun", nargs="*", default=[], metavar="COLLECTION:MODE",
                   help="with --reuse, search these configs again, e.g. section512:translate_dense")
    args = p.parse_args()

    if args.gate:
        questions = load_questions("dev")
        r10 = summarize(run_retrieval(questions, *GATED))["recall@10"]
        base_path = HERE / "baseline.json"
        if args.update_baseline:
            base_path.write_text(json.dumps({"config": list(GATED), "recall@10": round(r10, 2)}, indent=1))
            print(f"baseline set: recall@10 {r10:.1f}")
            return
        base = json.loads(base_path.read_text())["recall@10"]
        print(f"{GATED[0]} · {GATED[1]}: recall@10 {r10:.1f} (baseline {base:.1f}, allowed drop {GATE_DROP})")
        if r10 < base - GATE_DROP:
            print("FAIL: retrieval regressed")
            sys.exit(1)
        print("PASS")
        return

    questions = load_questions(args.split)
    res = HERE / "results"
    if args.reuse:
        runs, gen = load_saved(args.split, questions)
        for config in args.rerun:
            print(f"rerunning {config}", flush=True)
            runs[tuple(config.split(":"))] = run_retrieval(questions, *config.split(":"))
    else:
        configs = list(dict.fromkeys(c for cs in TABLES.values() for c in cs))
        runs, gen = {}, None
        for c in configs:
            print(f"running {c[0]} · {c[1]}", flush=True)
            runs[c] = run_retrieval(questions, *c)
    if args.generate:
        gen = run_generation(questions, runs[SHIPPED])
    res.mkdir(exist_ok=True)
    dump = {f"{c[0]}|{c[1]}": [{k: v for k, v in r.items() if k != "_hits"} for r in rows] for c, rows in runs.items()}
    (res / f"{args.split}.json").write_text(
        json.dumps({"retrieval": dump, "generation": gen}, ensure_ascii=False, indent=1), encoding="utf-8")
    md = report(args.split, questions, runs, gen)
    (res / f"{args.split}.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
