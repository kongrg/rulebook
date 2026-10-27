"""Checks on the parsed corpus (data/sections/*.jsonl) and on the labelled question set (eval/questions.jsonl)."""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from rulebook.corpus.common import FIELDS, SECTIONS

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "eval" / "questions.jsonl"
LANG = {"UK": "en", "DE": "de", "FI": "fi", "EL": "el"}
EXPECTED = {"UK": (100, 200), "DE": (60, 100), "FI": (80, 140), "EL": (25, 45)}  # sections per jurisdiction
QUESTION_MIX = {"lookup": 50, "crosslingual": 30, "comparison": 20, "unanswerable": 20}

if not all((SECTIONS / f"{j.lower()}.jsonl").exists() for j in LANG):
    pytest.skip("corpus not built: run `uv run python -m rulebook.corpus`", allow_module_level=True)


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


SECS = [r for j in LANG for r in _load(SECTIONS / f"{j.lower()}.jsonl")]
BY_ID = {r["id"]: r for r in SECS}
QS = _load(QUESTIONS) if QUESTIONS.exists() else []


def test_ids_unique_and_well_formed():
    assert len(BY_ID) == len(SECS)
    for r in SECS:
        assert re.fullmatch(r"(UK|DE|FI|EL):(LCCP|GLUESTV|RAHAPELILAKI|ARPAJAISLAKI|N4002):[A-Za-z0-9.\-]+", r["id"]), r["id"]
        assert r["id"].startswith(r["jurisdiction"] + ":")


def test_required_fields_non_empty():
    for r in SECS:
        assert set(r) == set(FIELDS), r["id"]
        assert all(isinstance(r[f], str) and r[f].strip() for f in FIELDS), r["id"]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["fetched"])
        assert r["url"].startswith("https://")


def test_section_counts_per_jurisdiction():
    counts = Counter(r["jurisdiction"] for r in SECS)
    for jur, (lo, hi) in EXPECTED.items():
        assert lo <= counts[jur] <= hi, (jur, counts[jur])


def test_no_leftover_markup():
    for r in SECS:
        for field in ("title", "text"):
            assert not re.search(r"</?[a-zA-Z][^>]*>|&(amp|lt|gt|nbsp|quot|#\d+);", r[field]), (r["id"], field)
        assert "\n\n\n" not in r["text"] and "\x00" not in r["text"], r["id"]


def test_lang_matches_jurisdiction():
    for r in SECS:
        assert r["lang"] == LANG[r["jurisdiction"]], r["id"]
        if r["lang"] == "el":
            assert re.search(r"[α-ω]", r["text"]), r["id"]


def test_question_set_shape():
    assert len(QS) == 120
    assert len({q["qid"] for q in QS}) == 120
    assert Counter(q["type"] for q in QS) == QUESTION_MIX
    assert {q["lang"] for q in QS} <= {"en", "el"}
    assert 0.5 <= sum(q["lang"] == "en" for q in QS) / len(QS) <= 0.7
    assert all(q["question"].strip() and q["notes"].strip() for q in QS)


def test_test_split_is_40_and_stratified():
    test = [q for q in QS if q["split"] == "test"]
    assert {q["split"] for q in QS} == {"dev", "test"}
    assert len(test) == 40
    for qtype, n in QUESTION_MIX.items():  # each type keeps its overall share (1/3) in test, +-1
        assert abs(sum(q["type"] == qtype for q in test) - n / 3) <= 1, qtype


def test_answer_ids_exist_and_match_type():
    for q in QS:
        ids = q["answer_ids"]
        assert all(i in BY_ID for i in ids), (q["qid"], [i for i in ids if i not in BY_ID])
        jurs = {BY_ID[i]["jurisdiction"] for i in ids}
        if q["type"] == "unanswerable":
            assert ids == [], q["qid"]
        elif q["type"] == "comparison":
            assert len(ids) >= 2 and len(jurs) >= 2, q["qid"]
        elif q["type"] == "crosslingual":
            assert ids and jurs <= {"DE", "FI"}, q["qid"]
        else:
            assert ids and len(jurs) == 1, q["qid"]
