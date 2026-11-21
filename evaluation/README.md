# Evaluation

How we measure whether the system answers questions correctly, and where it fails.
Results and analysis: [`docs/evaluation_results.md`](../docs/evaluation_results.md).

## Pipeline

| Step | Command | Environment | Cost |
|---|---|---|---|
| Validate the golden set | `python -m evaluation.validate` | `.venv` | free |
| Retrieval check (hit@k, MRR) | `python -m evaluation.retrieval_check` | `.venv` | free |
| Run the agent on every question | `python -m evaluation.run_agent` | `.venv` | ~90 LLM calls |
| Deterministic scores (routing, end-to-end hit@5, abstention, latency) | `python -m evaluation.score_deterministic` | `.venv` | free |
| LLM-judged scores (faithfulness, reference coverage) | `.venv-eval/Scripts/python.exe -m evaluation.grade_ragas` | `.venv-eval` | ~100 judge calls |
| Per-question report and failure stages | `python -m evaluation.report` | `.venv` | free |

Shortcuts: `make eval` runs every free step; `make eval-run` and `make eval-grade` are kept separate because they cost API calls.

Generation (`run_agent`) and grading (`grade_ragas`) are separate steps that communicate only through `results/answers.jsonl`. That keeps grading resumable, lets the same answers be re-graded, and allows RAGAS to live in its own environment.

### Why a separate `.venv-eval`

Installing RAGAS into the app environment would upgrade packages the API depends on (`langgraph`, `langchain-core`, `groq`, `huggingface_hub`), so the laptop would no longer match the Docker image. Grading never imports the app, so it runs in an isolated environment pinned by `requirements-eval.txt`:

```bash
python -m venv .venv-eval
.venv-eval/Scripts/python.exe -m pip install -r requirements-eval.txt
```

Notable pins: `ragas==0.4.4`, `instructor==1.12.0` (RAGAS 0.4.4 needs `instructor.Provider.GENAI`, but its dependency range allows 1.3.2, which lacks it), `openai==1.109.1` (kept to avoid a major upgrade).

The judge is reached through Groq's OpenAI-compatible endpoint (`base_url=https://api.groq.com/openai/v1`), because RAGAS's Groq adapter returned an unusable client.

## Golden set: `golden_set.jsonl`

30 hand-written questions: 18 `sec`, 4 `news`, 4 `general`, 4 `unanswerable`. One JSON object per line, no comments or blank lines.

| Field | Meaning |
|---|---|
| `id` | `q01` ... `q30`, with no gaps |
| `type` | `sec`, `news`, `general` or `unanswerable` |
| `question` | The question asked |
| `expected_route` | What the router should choose: `sec`, `news` or `general` only |
| `reference_answer` | A correct answer, written from the source chunks |
| `expected_chunk_ids` | Chunks that actually answer the question (empty for `general` and `unanswerable`) |
| `evidence` | An exact quote from the expected chunks, so they can be found again if IDs change |
| `note` | Why choices were made (ignored by the code) |

### Rules for adding questions

1. Find expected chunks independently with `python -m scripts.find_chunks <words>`, never by copying what the system retrieves, or retrieval would grade itself.
2. Read the full chunk text before choosing; snippets mislead.
3. Include only chunks that answer the question, not passing mentions.
4. Prefer specific questions with a few clear answering chunks; broad questions make retrieval scores meaningless.
5. Write the reference answer from the chunks, and keep it consistent with the source.
6. Prefer 10-K questions. News questions use only headline facts (NewsAPI's free tier truncates content) and only chunks genuinely about the company.
7. Unanswerable questions route to where the topic would be searched, and are verified unanswerable with `find_chunks` (record the check in `note`).
8. No placeholders.
9. If the same answer appears in duplicate passages (for example Risk Factors and MD&A), list every copy.

`python -m evaluation.validate` enforces the mechanical rules: valid JSONL, required fields, valid types and routes, no placeholders, no duplicate or missing IDs, existing chunk IDs, and evidence quotes that appear verbatim in their expected chunks.

### Versioning

The golden set is a measuring stick: changing it makes later scores incomparable with earlier ones. After a baseline, record every change here as a new version.

- **v1** (baseline): 30 questions.

Chunk IDs depend on chunking settings. If `chunk_size` or `overlap` change, rebuild `expected_chunk_ids` using each entry's `evidence` quote.

## Metrics

| Metric | Measures | How |
|---|---|---|
| hit@k, MRR@10 | Does vector search find an expected chunk (with perfect routing)? | Deterministic |
| Routing accuracy | Did the router choose `expected_route`? | Deterministic |
| End-to-end hit@5 | Did the agent's final sources include an expected chunk? | Deterministic |
| Abstention | Unanswerable questions should say "not enough information"; answerable ones shouldn't | Deterministic phrase match |
| Faithfulness | Share of the answer's statements supported by its retrieved contexts | RAGAS `Faithfulness`, judge `qwen/qwen3.8-27b` |
| Reference coverage | Share of the reference answer's claims found in the answer | Custom, built on RAGAS claim verification |

Judge: `qwen/qwen3.8-27b`, a different model family from the generator (`openai/gpt-oss-120b`), to limit self-preference bias.

### Metric caveats

- **Reference coverage is custom** because RAGAS's `FactualCorrectness(mode="recall")` computes `tp / (tp + fn)`, where `tp` counts the *answer's* claims supported by the reference. With deliberately short references it collapses to 0. `ContextRecall` (answer as context) was too lenient: it judges whole sentences. The custom metric is validated by known-answer tests in `ragas_recall_check.py` (reference vs itself 1.0, answer plus reference 1.0, unrelated text 0.0, a known half-correct answer 0.5). It uses a private RAGAS step, safe because `ragas==0.4.4` is pinned and the tests detect breakage.
- **Reference coverage is a strict lower bound.** The judge splits a prose reference into claims that bundle core facts with peripheral details (attributions, job titles, descriptive wording), and fails the whole claim if one detail is missing.
- **Faithfulness is reported only for answers that answered.** Abstentions make no factual claims, and the judge's values on them are noise.
- **Faithfulness measures grounding, not correctness.** A correct definition answered from general knowledge scores low.
- **Free-tier limits:** ~1000 output tokens/minute for the judge (so `max_tokens=950`, about one call per minute) and a daily cap. Long answers can exceed the judge's output limit (`judge_output_limit`, not retried). Context precision is not judged, because retrieval ranking is measured deterministically by hit@k and MRR.

### Tools

- `ragas_recall_check.py`: regression test for reference coverage. Run after any RAGAS upgrade.
- `ragas_spotcheck.py`: per-claim verdicts and reasons, for auditing the judge on specific questions.

Evaluation does not run in CI: real LLM calls are slow, rate-limited and vary between runs. The deterministic logic is unit-tested in `tests/test_evaluation.py`.