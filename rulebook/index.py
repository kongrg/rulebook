"""Qdrant collections: one named dense vector and one sparse vector per chunk.

Runs Qdrant in local file mode by default (no server needed); set QDRANT_URL to use a server,
e.g. the one in docker-compose.yml."""
import atexit
import hashlib
import json
import os
from functools import lru_cache

from qdrant_client import QdrantClient, models

from rulebook import DATA
from rulebook.chunking import make_chunks
from rulebook.embed import encode

FINGERPRINTS = DATA / "qdrant_fingerprints.json"


@lru_cache(1)
def client() -> QdrantClient:
    url = os.environ.get("QDRANT_URL")
    c = QdrantClient(url=url) if url else QdrantClient(path=str(DATA / "qdrant"))
    atexit.register(c.close)  # closing in __del__ at interpreter shutdown prints a spurious traceback
    return c


def ensure(strategy: str) -> str:
    """Build the collection for a chunking strategy unless an identical one already exists."""
    chunks = make_chunks(strategy)
    if not chunks:
        raise SystemExit("No sections found in data/sections/ - run `python -m rulebook.corpus` first.")
    fp = hashlib.sha256(json.dumps([[c["chunk_id"], c["text"]] for c in chunks]).encode()).hexdigest()
    seen = json.loads(FINGERPRINTS.read_text()) if FINGERPRINTS.exists() else {}
    c = client()
    if seen.get(strategy) == fp and c.collection_exists(strategy):
        return strategy
    print(f"indexing {len(chunks)} chunks for '{strategy}'", flush=True)
    vectors = encode([ch["text"] for ch in chunks], progress=True)
    if c.collection_exists(strategy):
        c.delete_collection(strategy)
    c.create_collection(
        strategy,
        vectors_config={"dense": models.VectorParams(size=1024, distance=models.Distance.COSINE)},
        sparse_vectors_config={"sparse": models.SparseVectorParams()},
    )
    points = [
        models.PointStruct(id=i, payload=ch, vector={
            "dense": dense.tolist(),
            "sparse": models.SparseVector(indices=list(sparse), values=list(sparse.values())),
        })
        for i, (ch, (dense, sparse)) in enumerate(zip(chunks, vectors))
    ]
    for i in range(0, len(points), 256):
        c.upsert(strategy, points[i:i + 256])
    seen[strategy] = fp
    FINGERPRINTS.write_text(json.dumps(seen, indent=1))
    return strategy


if __name__ == "__main__":
    import sys

    for s in sys.argv[1:] or ["section512"]:
        ensure(s)
