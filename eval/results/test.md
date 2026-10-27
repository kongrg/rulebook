# Results — test split (40 questions, 34 answerable)

Modes: `dense` BGE-M3 dense vectors · `sparse` its learned keyword weights · `hybrid` both, fused by RRF · `routed` dense search restricted to the jurisdictions the question names (all four if none) · `_rerank` cross-encoder over the top 20 · `translate_dense` the question translated into all four languages, one dense search each, fused by RRF. Shipped: `section512 · routed_rerank`.

## 1. Chunking

| Config | n | Recall@5 | Recall@10 | MRR | nDCG@10 | p95 ms |
|---|---|---|---|---|---|---|
| fixed512 · dense | 34 | 43.9% | 46.8% | 0.381 | 0.383 | 413 |
| section512 · dense | 34 | 73.0% | 74.0% | 0.665 | 0.646 | 401 |
| fixed512 · routed | 34 | 52.0% | 54.9% | 0.438 | 0.444 | 362 |
| section512 · routed | 34 | 86.3% | 89.0% | 0.839 | 0.815 | 387 |

## 2. Retrieval

| Config | n | Recall@5 | Recall@10 | MRR | nDCG@10 | p95 ms |
|---|---|---|---|---|---|---|
| section512 · dense | 34 | 73.0% | 74.0% | 0.665 | 0.646 | 401 |
| section512 · sparse | 34 | 40.2% | 42.6% | 0.403 | 0.394 | 390 |
| section512 · hybrid | 34 | 68.6% | 74.0% | 0.591 | 0.609 | 380 |
| section512 · routed | 34 | 86.3% | 89.0% | 0.839 | 0.815 | 387 |
| section512 · routed_rerank | 34 | 89.2% | 92.9% | 0.862 | 0.844 | 54647 |

## 3. Cross-language: multilingual embeddings vs translating the query

| Config | n | Recall@5 | Recall@10 | MRR | nDCG@10 | p95 ms |
|---|---|---|---|---|---|---|
| section512 · dense | 34 | 73.0% | 74.0% | 0.665 | 0.646 | 401 |
| section512 · translate_dense | 34 | 72.8% | 82.6% | 0.618 | 0.637 | 16821 |

Cross-language questions only:

| Config | n | Recall@5 | Recall@10 | MRR | nDCG@10 | p95 ms |
|---|---|---|---|---|---|---|
| section512 · dense | 10 | 70.0% | 70.0% | 0.520 | 0.565 | 702 |
| section512 · translate_dense | 10 | 80.0% | 80.0% | 0.567 | 0.626 | 16821 |

translate_dense latency includes the translation call, so it is not comparable.

## Shipped config (section512 · routed_rerank) by question type

| question type | n | Recall@5 | Recall@10 | MRR | nDCG@10 | p95 ms |
|---|---|---|---|---|---|---|
| comparison | 7 | 76.2% | 79.8% | 1.000 | 0.802 | 49010 |
| crosslingual | 10 | 90.0% | 100.0% | 0.746 | 0.808 | 52492 |
| lookup | 17 | 94.1% | 94.1% | 0.873 | 0.883 | 55231 |
| unanswerable | – | – | – | – | – |

## Shipped config (section512 · routed_rerank) by question language

| question language | n | Recall@5 | Recall@10 | MRR | nDCG@10 | p95 ms |
|---|---|---|---|---|---|---|
| el | 15 | 88.9% | 88.9% | 0.900 | 0.864 | 52492 |
| en | 19 | 89.5% | 96.1% | 0.831 | 0.828 | 55231 |

## Shipped config (section512 · routed_rerank) by language of the answer

| language of the answer | n | Recall@5 | Recall@10 | MRR | nDCG@10 | p95 ms |
|---|---|---|---|---|---|---|
| DE | 5 | 100.0% | 100.0% | 0.767 | 0.826 | 52492 |
| EL | 8 | 100.0% | 100.0% | 1.000 | 0.985 | 49270 |
| FI | 5 | 80.0% | 100.0% | 0.725 | 0.789 | 46379 |
| UK | 9 | 88.9% | 88.9% | 0.759 | 0.792 | 61622 |
| mixed | 7 | 76.2% | 79.8% | 1.000 | 0.802 | 49010 |
| none | – | – | – | – | – |

## Answers (shipped config, top 5 chunks to the model)

| Metric | Value |
|---|---|
| correct refusals | 5/6 |
| false refusals | 1/34 |
| faithfulness | 90.0 |
| citation precision | 95.7 |
| cites a gold section | 97.0 |
| p50 total ms | 58755.8 |
| p95 total ms | 67841.7 |

Answer time is the original model call through `claude -p`, which adds CLI start-up (about 2–3 s) that an API call would not have.
