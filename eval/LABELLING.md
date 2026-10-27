# How the question set was labelled

**Status: DRAFT. Pending human review.**

Claude (an AI model) drafted all 120 questions and labels in `eval/questions.jsonl` from the parsed section texts. **No human has reviewed them yet.** Don't report any number from this set as a result on "hand-labelled questions" until the review below is done and signed off.

The project plan says the questions should be written by the project owner, and that an LLM shouldn't write them in one go. This draft goes against both. Treat it as a starting point to edit, rewrite or replace, not as finished labels. Each question was written against a section Claude had read, but they were all drafted in one working session.

```
Reviewed by:
Date:
```

## Corpus the labels refer to

Labels are section ids from `data/sections/*.jsonl`, built by `uv run python -m rulebook.corpus`. If a source changes and a section is renumbered, its labels have to be re-checked.

| Jur. | Source | Version used | Sections |
|---|---|---|---|
| UK | UKGC Licence Conditions and Codes of Practice, print edition (gamblingcommission.gov.uk) | Version effective from 29 July 2026 | 132 |
| DE | GlüStV 2021, gesetze-bayern.de (all-sections view) | Text gilt ab 01.01.2023; last amended by Vertrag vom 26. März 2026 (GVBl. S. 550) | 75 |
| FI | Rahapelilaki 10/2026 (HE 16/2025), Finlex open data, consolidated Finnish AKN XML | Consolidated as of 2026-01-16; mostly in force 1.7.2027 (ch. 2 and 9 and some §§ from 1.3.2026) | 106 |
| EL | Ν. 4002/2011, arts 25–54 (incl. 45Α, 52Α), taxheaven.gr per-article consolidated text | Amendments incorporated up to ν. 5313/2026 (ΦΕΚ Α' 102/25.06.2026) | 32 |

Notes for the reviewer:
- **FI:** Most of the Finnish act isn't in force yet. Questions say "under the new act" where that matters.
- **EL:** The Greek text is a third-party consolidation. No official consolidated text was found online (et.gr has only the original and amending ΦΕΚ). Spot-check any EL answer that matters against the ΦΕΚ.
- **EL 5313/2026:** The Greek law hasn't been re-codified. 5313/2026 is an amending law, and taxheaven's "Κωδικοποιημένος με 5313/2026" means "consolidated up to 5313/2026".

## The mix

| type | n | en | el | test | what answers it |
|---|---|---|---|---|---|
| lookup | 50 | 28 | 22 | 17 | one UK or EL section |
| crosslingual | 30 | 18 | 12 | 10 | DE or FI text only |
| comparison | 20 | 12 | 8 | 7 | ≥2 sections from ≥2 jurisdictions |
| unanswerable | 20 | 14 | 6 | 6 | nothing (`answer_ids: []`) |
| **total** | **120** | **72 (60%)** | **48 (40%)** | **40** | |

**Why lookups only point at UK and EL.** By the type definitions, an English or Greek question answered by German or Finnish text is `crosslingual`. So single-jurisdiction DE/FI questions are all in the crosslingual bucket. Some lookups cross languages anyway: 6 Greek questions about the UK LCCP and 6 English questions about the Greek law.

**Test split.** Within each type, every third question (index 1, 4, 7, … in file order) is `test`. For unanswerable, the last eligible one stays in dev so the total is exactly 40. `tests/test_corpus.py` checks the per-type shares.

## Process used for the draft

1. Built the corpus and listed every section id and title.
2. Picked target sections that cover what a compliance analyst asks about: limits, age, self-exclusion, bonuses, marketing, AML, licensing, fines and player funds. Each jurisdiction got a spread.
3. For each target, read the section in its original language (German and Finnish included) and found the paragraph that answers. Wrote the question as an analyst would ask it, avoiding the section's own wording. Recorded the paragraph in `notes`.
4. **Comparison** questions list every section needed to answer each side. Where a second section in the same jurisdiction also answers directly, it is included too (e.g. FI § 24 and § 20 for age).
5. **Unanswerable** questions are on-topic for an analyst but outside these four texts: taxes and duties, fee amounts, loot boxes, VPNs, esports, statistics. For each, the whole corpus was keyword-searched in all four languages to confirm nothing answers it. Where a section looks relevant but doesn't answer, `notes` names it as a distractor.
6. Automated checks in `tests/test_corpus.py`:
   - every `answer_id` exists in `data/sections/`
   - type and language counts
   - stratified 40-question test split
   - crosslingual answers are DE/FI only
   - comparisons span ≥2 jurisdictions
   - unanswerable has no ids
7. Lexical overlap check: the share of a question's content words (4+ letters) that also appear in its answer section(s) averages 0.22. Crosslingual questions are near 0 by construction. The highest are lookups that use an official term, e.g. q012 "financial vulnerability check" and q010 "regulatory return". Rerun this after edits; rising overlap flatters BM25/sparse retrieval.

## Known weaknesses of the draft

- **Phrasing.** The questions are Claude's English and Greek. Some Greek questions may read as translated rather than as a Greek analyst would write them.
- **Missing relevant sections.** `answer_ids` lists the sections Claude judged to answer directly. Others may also answer, especially in the UK LCCP, where the same duty appears in several remote / non-remote / SR / ordinary code variants. An answer missing from the labels makes recall look worse than it is.
- **Unanswerable is "not in this corpus", not "not regulated".** Several of them are answered by laws outside the corpus, e.g. UK slot stake limits and German gaming taxes. That is intended: the system should refuse rather than answer from memory.
- **One section, two questions.** A few sections back two lookups (EL 32, EL 45, DE 5), which slightly overweights them.

## Audit (27 Oct 2026)

**This was a second model pass, not human review.** Claude re-checked the draft labels against the section texts. The status at the top of this file is still DRAFT, pending human review, and the review log below stays empty.

**Checked:** all 120 questions, dev and test.
- Every gold section was read in full against its question, and each comparison was checked for coverage of every jurisdiction it asks about.
- `data/sections/` was keyword-searched in English, German, Finnish and Greek for other sections that answer.
- Every unanswerable question was searched again in all four languages.
- The retriever, Qdrant and `eval/results/` were not used, so the audit stays independent of the system it grades.

**Rule for adding a section:** the section must state the asked rule as directly as the existing gold, for a case the question's wording covers. In practice that meant two kinds of section: a licence-type variant that the existing gold excludes (e.g. remote lotteries, remote pool betting), and a near-verbatim restatement in another article. Venue-entry corollaries, clauses that only set penalties, and definitions were not added. They are listed under "Doubtful" below.

**Changed: 17 of 120 questions (7 test, 10 dev).**
- 15 got extra ids in `answer_ids`, 17 ids in total, so the label count went from 127 to 144.
- 1 note was corrected (q044) and 1 unanswerable question was reworded (q119).
- No id was removed, and no `qid`, `split`, `type` or `lang` changed. The 50/30/20/20 mix and the 40-question test split are as before.
- The `notes` of each changed question now cover the added sections.

| qid | split | change | why (decisive phrase) |
|---|---|---|---|
| q014 | test | + `UK:LCCP:CP-5.1.12` | Also governs emails and texts to customers who never opted in. The options are "set to opt-out by default", and "Customers must not receive direct marketing that contravenes their channel or product preferences." |
| q019 | dev | + `UK:LCCP:CP-3.2.13` | 3.2.11 excludes lottery licences. The remote lottery SR code has the same duty: "licensees must verify the age of a customer before the customer is able to: … access any free-to-play versions of lotteries (for example instant win or digital scratchcard lotteries)". |
| q025 | dev | + `UK:LCCP:CP-3.6.8` | 3.6.7 excludes remote pool betting, which 3.6.8 covers: "(b) otherwise to employ children and young people to provide facilities for gambling". For football pools only under-16s are barred. |
| q027 | dev | + `UK:LCCP:LC-15.1.2` | Para 2 is a duty tied to the governing bodies' betting rules: "must as soon as reasonably practicable provide the sport governing body with relevant and necessary information … that they know or suspect may relate to a breach of betting rules applied by that governing body". |
| q028 | dev | + `UK:LCCP:LC-15.1.2` | The gold 8.1.2 says it elaborates this condition: "In considering their obligations under licence condition 15.1.2 …". Para 1 is the duty itself: "provide the Commission with any information … that they: (a) know relates to or suspect may relate to the commission of an offence under the Act". |
| q030 | dev | + `EL:N4002:48` | 48 §5 sets the same age limit for online play: "απαγορεύεται να επιτρέπουν τη συμμετοχή … σε φυσικά πρόσωπα που δεν έχουν συμπληρώσει το εικοστό πρώτο έτος της ηλικίας τους". This is the same standard as FI § 20 next to § 24. |
| q044 | test | notes only | The note cited 52 §1(α), which covers games in general. The question asks about τυχερά παίγνια, which §1(β) covers: "Αν τα παίγνια που διεξάγονται είναι τυχερά, τιμωρείται με κάθειρξη τουλάχιστον δέκα (10) ετών". The note now covers §1(α)–(δ). The id was already right. |
| q050 | test | + `EL:N4002:29` | 29 §3 item 18 repeats the list in 30 §1 almost word for word: "… (Π.Σ.Ε.Ε.), ώστε να επιτυγχάνεται: 18.1) Η ηλεκτρονική παρακολούθηση όλων των μορφών παιγνίων …". |
| q074 | dev | + `FI:RAHAPELILAKI:41` | The same rule applies to an open-ended casino ban set at the player's request: "Henkilö voi pyytää toistaiseksi asetetun kiellon tai rajoituksen poistamista aikaisintaan vuoden kuluttua …" and "pelaajan pyynnöstä asetettu toistaiseksi voimassa oleva pääsykielto tai rajoitus poistetaan kolmen kuukauden kuluttua poistamista koskevasta pyynnöstä". |
| q082 | test | + `EL:N4002:48` | As q030. |
| q084 | dev | + `UK:LCCP:CP-3.7.1`, + `UK:LCCP:LC-6.1.1` | LC 6.1.2 (no credit cards) gave only part of the UK answer. Betting and remote operators may lend under conditions: "Licensees who choose to offer credit to members of the public … must also: (a) have procedures for checking and scoring applications for credit". AGCs and FECs may not lend at all: "Licensees must neither: (a) provide credit themselves in connection with gambling". |
| q086 | dev | + `UK:LCCP:CP-5.1.12` | As q014: the per-product, per-channel opt-in is a precondition for UK direct marketing. |
| q091 | test | + `FI:RAHAPELILAKI:53` | This is the only FI restriction on gambling advertising at sports events: "Rahapelejä ei saa markkinoida sellaisissa urheilutapahtumissa tai muissa yleisötapahtumissa, jotka on suunnattu alaikäisille." |
| q094 | test | + `EL:N4002:52` | 52 §10 is the statutory blocking duty on ISPs: "απαγορεύεται στους παρόχους υπηρεσιών διαδικτύου (ISPs) … να επιτρέπουν την πρόσβαση σε παρόχους τυχερών παιγνίων μέσω του διαδικτύου, οι οποίοι δεν έχουν λάβει άδεια … και αναφέρονται στον οικείο κατάλογο (black list)". |
| q097 | test | + `FI:RAHAPELILAKI:55` | This is the FI counterpart of the EL gold 35 §1, which requires ads to name the persons barred from playing and the help lines: "Markkinoinnin tulee aina sisältää tieto rahapelaamisen sallitusta ikärajasta sekä siitä, mistä saa tietoa … rahapeliongelmiin apua tarjoavista palveluntuottajista." |
| q099 | dev | + `EL:N4002:52`, + `DE:GLUESTV:9` | EL 52 §9: "απαγορεύεται στα πιστωτικά ιδρύματα ή τα ιδρύματα πληρωμών … να πραγματοποιούν πληρωμές … στους λογαριασμούς που τηρούν σε αυτά πάροχοι τυχερών παιγνίων μέσω του διαδικτύου, οι οποίοι δεν έχουν λάβει άδεια". DE § 9 Abs. 1 Nr. 4: "den am Zahlungsverkehr Beteiligten, insbesondere den Kredit- und Finanzdienstleistungsinstituten, … die Mitwirkung an Zahlungen für unerlaubtes Glücksspiel … untersagen". |
| q119 | dev | question reworded, notes rewritten | 42 §4 sets an age for one shop role: "Ο υπεύθυνος εκμετάλλευσης πρέπει να είναι φυσικό πρόσωπο ηλικίας 25 έως 60 ετών". So "employees working in Greek gaming shops" was partly answerable, and the note's "no staff age requirement" was wrong. The question now reads "What is the minimum age for cashiers and other floor staff in Greek gaming shops?", with 42 §4 named as a distractor. It stays unanswerable, so the bucket keeps its 20 questions. |

**Doubtful, left alone.** These are for the human review:
- **q016:** SR 3.5.3 para 5, "close any customer accounts of an individual who has entered a self-exclusion agreement", implies that all accounts are closed. The multi-account rule itself is in 3.9.1.
- **q030, q075, q082:** these venue-entry rules restate the age limit but were not added:
  - EL 33 §1 bars 18–21-year-olds from gambling venues.
  - EL 54 §12 sets casino entry at 21; it is an amendment to Law 2206/1994.
  - FI § 41 paras 1 and 3 keep under-18s out of casinos and arcades.

  Adding all of them would put q082 at 7 gold, which caps its recall@5 at 5/7.
- **q054, q083:** DE § 6i Abs. 3. The panic-button lock is entered in the Sperrdatei and "endet ohne Antrag nach Ablauf von 24 Stunden", which makes it arguably the shortest exclusion in the file. It is a "kurzzeitige Sperre", though, not a Selbstsperre. Consider saying "Selbstsperre" in q054.
- **q053:** DE § 4 Abs. 5 Nr. 5 sets a one-minute wait when switching between the same licensee's areas or domains. The question means another operator (§ 6h).
- **q048:** EL 48 §4 requires a special ΕΕΕΠ licence for games of chance via audiovisual media. It is the generic clause; Art. 53 is the specific one.
- **q050:** the EL 25(ε) definition of the Π.Σ.Ε.Ε. states its purpose in one line.
- **q045:** EL 51 §5 and 52 §10 refer to the ΕΕΕΠ black list but do not say how it is kept.
- **q077:** FI § 53 para 4 bans marketing at youth sports events. That is marketing, not sponsorship.
- **q091:** FI § 51 para 3(3) allows marketing at sports events, subject to the moderation rule in para 2.
- **q092:** FI § 28 lets players play only while identified as a registered player.
- **q093:** EL 35 §2 bans advertising credit for gambling.
- **q096:** EL 33 §3 requires entry-ban signs inside and outside shops.

**Checks after the edits:**
- `uv run pytest -q`: 18 passed.
- Every `answer_id` exists in `data/sections/`.
- No question has a duplicate id.
- The type rules, the type counts and the test-split membership are unchanged.
- The lexical-overlap figure was not rerun. The only question text that changed is q119, which is unanswerable and has no answer sections.

## Review checklist (for the project owner)

Work through every question, dev and test, before running the final table:

1. [ ] **Read the section yourself.** Open the `url` of each `answer_id` and confirm the paragraph in `notes` really answers the question. For DE and FI, read the original next to a machine translation.
2. [ ] **Search for other answering sections.** Search `data/sections/` for the key terms and add any other section that answers equally directly.
3. [ ] **Fix the phrasing.** Rewrite anything that sounds off in your own words, especially the Greek. Rewrite at least a good share of them so the set is genuinely yours, and keep word overlap with the section low.
4. [ ] **Check unanswerables.** Try to answer each one from the corpus in all four languages. If you can, convert it to an answerable question or replace it.
5. [ ] **Re-check types after edits.** Crosslingual = DE/FI only; comparison = ≥2 jurisdictions; lookup = one jurisdiction.
6. [ ] **Re-run the checks.** Run `uv run pytest tests/test_corpus.py` after editing.
7. [ ] **Freeze the test split.** Once reviewed, don't look at test results while tuning. Only the 80 dev questions are for iteration.
8. [ ] **Sign off.** Fill in `Reviewed by:` and `Date:` above, and record what changed below.

## Review log

_(empty: no review has happened yet)_
