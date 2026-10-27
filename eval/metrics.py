"""Retrieval metrics at section level: a chunk counts as its section, first occurrence wins."""
import math


def ranked_sections(hits: list[dict]) -> list[str]:
    seen = []
    for h in hits:
        if h["section_id"] not in seen:
            seen.append(h["section_id"])
    return seen


def recall_at(ranked: list[str], gold: list[str], k: int) -> float:
    return len(set(ranked[:k]) & set(gold)) / len(gold)


def mrr(ranked: list[str], gold: list[str]) -> float:
    return next((1 / (i + 1) for i, s in enumerate(ranked) if s in gold), 0.0)


def ndcg_at(ranked: list[str], gold: list[str], k: int) -> float:
    dcg = sum(1 / math.log2(i + 2) for i, s in enumerate(ranked[:k]) if s in gold)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(k, len(gold))))
    return dcg / ideal


def percentile(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, round(p / 100 * (len(s) - 1)))] if s else float("nan")
