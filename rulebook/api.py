"""HTTP API and demo page: `uvicorn rulebook.api:app`, then open http://127.0.0.1:8000 or POST /ask {"question": "..."}."""
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from rulebook.answer import answer
from rulebook.chunking import MAX_TOKENS
from rulebook.index import ensure
from rulebook.search import jurisdictions, search

COLLECTION = f"section{MAX_TOKENS}"
PAGE = Path(__file__).parent / "static" / "index.html"
SOURCE_FIELDS = ("chunk_id", "section_id", "jurisdiction", "lang", "doc", "ref", "url", "score", "text")


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure(COLLECTION)
    yield


app = FastAPI(title="Rulebook", lifespan=lifespan)


class Ask(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    mode: Literal["routed_rerank", "routed", "dense", "hybrid", "hybrid_rerank"] = "routed_rerank"


def _retrieve(body: Ask) -> tuple[list[dict], dict]:
    t = time.perf_counter()
    hits = search(body.question, COLLECTION, body.mode, k=10)
    routed = jurisdictions(body.question) if body.mode.startswith("routed") else []
    return hits, {"mode": body.mode, "routed_to": routed, "retrieval_ms": round((time.perf_counter() - t) * 1000),
                  "sources": [{f: h[f] for f in SOURCE_FIELDS} for h in hits]}


def _answer(question: str, hits: list[dict]) -> dict:
    t = time.perf_counter()
    return {**answer(question, hits), "answer_ms": round((time.perf_counter() - t) * 1000)}


@app.post("/ask")
def ask(body: Ask) -> dict:
    hits, retrieved = _retrieve(body)
    return {**retrieved, **_answer(body.question, hits)}


@app.post("/ask/stream")
def ask_stream(body: Ask) -> StreamingResponse:
    """For the demo page: one NDJSON line with the sources as soon as search is done, then one with the answer."""
    def lines():
        hits, retrieved = _retrieve(body)
        yield json.dumps(retrieved, ensure_ascii=False) + "\n"
        try:
            yield json.dumps(_answer(body.question, hits), ensure_ascii=False) + "\n"
        except RuntimeError as e:
            yield json.dumps({"error": f"The answer step failed: {str(e)[:300]}"}) + "\n"
    return StreamingResponse(lines(), media_type="application/x-ndjson")


@app.get("/", include_in_schema=False)
def page() -> FileResponse:
    return FileResponse(PAGE)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
