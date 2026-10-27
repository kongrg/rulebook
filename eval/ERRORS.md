# Error analysis: what still fails on the test split

The shipped pipeline (routed dense search, cross-encoder rerank, Claude Sonnet 5.5 answering from the top 5) on the 40 held-out questions. Seven questions miss in some way. Two of those are partial misses on redundant gold sections (q082, q097), where the answer is still right. The other five each fail by a different mechanism, below, with the fix I'd try first, on dev.

Ranks come from `eval/results/test.json`.

## 1. One country fills the list (q085, comparison)

> How do the UK and Finnish caps on bonus wagering requirements compare?

- **Gold:** UK SR code 5.1.1 (a 10× cap) and FI Rahapelilaki § 26 (*"enintään viisinkertaisen kierrätysvaatimuksen"*: at most 5×).
- **What happened:** routing correctly kept UK and FI, but all ten results are UK sections. § 26 is not in the top 10 of any configuration. A dev question that names only Finland (q068) finds the same section first.
- **Why:** the UK conditions are the largest part of the corpus and share the question's language, so in a mixed search they outscore the Finnish text.
- **What the answer did:** Claude answered the UK half and said the Finnish half was missing. That is correct given its sources, but it is no help to the analyst.
- **Fix:** a candidate quota per named jurisdiction, e.g. the 10 best per country, then rerank.

## 2. The reranker prefers its own language (q094, comparison, asked in Greek)

> Πώς μπλοκάρουν η Ελλάδα και η Γερμανία τις ιστοσελίδες παράνομων παρόχων τυχερών παιγνίων;
> (How do Greece and Germany block illegal gambling websites?)

- **What happened:** routed dense search found all three gold sections, at ranks 1, 6 and 8. One of them is GlüStV § 9, which lets the regulator order blocking by *"Zugangsvermittler und Registrare"*. The cross-encoder then dropped § 9 and filled the list with Greek sections.
- **What the answer did:** Claude answered for Greece only.
- **Why:** a Greek question against a Greek passage scores higher than the same question against a German passage. That is a known lean of multilingual cross-encoders, and here it beats the actual relevance.
- **Fix:** the same quota as #1, applied after reranking: keep each named country's best section in the top 5.

## 3. The reranker demotes the right section below its neighbours (q073, cross-language)

> What is the maximum penalty payment a company can face under Finland's new gambling law?

- **Gold:** § 85, *seuraamusmaksun suuruus*. For a company the payment is at most 4% of turnover, *"kuitenkin enintään viisi miljoonaa euroa"* (capped at €5 million).
- **What happened:** routing ranked § 85 4th. The reranker moved §§ 80 and 84 above it, which use the same vocabulary but cover the minor-infringement fee (*rikemaksu*) and when a penalty applies. § 85 ended up 8th, outside the five sources Claude sees.
- **What the answer did:** Claude said the sources don't state the penalty payment's maximum, and gave the fee range from § 80 instead. Each sentence is faithful to a cited source, so the judge can't catch this one. Only the gold labels do.
- **Fix:** pass the top 8 to Claude (a longer prompt, at a cost per question), or merge adjacent sections of the same chapter into one candidate.

## 4. Broad conditions crowd out the specific rule (q026, lookup, asked in Greek)

> Με ποιους όρους μπορεί ένας Βρετανός bookmaker να δίνει πίστωση σε πελάτες του;
> (On what terms may a British bookmaker give credit to customers?)

- **Gold:** SR code 3.7.1, *Provision of credit*: credit checks and scoring, a maximum credit limit per customer.
- **What happened:** it is not in the top 10 of any configuration, whether dense, routed, translated or reranked. The list is general UK conditions instead: payments (LC 5.1.2), anti-money laundering (LC 12.1.x), network arrangements (LC 3.1.x).
- **Why:** those sections show up for many UK questions on dev too. They sit near the middle of the UK cluster in embedding space (*hubness*), so they are close to almost any operator question. A Greek word for "credit" doesn't pull hard enough against them.
- **What the answer did:** Claude refused, correctly given its sources.
- **Fix:** a hubness correction, i.e. scaling each section's score by its average similarity to queries. Or a keyword signal used only when question and section share a language, which is where hybrid search should have earned its place.

## 5. An unanswerable question gets an adjacent answer (q111, unanswerable)

> What is the minimum age to buy National Lottery tickets in the UK?

- **Why it's unanswerable:** the National Lottery is licensed under its own Act, not the LCCP, and has been 18+ since 2021. The corpus doesn't cover it.
- **What happened:** retrieval returned the LCCP codes for society and local-authority lotteries (*"tickets may only be sold to persons aged 16 or over"*). Claude opened with *"The sources don't mention the National Lottery"* and then gave 16 for the lotteries they do cover.
- **Why it's wrong:** it is faithful and even flags the gap, but someone who skims takes away the wrong number. It also comes from a trade-off made on dev. The partial-answer instruction cut wrong refusals on comparisons, and it makes this kind of adjacent answer more likely. This is the one unanswerable question out of 20 that wasn't refused (dev 14/14, test 5/6).
- **Fix:** tell the model to refuse when the sources cover a different instrument than the one asked about. Or add each section's scope (*"applies to: non-remote lottery licences"*) to its chunk header, so the mismatch is visible in the text Claude reads.

## What the five have in common

- **Retrieval (#1, #2, #4):** a large group of same-language or general sections pushes a specific one out.
- **Not enough sources shown (#3):** the reranker reorders well on average (test MRR 0.839 → 0.862), but on #2 and #3 it is the step that loses the answer, and Claude sees only 5 sources.
- **Answer step (#5).**

The per-jurisdiction quota addresses #1 and #2 and is the next dev experiment. Comparisons are already the weakest type on dev (60% recall@10 against 91% for lookups), so the quota is where the remaining recall is.
