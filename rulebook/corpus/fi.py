"""FI: Rahapelilaki 10/2026 (HE 16/2025), consolidated Finnish text from the Finlex open-data API (Akoma Ntoso XML).

One record per § . Subsections (momentit) are paragraphs; numbered points (kohdat) are lines within them.
"""

from lxml import etree

from .common import RAW, clean, fetch, fetched_on, paras, write_sections

STATUTE = "2026/10"
API = f"https://opendata.finlex.fi/finlex/avoindata/v1/akn/fi/act/statute-consolidated/{STATUTE}/fin@"
PAGE = f"https://www.finlex.fi/fi/lainsaadanto/{STATUTE}"
NS = {"a": "http://docs.oasis-open.org/legaldocml/ns/akn/3.0", "finlex": "http://data.finlex.fi/schema/finlex"}
NESTED = {"paragraph", "subparagraph", "point", "item", "list", "blockList"}


def _local(el) -> str:
    return etree.QName(el).localname


def _text(el) -> str:
    return " ".join("".join(el.itertext()).split())


def _lines(el) -> list[str]:
    """Lines of a subsection / point: its own text, then each nested point on its own line, numbered."""
    out = []
    for c in el:
        if not isinstance(c.tag, str) or _local(c) in ("num", "heading"):
            continue
        out += _lines(c) if _local(c) in NESTED else [_text(c)]
    num = el.findtext("a:num", namespaces=NS)
    if num and out:
        out[0] = f"{num.strip()} {out[0]}"
    return [line for line in out if line]


def parse(xml: bytes) -> tuple[str, list[dict]]:
    root = etree.fromstring(xml)
    consolidated = root.find(".//a:FRBRExpression/a:FRBRdate[@name='dateConsolidated']", NS).get("date")
    in_force = root.find(".//finlex:dateEntryIntoForce", NS).get("date")
    note = root.findtext(".//finlex:inForce/finlex:noteEditorial", namespaces=NS)
    version = f"Rahapelilaki {STATUTE.split('/')[1]}/{STATUTE.split('/')[0]}, Finlex ajantasa as of {consolidated}; in force {in_force}"
    version += f" ({note.strip()})" if note else ""

    records = []
    for sec in root.iterfind(".//a:section", NS):
        ref = " ".join(sec.findtext("a:num", namespaces=NS).split())  # "21 §" / "5 a §"
        blocks = []
        for c in sec:
            if not isinstance(c.tag, str) or _local(c) in ("num", "heading"):
                continue
            blocks.append("\n".join(_lines(c)) if _local(c) in NESTED | {"subsection"} else _text(c))
        num = ref.removesuffix("§").strip().replace(" ", "")
        records.append({
            "id": f"FI:RAHAPELILAKI:{num}", "jurisdiction": "FI", "lang": "fi", "doc": "Rahapelilaki 10/2026",
            "ref": ref, "title": clean(sec.findtext("a:heading", namespaces=NS) or ""), "text": paras(blocks),
            "url": PAGE, "version": version,
        })
    return version, records


def run(refresh: bool = False) -> list[dict]:
    raw = RAW / "fi" / "rahapelilaki_2026-10_fin.xml"
    _, records = parse(fetch(API, raw, refresh))
    for r in records:
        r["fetched"] = fetched_on(raw)
    write_sections("FI", records)
    return records
