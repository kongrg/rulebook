"""DE: Glücksspielstaatsvertrag 2021 (GlüStV 2021), all-sections view of the official Bavarian law portal.

One record per § (incl. lettered ones such as § 6c). Sentence numbers and editorial footnote markers are dropped.
"""

import re

from bs4 import BeautifulSoup, Tag

from .common import RAW, clean, fetch, fetched_on, paras, write_sections

BASE = "https://www.gesetze-bayern.de/Content/Document/StVGlueStV2021"
URL = BASE + "/true"


def _dl(dl: Tag) -> str:
    """Numbered list (dt = number, dd = text) as one line per item; nested lists indent nothing, just follow."""
    lines = []
    for dt in dl.find_all("dt", recursive=False):
        dd = dt.find_next_sibling("dd")
        nested = [_dl(x) for x in dd.find_all("dl", recursive=False)]
        for x in dd.find_all("dl", recursive=False):
            x.extract()
        lines.append(f"{dt.get_text(strip=True)} {' '.join(dd.get_text().split())}".strip())
        lines += nested
    return "\n".join(lines)


def _block(el: Tag) -> str:
    if el.name == "dl":
        return _dl(el)
    if el.name == "table" or el.find("table"):
        rows = el.find_all("tr")
        return "\n".join(" | ".join(" ".join(td.get_text().split()) for td in tr.find_all(["td", "th"])) for tr in rows)
    nested = el.find_all("dl", recursive=False)
    for x in nested:
        x.extract()
    return "\n".join([" ".join(el.get_text().split()), *(_dl(x) for x in nested)])


def parse(html: str) -> tuple[str, list[dict]]:
    soup = BeautifulSoup(html, "lxml")
    meta = soup.find("div", id="doc-metadata").get_text(" ", strip=True)
    valid_from = re.search(r"Text gilt ab:\s*([\d.]+)", meta).group(1)
    standangabe = soup.find("div", class_="standangabe").get_text(" ", strip=True)
    amended = re.search(r"zuletzt durch (.*?) geändert", standangabe)
    version = f"Text gilt ab {valid_from}" + (f"; zuletzt geändert durch {amended.group(1)}" if amended else "")

    for junk in soup.select("sup.satznr, sup:has(a.footnotelink-down), a.footnoteanchor"):
        junk.decompose()

    records = []
    for head in soup.find_all("div", class_="paraheading"):
        if not head.find("div", class_="paranr"):  # the signature block at the end has an empty heading
            continue
        ref = " ".join(head.find("div", class_="paranr").get_text().split())  # "§ 6c"
        title = clean(head.find("div", class_="paratitel").get_text(" "))
        body = [_block(el) for el in head.find_next_siblings()
                if el.name != "hr" and not {"clearer", "fn", "fn-container"} & set(el.get("class") or [])]
        text = paras(body)
        if not text or re.fullmatch(r"\(?(weggefallen|aufgehoben)\)?", text, re.I):
            continue
        num = ref.removeprefix("§").strip()
        records.append({
            "id": f"DE:GLUESTV:{num}", "jurisdiction": "DE", "lang": "de", "doc": "GlüStV 2021",
            "ref": ref, "title": title, "text": text, "url": f"{BASE}-{num}", "version": version,
        })
    return version, records


def run(refresh: bool = False) -> list[dict]:
    raw = RAW / "de" / "gluestv2021_all.html"
    _, records = parse(fetch(URL, raw, refresh).decode("utf-8"))
    for r in records:
        r["fetched"] = fetched_on(raw)
    write_sections("DE", records)
    return records
