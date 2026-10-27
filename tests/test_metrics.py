import math

from eval.metrics import mrr, ndcg_at, percentile, ranked_sections, recall_at
from rulebook.search import rrf


def test_ranked_sections_dedupes_chunks_keeping_first_rank():
    hits = [{"section_id": "A"}, {"section_id": "B"}, {"section_id": "A"}, {"section_id": "C"}]
    assert ranked_sections(hits) == ["A", "B", "C"]


def test_recall_counts_each_gold_section_once():
    assert recall_at(["A", "B", "C"], ["C", "D"], 2) == 0
    assert recall_at(["A", "B", "C"], ["C", "D"], 3) == 0.5
    assert recall_at(["D", "C"], ["C", "D"], 2) == 1


def test_mrr_uses_first_gold_hit():
    assert mrr(["X", "Y", "A"], ["A", "Y"]) == 0.5
    assert mrr(["X"], ["A"]) == 0


def test_ndcg_perfect_and_partial():
    assert ndcg_at(["A", "B"], ["A", "B"], 10) == 1
    assert math.isclose(ndcg_at(["X", "A"], ["A"], 10), 1 / math.log2(3))


def test_percentile():
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert percentile([5, 1, 4, 2, 3], 95) == 5


def test_rrf_rewards_agreement():
    a = [{"chunk_id": "x"}, {"chunk_id": "y"}]
    b = [{"chunk_id": "y"}, {"chunk_id": "z"}]
    assert [h["chunk_id"] for h in rrf([a, b])][0] == "y"
