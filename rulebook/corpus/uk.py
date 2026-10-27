"""UK: Gambling Commission Licence Conditions and Codes of Practice (LCCP), single-page print edition.

One record per licence condition / code provision (h5 `section.condition` blocks). Reuse: Open Government Licence v3.0.
"""

import re

from bs4 import BeautifulSoup, NavigableString, Tag

from .common import RAW, clean, fetch, fetched_on, paras, write_sections

BASE = "https://www.gamblingcommission.gov.uk/licensees-and-businesses/lccp"
URL = BASE + "/print"
PARTS = {"1": "LC", "2": "CP", "3": "PLC"}  # operating licence conditions, code provisions, personal licence conditions


def _label(lst: Tag, i: int) -> str:
    cls = lst.get("class") or []
    if lst.name == "ul":
        return "-"
    if "gcweb-letters" in cls:
        return f"({chr(96 + i)})"
    if "gcweb-roman" in cls:
        return f"({['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x', 'xi', 'xii'][i - 1]})"
    return f"{i}."


def _items(lst: Tag) -> list[str]:
    start = int(lst.get("start", 1))
    return [_li(li, _label(lst, i)) for i, li in enumerate(lst.find_all("li", recursive=False), start)]


def _li(li: Tag, label: str) -> str:
    """A list item as one line, its nested list items as further lines."""
    head, nested = [], []
    for c in li.children:
        if isinstance(c, Tag) and c.name in ("ol", "ul"):
            nested += _items(c)
        else:
            head.append(c.get_text() if isinstance(c, Tag) else str(c))
    return "\n".join([f"{label} {' '.join(' '.join(head).split())}".strip(), *nested])


def _blocks(el: Tag) -> list[str]:
    out = []
    for c in el.children:
        if isinstance(c, NavigableString):
            out.append(str(c))
        elif c.name in ("h5", "hr"):
            continue
        elif "print-panel" in (c.get("class") or []):  # "Applies to:" + scope on one line
            out.append(" ".join(p.get_text(" ", strip=True) for p in c.find_all("p")))
        elif c.name in ("ol", "ul"):
            out += _items(c)
        elif c.name == "li":
            out.append(_li(c, ""))
        elif c.find(["p", "ol", "ul", "div", "blockquote"]):
            out += _blocks(c)
        else:
            out.append(" ".join(c.get_text().split()))
    return out


def parse(html: str) -> tuple[str, list[dict]]:
    soup = BeautifulSoup(html, "lxml")
    version = soup.find("p", class_="effective-date").get_text(strip=True)
    records = []
    for sec in soup.find_all("section", class_="condition"):
        part = re.match(r"\d+", sec.find_parent("div", class_="page-part").find("h2").get_text(strip=True)).group()
        num, title = re.match(r"\s*([\d.]*\d)\s*-\s*(.*)", sec.find("h5").get_text(" ", strip=True)).groups()
        title = clean(title)
        if title.lower() == "not in use":
            continue
        for sup in sec.find_all("sup"):  # footnote markers and footnote bodies both become [n]
            sup.replace_with(f"[{sup.get_text(strip=True)}]")
        kind = PARTS[part]
        if kind == "LC":
            ref, url = f"LC {num}", f"{BASE}/1/{num.split('.')[0]}"
        elif kind == "CP":
            code = "SR code" if sec.find("div", class_="sr-code") else "Ordinary code"
            ref, url = f"{code} {num}", f"{BASE}/2/{num.split('.')[0]}"
        else:
            ref, url = f"Personal licence condition {num}", f"{BASE}/condition/1-personal-licence-conditions-conditions"
        text = paras(_blocks(sec)).replace("(opens in new tab)", "")
        text = re.sub(r" (\[\d+\]) ?([,.;:)])?", lambda m: m[1] + (m[2] or " "), text)  # "Act [1] ," -> "Act[1],"
        records.append({
            "id": f"UK:LCCP:{kind}-{num}", "jurisdiction": "UK", "lang": "en", "doc": "LCCP",
            "ref": ref, "title": title, "text": clean(text), "url": url,
        })
    return version, records


def run(refresh: bool = False) -> list[dict]:
    raw = RAW / "uk" / "lccp_print.html"
    version, records = parse(fetch(URL, raw, refresh).decode("utf-8"))
    for r in records:
        r.update(version=version, fetched=fetched_on(raw))
    write_sections("UK", records)
    return records
