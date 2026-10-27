# Design decisions

Why Rulebook is built the way it is, and what each choice costs. Every number referred to here is in `eval/results/`.

## Retrieval

**Shipped: dense search, routed by jurisdiction, then reranked.** The original design was hybrid search plus a reranker. The first dev run showed it scoring *below* plain dense search: 67.4% recall@10 against 69.6%. Three measurements on the dev questions decided the change. All three use the *candidate pool*, the share of gold sections in the 20 passages the reranker gets to see, because the reranker can only reorder what is in it.

**1. Routing is the biggest lever.** Compliance questions usually name the country ("…in Germany", "στη Φινλανδία").
- **How it works:** `jurisdictions()` in `search.py` matches country names and adjectives in English and Greek, plus the laws' and regulators' names. It lower-cases the question and strips accents first. Qdrant then searches only those jurisdictions' sections, and a question that names none searches all four.
- **Dev result:** the candidate pool went from 82% to 92%. On cross-language questions it went from 83% to 100%.
- **Why it matters so much here:** without routing, English questions about German or Finnish law mostly retrieved UK sections. The UK text is the largest of the four and shares the question's language, so it wins on similarity even when it's the wrong country. Most of the 23 answerable dev questions Claude refused in that first run had only UK sources in front of it.
- **Coverage:** routing kept every gold jurisdiction for all 66 answerable dev questions. Eleven named no country and were searched unfiltered.
- **Cost:** a question that names one country but needs another loses the answer silently. The four patterns were written from country names, not from the questions, and the test split measures whether they generalise.

**2. Hybrid search lost, and the table keeps it to show why.** BGE-M3's sparse output is learned keyword weights. Keywords can't connect an English question to German text, so on cross-language questions sparse search found 0% of the gold sections in its top 20.
- **What fusion did:** reciprocal rank fusion gives that noise an equal vote, and the pool dropped from 82% (dense) to 75% (fused).
- **Variants that didn't help:**
  - down-weighting sparse with Qdrant's weighted RRF: 64–71%
  - fusing inside the routed jurisdictions: 89%, against 92% for routed dense
- **Where hybrid would win:** a single-language corpus full of exact identifiers (section numbers, product codes), where keywords carry what embeddings blur.

**3. The reranker is for the top of the list.** A cross-encoder (bge-reranker-v2-m3) reads the question and a passage together, which is more precise than comparing two separately computed vectors. It reorders the 20 candidates, and Claude sees only the top 5, so recall@5 and MRR are where it should show.
- **Cost:** about 50 s per question on this CPU (20 passages × 512 tokens through a 568M-parameter model). That's why it sees only 20 candidates and why CI doesn't gate on it. On a GPU it would take a fraction of a second.

**Why BGE-M3.** One model gives dense vectors in 100+ languages, so an English or Greek question lands near German and Finnish text. It also gives the learned sparse weights that the hybrid rows test, so the comparison needs no second model and no language-specific BM25 (German compounds, Finnish case endings, Greek accents).

**RRF where rankings are merged.** Hybrid and the translate baseline merge ranked lists by rank, not score. Cosine similarities and sparse dot products are on different scales, and RRF has one constant (k=60) and nothing to tune.

**Translate-the-query baseline.** The obvious alternative to multilingual embeddings is to translate the question into all four languages, search each, and merge. It costs an LLM call per question. Table 3 compares the two.

**Qdrant in local file mode.** Development and CI need no server. The same client code talks to a real server when `QDRANT_URL` is set, which is what `docker-compose.yml` does.

## Chunking

**One chunk per legal section, headed with its citation.** Sections are the unit a compliance analyst cites. A chunk starts with e.g. "GlüStV 2021 § 6c …", so the citation is part of what gets embedded. Long sections split at paragraph breaks, and a single paragraph that overflows is cut by tokens.

**The fixed-window baseline ignores structure on purpose.** That's the comparison. A window is credited to the section that owns most of its tokens. This is stricter than crediting every section it touches, and it matches what a user would see cited.

## Evaluation

**Metrics at section level.** A hit is a section, not a chunk. Chunks are de-duplicated to their section in rank order. Recall@k for a multi-section question is the share of its gold sections found.

**Retrieval and answers are scored separately.** When an answer is wrong, the first question is whether the right section was even retrieved. Retrieval metrics answer that without any LLM. Answer metrics (faithfulness, citation precision, refusals) only run on top of it.

**Unanswerable questions.** They have no gold sections, so they're left out of retrieval metrics. They count in the answer metrics: the system should say `INSUFFICIENT_CONTEXT` instead of answering from memory.

**Partial answers instead of refusals.** In the first dev run Claude refused comparison questions outright when one country's section was missing, even though it had the other country's rule in front of it. The prompt now asks it to answer the covered part and say which part is missing. `INSUFFICIENT_CONTEXT` is kept for questions the sources don't touch at all, which is what the unanswerable questions test.

**Frozen test split.** 40 of the 120 questions are test. Tuning happens on the 80 dev questions, and test is run once for the final table. Routing, the hybrid comparison and the prompt change were all decided on dev.

**Retrieval is saved, so labels can change without re-searching.** Each run stores every question's retrieved chunk IDs and ranked sections in `eval/results/<split>.json`.
- `--reuse` rescores them against the current labels in seconds.
- `--reuse --generate` re-answers the saved retrieval after a prompt change.
- Re-running retrieval itself takes over an hour on this CPU, mostly the reranker.

**The question set is a draft.** Claude drafted the questions and labels from the section texts, and they are pending human review (see `eval/LABELLING.md`). Say so if asked. Until the review is done, the numbers measure the system against a careful but unreviewed label set.

## LLM calls

**Subscription for experiments, API for everyone else.** The experiments ran through headless Claude Code (`claude -p`) on a Claude subscription. Anyone else running the repo sets `ANTHROPIC_API_KEY` and gets the Anthropic API. Same prompts, same cache.

**Isolation.** The prompt contains retrieved legal text, which counts as untrusted input. So `claude -p` runs with:
- no tools (`--tools ""`)
- no MCP servers (`--strict-mcp-config`)
- no settings at all: no hooks, no plugins, no CLAUDE.md (`--setting-sources ""`)
- an empty temporary working directory
- nothing saved

With `--setting-sources project` the user-level CLAUDE.md was still injected. The empty value removed it. The prompts also tell the model that the sources are data, not instructions.

**Exact model IDs, never aliases.** Both paths pass `claude-sonnet-5-5` and `claude-haiku-5-5` (`MODELS` in `llm.py`). The CLI's bare `sonnet` / `haiku` aliases follow whatever the installed CLI version defaults to: on 2.1.132 they meant Sonnet 4.6 and Haiku 4.5. A first set of answers was generated that way before the check caught it. The cache key now includes the model ID, so a reply from one model is never served for another. All reported answers come from the pinned models.

**Structured output wherever code parses the reply.** The judge and the query translator return JSON that code reads, so they use structured output: `--json-schema` on the CLI, `output_config` on the API. A prompt saying "reply with JSON only" works almost every time. Then one German quotation („…") closed with a plain `"` broke a judge reply and crashed a run. A schema makes the shape a guarantee rather than a request. Answers are prose, so they stay plain text.

**What the judge counts as a claim.** Statements about the sources themselves ("the sources don't cover Finland") are not claims about the rules. The answer prompt asks for them, and they can't carry a citation.
- **What went wrong:** the first judging pass counted them as unsupported. 75 of the 84 unsupported claims across both splits had no citation, mostly of that kind, and faithfulness read about 86% for answers that were behaving as asked.
- **The fix:** the judge prompt now leaves those statements out. An uncited claim about the rules still counts as unsupported.
- **The rule behind it:** this is a fix to the measuring instrument, made because the rule was inconsistent with the answer prompt. No number was being tuned. It applies to dev and test alike.

**Sonnet answers, Haiku judges.** The judge is a different, cheaper model that checks each claim against the cited source. Both are Claude, so they may share blind spots. Spot-check a sample of judge verdicts by hand before trusting the faithfulness number.

**Caching.**
- Document embeddings are cached in SQLite by text hash.
- LLM replies are cached by prompt hash, together with the original call time.
- Reruns are free and reproducible.
- Query embeddings are not cached, so measured search latency includes encoding the question.

**Retries.** Rate-limit and overload errors are retried with backoff (10 s, doubling, five times); a subscription usage limit stops the run instead. A long eval shouldn't die at question 70 over one 529. Latency is taken from the attempt that succeeded.

**Latency caveat.** Answer time through `claude -p` includes CLI start-up of about 2–3 s, which an API call wouldn't have. Retrieval latency is measured directly.

## CI

**What the gate checks.** On every PR, CI runs the shipped first stage (routed dense search) on the dev questions and fails if recall@10 drops more than 1 point below `eval/baseline.json`.
- It gates the first stage, not the reranker, because reranking every dev question on a CPU runner takes over an hour.
- The reranker only reorders the first stage's top 20, so a first-stage regression is the one that loses answers outright.
- **Trade-off:** a reranker-only regression would not be caught.

**The demo of a bad change.** `RULEBOOK_CHUNK_TOKENS=64` (64-token chunks) makes the gate fail. The output is in the README.

**CPU-only torch on Linux.** CI and Docker install torch from the CPU wheel index. Otherwise they would download several GB of CUDA libraries they can't use.

## Corpus

Fetched by scripts, never committed. Reuse terms differ per source (the UK text is under the Open Government Licence, the others less clearly). Shipping scripts keeps the repo clean either way.

| Source | Caveat |
|---|---|
| UK LCCP | Current version at fetch time; the version date is recorded in each record. |
| DE GlüStV 2021 | Official Bavarian portal, all sections. |
| FI Rahapelilaki 10/2026 | The new act; most of it isn't in force until 1.7.2027. |
| EL Ν. 4002/2011 arts 25–54 | Third-party consolidation (taxheaven.gr). No official consolidated text was found online. |

## What I'd do next

- Finish the human review of the question set and re-run the test split.
- Give comparison questions a candidate quota per named jurisdiction. They are still the weakest type, because one country's sections can fill all 20 slots.
- Replace the routing regexes with a small classifier once there are questions phrased in ways the regexes miss.
- Add BGE-M3's third output (ColBERT multi-vectors) as a reranking step that's cheaper than the cross-encoder.
- Run on a GPU and report latency there.
