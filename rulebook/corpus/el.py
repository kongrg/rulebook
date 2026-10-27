"""EL: Ν. 4002/2011, gaming part (articles 25-54, incl. 45Α and 52Α), consolidated text from taxheaven.gr.

No official consolidated text exists online: et.gr serves the original and amending ΦΕΚ only, and the Hellenic
Gaming Commission publishes regulations, not the law. taxheaven.gr keeps a per-article consolidated version
("Κωδικοποιημένος με 5313/2026" = amendments incorporated up to ν. 5313/2026), so it is used as the fallback.
"""

import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from .common import RAW, clean, fetch, fetched_on, paras, write_sections

LAW = "https://www.taxheaven.gr/law/4002/2011"
FIRST, LAST = 25, 54
LATIN = str.maketrans("ΑΒΓΔΕ", "ABGDE")  # article suffixes (45Α) -> ASCII ids


def articles(toc_html: str) -> list[str]:
    soup = BeautifulSoup(toc_html, "lxml")
    nums = [a["data-art-num"] for a in soup.find_all("a", class_="lawt-toc-link")]
    return [n for n in nums if FIRST <= int(re.match(r"\d+", n).group()) <= LAST]


def parse_article(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1", class_="lawt-artview-art-title")  # absent for untitled articles (52Α, 53)
    title = clean(h1.get_text(" ")) if h1 else ""
    blocks = []
    for p in soup.find_all("div", class_="lawt-artview-para-text"):
        for br in p.find_all("br"):
            br.replace_with("\x00")
        text = " ".join(p.get_text().split()).replace("\x00", "\n")  # source line wraps are PDF artefacts; <br> is real
        blocks.append(text.replace("µ", "μ"))  # micro sign used as Greek mu in the source
    return title, paras(blocks)


def run(refresh: bool = False) -> list[dict]:
    toc = RAW / "el" / "4002_2011.html"
    toc_html = fetch(LAW, toc, refresh).decode("utf-8")
    codified = re.search(r"Κωδικοποιημένος με ([\d/]+)", toc_html)
    version = "Ν. 4002/2011 (ΦΕΚ Α' 180/22.08.2011), consolidated text"
    version += f" incl. amendments up to ν. {codified.group(1)}" if codified else ""
    records = []
    for num in articles(toc_html):
        raw = RAW / "el" / f"arthro_{num.translate(LATIN)}.html"
        url = f"{LAW}/arthro/{quote(num)}"
        title, text = parse_article(fetch(url, raw, refresh).decode("utf-8"))
        if not text:
            continue
        records.append({
            "id": f"EL:N4002:{num.translate(LATIN)}", "jurisdiction": "EL", "lang": "el", "doc": "Ν. 4002/2011",
            "ref": f"Άρθρο {num}", "title": title or f"Άρθρο {num}", "text": text, "url": url,
            "version": version, "fetched": fetched_on(raw),
        })
    write_sections("EL", records)
    return records
