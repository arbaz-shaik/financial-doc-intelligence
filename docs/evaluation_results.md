# Evaluation results: baseline (golden set v1)

System under test: all-MiniLM-L6-v2 embeddings, ChromaDB, 512-character chunks with 50 overlap, LangGraph agent (router, retrieve + LLM rerank, generate, risk flagger), generator `openai/gpt-oss-120b` on Groq. Judge: `qwen/qwen3.8-27b`. Method and metric definitions: [`evaluation/README.md`](../evaluation/README.md).

## Summary

| Metric | Result |
|---|---|
| Retrieval hit@5 (vector search, perfect routing) | **82%** (18/22) |
| Routing accuracy | **57%** (17/30) |
| End-to-end hit@5 (full agent) | **50%** (11/22) |
| Abstention on unanswerable questions | **4/4** |
| Faithfulness (answered questions only) | **0.94** (n=10) |
| Reference coverage (strict lower bound) | **0.27** (n=26) |
| Latency | median 9.6 s, p95 13.4 s |

**Main finding: most failures happen before generation.** Routing is the largest problem. When the generator receives the right route and the right chunks, it answers, stays grounded, and never wrongly abstains.

## 1. Retrieval only

Vector search with each question's expected source as the filter (no router, no reranker, no LLM).

| hit@1 | hit@3 | hit@5 | hit@10 | MRR@10 |
|---|---|---|---|---|
| 50% | 77% | 82% | 86% | 0.63 |

Misses (not in the top 5): q13 (employee count, not in top 10), q14 (dividends, not in top 10), q28 (direct/indirect sales, rank 9), q29 (seasonality, not in top 10).

**Diagnosis of q13.** The top 5 results were filing boilerplate (exhibit list, auditor sign-off, statement headings), not employee-related at all. Testing three phrasings:

| Query | Rank of the expected chunk |
|---|---|
| "How many full-time equivalent employees did Apple report as of September 27, 2025?" | not in top 10 |
| "How many full-time equivalent employees does Apple have?" | not in top 10 |
| "full-time equivalent employees" | 1 |

The embedding of a full question is dominated by common words ("Apple", question phrasing), not the rare key phrase. Keyword search (BM25) weights terms by rarity (IDF) and would rank this chunk highly.

**q14 and q29:** the expected chunks mix two topics (dividends with accounting pronouncements; seasonality after a section on patent licensing), because the chunker splits every 512 characters regardless of section boundaries, which dilutes their embeddings.

## 2. Routing

| Type | Correct |
|---|---|
| sec | 10/18 |
| news | 3/4 |
| general | 1/4 |
| unanswerable | 3/4 |

| Confusion | Questions | Pattern |
|---|---|---|
| sec → news (6) | q03, q06, q07, q09, q12, q26 | Topics that sound like current events (lawsuits, tariffs, AI, regulators) although the 10-K discusses them |
| sec → general (3) | q02, q11, q21 | No explicit filing cue |
| general → sec (3) | q04, q16, q17 | Definitions that mention filing terms |
| news → sec (1) | q25 | A financial figure, but fiscal 2026 is only in the news |

The router classifies by topic keywords rather than by where the answer can be found.

**Not all routing errors cost the same.** `sec → news` misroutes all scored 0 reference coverage (the news filter excludes the 10-K). `sec → general` misroutes still scored 0.80 (q02) and 0.67 (q11), apparently because the general route searches without a source filter. Defaulting to an unfiltered search when uncertain is much safer than guessing a narrow source.

## 3. End to end

End-to-end hit@5 is 50% (11/22), against 82% with perfect routing. Every miss is explained: 7 by routing (q03, q06, q07, q09, q12, q25, q26) and 4 by retrieval (q13, q14, q28, q29).

**Abstention.** All 4 unanswerable questions abstained. 12 of 26 answerable questions also abstained, and every one is explained upstream: the 7 misroutes above, 2 definitions routed to `sec` (q16, q17), and 3 retrieval misses (q13, q28, q29). The generator abstains when the context lacks the answer instead of inventing one, which is the right failure mode for financial questions.

## 4. Failure stages

Each answerable question is assigned to the earliest stage that failed.

| Stage | Count | Questions |
|---|---|---|
| Routing | 12 | q02, q03, q04, q06, q07, q09, q11, q12, q16, q17, q25, q26 |
| Retrieval | 4 | q13, q14, q28, q29 |
| Abstained (with the right chunks) | 0 | |
| Incomplete (answered, coverage < 1) | 8 | q01, q10, q15, q18, q22, q23, q24, q30 |
| OK | 2 | q08, q27 |

## 5. Worst five, one per failure mode

Ranking by score alone is uninformative (14 questions tie at coverage 0), so these were chosen to show the different ways the system fails.

| Question | Failure | Why |
|---|---|---|
| q07 tariffs | Routing (sec → news) | The most common failure: a topic that sounds current, answered in the 10-K |
| q25 fiscal 2026 capex | Routing (news → sec) | Only news covers fiscal 2026; searching the filing cannot find it |
| q13 employee count | Retrieval: query wording | Common words outweigh the rare key phrase |
| q29 seasonality | Retrieval: mixed-topic chunk | The answer sentence sits in a chunk mostly about patent licensing |
| q01 supply chain | Incomplete generation | Right chunks retrieved, but the answer omitted 2 of 4 reference facts (single-source components, semiconductor shortages) |

## 6. Trusting the measurements

**RAGAS's "recall" is not textbook recall.** For q01 it returned 0.0 although the answer quotes a reference fact verbatim. Known-answer tests passed, the judge's per-claim verdicts were correct (2 of 4), and the source of `FactualCorrectness.ascore` showed why: recall is `tp / (tp + fn)` with `tp` counting the answer's claims supported by a deliberately short reference. Reference coverage was rebuilt from the verdict step and validated:

| Test | Expected | Result |
|---|---|---|
| Reference vs itself | 1.0 | 1.0 |
| Answer with the reference appended | 1.0 | 1.0 |
| Unrelated text | 0.0 | 0.0 |
| Real q01 answer (2 of 4 facts) | ~0.5 | 0.5 |

`ContextRecall` with the answer as context scored the q01 answer 1.0 (it judges whole sentences), so it was rejected. Only the realistic test exposed that.

**Judge spot-check.** On three hand-checked answers, the judge agreed once:

| Question | Judge | Human | Agree |
|---|---|---|---|
| q01 | 0.50 | 2 of 4 facts present | yes |
| q23 | 0.00 | core fact present; "Bloomberg" and "CEO" missing | no, too strict |
| q24 | 0.00 | Counterpoint, ~6 million, this year all present; "foldable" not stated | no, too strict |

Removing formatting (markdown bold, citation markers, Unicode hyphens) did not change the verdicts. The judge bundles core facts with peripheral details into one claim and fails the claim if any detail is missing. Reference coverage is therefore a strict lower bound.

**Faithfulness on abstentions is noise.** Abstaining answers scored 1.0 (q13, q16, q26, q28) or 0.0 (q25, q29) for the same kind of text. They are excluded from the faithfulness mean.

**Unscored.** Faithfulness could not be judged for 4 long answers (q04, q08, q14, q18): the judge's reply exceeded the free tier's output limit. Since long answers have more room for unsupported claims, the faithfulness mean may slightly overstate grounding.

## 7. Data observations

- NewsAPI's free tier truncates content to about 200 characters, so news chunks hold headlines and opening sentences only.
- Some news chunks are not about the company (matched by ticker), and some are non-English (Japanese Mac app updates), which the English-only embedding model handles poorly.
- Several 10-K passages appear twice (Risk Factors and MD&A; Business and Notes).
- Some chunks are XBRL tags or flattened financial tables.
- PDF-to-text conversion dropped some spaces ("inthe", "GreaterChina"), and repeated page headers ("Apple Inc. | 2025 Form 10-K | NN") attract filing-style queries.

## 8. Hypotheses for the next iteration

Ordered by expected impact on this baseline:

1. **Router:** define routes by where the answer lives, add examples from the misroutes, and fall back to an unfiltered search when uncertain (targets 12 routing failures).
2. **Hybrid search (BM25 + vectors):** rare key terms (q13).
3. **Strip page headers and footers** during parsing.
4. **Section-aware chunking:** one topic per chunk (q14, q29).
5. **Generation completeness:** prompt the generator to cover every relevant retrieved chunk (q01, q15, q30).
6. **Evaluation:** add explicit `key_facts` to the golden set, so coverage checks must-have facts instead of a judge's decomposition of prose.