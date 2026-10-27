"""Shared helpers: a polite HTTP fetcher with an on-disk cache, text cleanup, JSONL output."""

import datetime as dt
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("RULEBOOK_DATA", ROOT / "data"))  # override when the repo folder is write-protected
RAW = DATA / "raw"
SECTIONS = DATA / "sections"

UA = "Rulebook/0.1 (open-source research project: cross-lingual RAG over public gambling regulation; 1 req/s)"
MIN_GAP_S = 1.1
FIELDS = ("id", "jurisdiction", "lang", "doc", "ref", "title", "text", "url", "version", "fetched")

_client = httpx.Client(headers={"User-Agent": UA}, timeout=60, follow_redirects=True)
_last_request = 0.0
_robots: dict[str, RobotFileParser] = {}


def _request(url: str) -> httpx.Response:
    global _last_request
    wait = _last_request + MIN_GAP_S - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    try:
        return _client.get(url)
    finally:
        _last_request = time.monotonic()


def _allowed(url: str) -> bool:
    host = "{0.scheme}://{0.netloc}".format(urlsplit(url))
    if host not in _robots:
        rp = RobotFileParser()
        r = _request(host + "/robots.txt")
        if r.status_code in (401, 403):
            rp.disallow_all = True
        else:  # a missing robots.txt means everything is allowed
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        _robots[host] = rp
    return _robots[host].can_fetch(UA, url)


def fetch(url: str, dest: Path, refresh: bool = False) -> bytes:
    """Return the body of `url`, downloading it to `dest` unless a cached copy exists.

    Fails loudly on robots.txt refusals and HTTP errors (e.g. bot protection) instead of working around them.
    """
    if dest.exists() and not refresh:
        return dest.read_bytes()
    if not _allowed(url):
        raise PermissionError(f"robots.txt disallows {url}")
    r = _request(url)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return r.content


def fetched_on(path: Path) -> str:
    return dt.date.fromtimestamp(path.stat().st_mtime).isoformat()


def clean(s: str) -> str:
    """Collapse runs of spaces (incl. NBSP / narrow NBSP) and trim each line; keep line breaks."""
    s = re.sub(r"[ \t\r\f\v   ]+", " ", s)
    return "\n".join(line.strip() for line in s.split("\n")).strip()


def paras(blocks) -> str:
    """Join non-empty blocks with a blank line, the paragraph separator of the record contract."""
    return "\n\n".join(b for b in (clean(b) for b in blocks) if b)


def write_sections(jur: str, records: list[dict]) -> Path:
    for r in records:
        missing = [f for f in FIELDS if not r.get(f)]
        if missing:
            raise ValueError(f"{r.get('id')}: empty {missing}")
    ids = [r["id"] for r in records]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate ids: {sorted(dupes)}")
    out = SECTIONS / f"{jur.lower()}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps({k: r[k] for k in FIELDS}, ensure_ascii=False) + "\n")
    return out
