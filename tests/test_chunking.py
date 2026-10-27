from rulebook.chunking import fixed_chunks, section_chunks, token_ids

SECTIONS = [
    {"id": "DE:GLUESTV:1", "jurisdiction": "DE", "lang": "de", "doc": "GlüStV 2021", "ref": "§ 1", "title": "Ziele",
     "text": "Erster Absatz über Spielerschutz.\n\nZweiter Absatz über Jugendschutz.", "url": ""},
    {"id": "DE:GLUESTV:2", "jurisdiction": "DE", "lang": "de", "doc": "GlüStV 2021", "ref": "§ 2", "title": "",
     "text": " ".join(["Wort"] * 900), "url": ""},
]


def test_section_chunks_keep_section_ids_and_respect_the_budget():
    chunks = section_chunks(SECTIONS, max_tokens=128)
    assert {c["section_id"] for c in chunks} == {"DE:GLUESTV:1", "DE:GLUESTV:2"}
    assert all(len(token_ids(c["text"])) <= 128 + 8 for c in chunks)  # decode/re-encode can shift a few tokens
    assert chunks[0]["text"].startswith("GlüStV 2021 § 1 Ziele")
    assert len({c["chunk_id"] for c in chunks}) == len(chunks)


def test_fixed_chunks_credit_the_majority_section():
    chunks = fixed_chunks(SECTIONS, size=8, overlap=2)
    assert chunks[0]["section_id"] == "DE:GLUESTV:1"
    assert chunks[-1]["section_id"] == "DE:GLUESTV:2"
    assert len({c["chunk_id"] for c in chunks}) == len(chunks)
