"""BGE-M3: one forward pass gives a dense vector and learned per-token weights (a sparse,
keyword-style vector), in 100+ languages. Encodings are cached in SQLite by text hash."""
import hashlib
import json
import sqlite3
from functools import lru_cache

import numpy as np

from rulebook import DATA

DB = DATA / "embeddings.sqlite"


@lru_cache(1)
def model():
    from FlagEmbedding import BGEM3FlagModel

    return BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)


def encode_query(text: str) -> tuple[np.ndarray, dict[int, float]]:
    """Uncached, so measured search latency includes encoding the query."""
    out = model().encode([text], max_length=512, return_dense=True, return_sparse=True, return_colbert_vecs=False)
    return np.asarray(out["dense_vecs"][0], dtype=np.float32), {int(a): float(b) for a, b in out["lexical_weights"][0].items()}


def encode(texts: list[str], batch_size: int = 8, progress: bool = False) -> list[tuple[np.ndarray, dict[int, float]]]:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("create table if not exists e (k text primary key, dense blob, sparse text)")
    keys = [hashlib.sha256(t.encode()).hexdigest() for t in texts]
    have = {}
    for i in range(0, len(keys), 900):  # stay under SQLite's bound-parameter limit
        part = keys[i:i + 900]
        have.update({k: (d, s) for k, d, s in con.execute(
            f"select k, dense, sparse from e where k in ({','.join('?' * len(part))})", part)})
    todo = sorted({k: t for k, t in zip(keys, texts) if k not in have}.items())
    for i in range(0, len(todo), batch_size * 8):
        batch = todo[i:i + batch_size * 8]
        out = model().encode([t for _, t in batch], batch_size=batch_size, max_length=512,
                             return_dense=True, return_sparse=True, return_colbert_vecs=False)
        rows = [(k, np.asarray(d, dtype=np.float32).tobytes(), json.dumps({str(a): float(b) for a, b in w.items()}))
                for (k, _), d, w in zip(batch, out["dense_vecs"], out["lexical_weights"])]
        con.executemany("insert or replace into e values (?, ?, ?)", rows)
        con.commit()
        have.update({k: (d, s) for k, d, s in rows})
        if progress:
            print(f"  encoded {min(i + len(batch), len(todo))}/{len(todo)} new texts", flush=True)
    con.close()
    return [(np.frombuffer(have[k][0], dtype=np.float32), {int(a): b for a, b in json.loads(have[k][1]).items()})
            for k in keys]
