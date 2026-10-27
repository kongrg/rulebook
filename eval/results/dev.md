# Results — dev split (80 questions, 66 answerable)

Modes: `dense` BGE-M3 dense vectors · `sparse` its learned keyword weights · `hybrid` both, fused by RRF · `routed` dense search restricted to the jurisdictions the question names (all four if none) · `_rerank` cross-encoder over the top 20 · `translate_dense` the question translated into all four languages, one dense search each, fused by RRF. Shipped: `section512 · routed_rerank`.

## 1. Chunking

| Config | n | Recall@5 | Recall@10 | MRR | nDCG@10 | p95 ms |
|---|---|---|---|---|---|---|
| fixed512 · dense | 66 | 51.6% | 56.2% | 0.411 | 0.423 | 1091 |
| section512 · dense | 66 | 62.8% | 69.7% | 0.588 | 0.584 | 1101 |
| fixed512 · routed | 66 | 53.9% | 59.2% | 0.500 | 0.497 | 1603 |
| section512 · routed | 66 | 81.1% | 87.1% | 0.694 | 0.708 | 2142 |

## 2. Retrieval

| Config | n | Recall@5 | Recall@10 | MRR | nDCG@10 | p95 ms |
|---|---|---|---|---|---|---|
| section512 · dense | 66 | 62.8% | 69.7% | 0.588 | 0.584 | 1101 |
| section512 · sparse | 66 | 28.8% | 31.8% | 0.311 | 0.290 | 1904 |
| section512 · hybrid | 66 | 60.0% | 63.5% | 0.492 | 0.499 | 990 |
| section512 · routed | 66 | 81.1% | 87.1% | 0.694 | 0.708 | 2142 |
| section512 · routed_rerank | 66 | 82.6% | 87.6% | 0.785 | 0.791 | 97551 |

## 3. Cross-language: multilingual embeddings vs translating the query

| Config | n | Recall@5 | Recall@10 | MRR | nDCG@10 | p95 ms |
|---|---|---|---|---|---|---|
| section512 · dense | 66 | 62.8% | 69.7% | 0.588 | 0.584 | 1101 |
| section512 · translate_dense | 66 | 68.9% | 73.9% | 0.618 | 0.619 | 15280 |

Cross-language questions only:

| Config | n | Recall@5 | Recall@10 | MRR | nDCG@10 | p95 ms |
|---|---|---|---|---|---|---|
| section512 · dense | 20 | 47.5% | 62.5% | 0.411 | 0.459 | 1515 |
| section512 · translate_dense | 20 | 72.5% | 77.5% | 0.509 | 0.571 | 15280 |

translate_dense latency includes the translation call, so it is not comparable.

## Shipped config (section512 · routed_rerank) by question type

| question type | n | Recall@5 | Recall@10 | MRR | nDCG@10 | p95 ms |
|---|---|---|---|---|---|---|
| comparison | 13 | 50.0% | 60.3% | 0.614 | 0.526 | 62875 |
| crosslingual | 20 | 100.0% | 100.0% | 0.887 | 0.912 | 64329 |
| lookup | 33 | 84.8% | 90.9% | 0.791 | 0.823 | 99834 |
| unanswerable | – | – | – | – | – |

## Shipped config (section512 · routed_rerank) by question language

| question language | n | Recall@5 | Recall@10 | MRR | nDCG@10 | p95 ms |
|---|---|---|---|---|---|---|
| el | 27 | 85.2% | 90.7% | 0.739 | 0.769 | 74943 |
| en | 39 | 80.8% | 85.5% | 0.818 | 0.807 | 99834 |

## Shipped config (section512 · routed_rerank) by language of the answer

| language of the answer | n | Recall@5 | Recall@10 | MRR | nDCG@10 | p95 ms |
|---|---|---|---|---|---|---|
| DE | 11 | 100.0% | 100.0% | 0.886 | 0.915 | 64329 |
| EL | 14 | 92.9% | 92.9% | 0.839 | 0.866 | 62656 |
| FI | 9 | 100.0% | 100.0% | 0.889 | 0.909 | 68768 |
| UK | 19 | 78.9% | 89.5% | 0.756 | 0.791 | 102296 |
| mixed | 13 | 50.0% | 60.3% | 0.614 | 0.526 | 62875 |
| none | – | – | – | – | – |

## Answers (shipped config, top 5 chunks to the model)

| Metric | Value |
|---|---|
| correct refusals | 14/14 |
| false refusals | 6/66 |
| faithfulness | 92.0 |
| citation precision | 97.8 |
| cites a gold section | 95.0 |
| p50 total ms | 70583.8 |
| p95 total ms | 109392.6 |

Answer time is the original model call through `claude -p`, which adds CLI start-up (about 2–3 s) that an API call would not have.
