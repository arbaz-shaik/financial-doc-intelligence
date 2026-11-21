r"""LLM-judged scores for saved agent answers. Runs in .venv-eval.

Metrics (judge: qwen/qwen3.8-27b, a different family from the generator):
- faithfulness: share of the answer's statements supported by the retrieved contexts
  (RAGAS Faithfulness).
- reference_coverage: share of the reference answer's atomic claims found in the answer.
  Built from RAGAS's claim decomposition + verification step, because the library's
  FactualCorrectness "recall" uses the ANSWER's claims as true positives
  (tp / (tp + fn), see FactualCorrectness.ascore), which collapses to 0 when references
  are deliberately minimal. Validated by known-answer tests in ragas_recall_check.py.

Permanent failures are recorded and NOT retried:
- "judge_output_limit": the answer is too long for the judge's reply to fit the
  free tier's ~1000 output tokens/minute (affects faithfulness on long answers).
- "no contexts": nothing was retrieved, so faithfulness is undefined.

Unanswerable questions are skipped (abstention is scored deterministically).
Resumable: finished questions are skipped; each result is saved immediately.

Usage:
    .venv-eval\Scripts\python.exe -m evaluation.grade_ragas            # all questions
    .venv-eval\Scripts\python.exe -m evaluation.grade_ragas q01 q02    # only these
"""

import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import FactualCorrectness, Faithfulness

JUDGE = "qwen/qwen3.8-27b"
GOLDEN = Path("evaluation/golden_set.jsonl")
ANSWERS = Path("evaluation/results/answers.jsonl")
OUT = Path("evaluation/results/ragas_scores.jsonl")
METRICS = ("faithfulness", "reference_coverage")


def load(path: Path) -> dict[str, dict]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {r["id"]: r for r in rows}


def with_retry(fn, attempts: int = 8, wait: int = 65):
    """Free tier: ~1000 output tokens/minute. On a rate limit, wait for the budget to refill.
    A DAILY limit can't be waited out within a run, so stop immediately instead."""
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:
            if "rate_limit" not in str(e) and "429" not in str(e):
                raise
            if "per day" in str(e):
                raise RuntimeError("Daily rate limit reached: resume tomorrow") from e
            if i == 1:
                print(f"    {str(e)[:300]}")  # show Groq's exact reason once
            print(f"    rate limited ({i}/{attempts}), waiting {wait}s")
            time.sleep(wait)
    raise RuntimeError("still rate limited after retries")


def reference_coverage(fc: FactualCorrectness, reference: str, answer: str) -> float:
    """Share of the reference's atomic claims that the answer supports (private RAGAS step, pinned 0.4.4)."""
    verdicts = asyncio.run(fc._decompose_and_verify_claims(reference, answer))
    return round(float(verdicts.mean()), 2) if len(verdicts) else 0.0


def score_one(metric_fn) -> dict:
    """Run one metric; record the value, or the error, without stopping the whole run."""
    try:
        result = with_retry(metric_fn)
        value = result.value if hasattr(result, "value") else result
        return {"value": value, "error": None}
    except Exception as e:
        msg = str(e)
        if "max_tokens length limit" in msg:
            return {
                "value": None,
                "error": "judge_output_limit",
            }  # permanent: answer too long to grade
        return {"value": None, "error": type(e).__name__ + ": " + msg[:200]}


def finished(err) -> bool:
    """None = scored. Permanent errors count as finished, because retrying would only waste budget."""
    return (
        err is None
        or err in ("judge_output_limit", "no contexts")
        or "max_tokens length limit" in err
    )


def summarise(done: dict[str, dict]) -> None:
    print("\nMean scores by type (n = scored questions):")
    for t in ("sec", "news", "general"):
        rows = [r for r in done.values() if r["type"] == t]
        parts = []
        for m in METRICS:
            vals = [r[m]["value"] for r in rows if r[m]["value"] is not None]
            parts.append(
                f"{m}={statistics.mean(vals):.2f} (n={len(vals)})"
                if vals
                else f"{m}=n/a"
            )
        print(f"  {t:<8} " + "  ".join(parts))
    unscored = [
        f"{r['id']}:{m}={r[m]['error'][:40]}"
        for r in done.values()
        for m in METRICS
        if r[m]["error"]
    ]
    if unscored:
        print("  Not scored: " + ", ".join(unscored))


def main() -> None:
    load_dotenv()
    llm = llm_factory(
        JUDGE,
        provider="openai",
        client=OpenAI(
            api_key=os.environ["GROQ_API_KEY"],
            base_url="https://api.groq.com/openai/v1",
        ),
        max_tokens=950,  # just under the 1000 output-tokens/minute limit, so requests are admitted
    )
    faithfulness = Faithfulness(llm=llm)
    fc = FactualCorrectness(llm=llm)

    golden, answers = load(GOLDEN), load(ANSWERS)
    done = load(OUT) if OUT.exists() else {}
    only = set(sys.argv[1:])

    todo = [
        q
        for q in golden
        if golden[q]["type"] != "unanswerable"
        and (not only or q in only)
        and not (q in done and all(finished(done[q][m]["error"]) for m in METRICS))
    ]
    print(f"{len(todo)} questions to grade with {JUDGE}")

    for i, qid in enumerate(todo, start=1):
        g, a = golden[qid], answers[qid]
        print(f"[{i}/{len(todo)}] {qid} ({g['type']})")
        record = {"id": qid, "type": g["type"]}
        record["faithfulness"] = (
            score_one(
                lambda: faithfulness.score(
                    user_input=g["question"],
                    response=a["answer"],
                    retrieved_contexts=a["contexts"],
                )
            )
            if a["contexts"]
            else {"value": None, "error": "no contexts"}
        )
        record["reference_coverage"] = score_one(
            lambda: reference_coverage(fc, g["reference_answer"], a["answer"])
        )
        print(
            f"    faithfulness={record['faithfulness']['value']}  "
            f"reference_coverage={record['reference_coverage']['value']}"
        )

        done[qid] = record
        ordered = [done[q] for q in golden if q in done]
        OUT.write_text(
            "\n".join(json.dumps(r) for r in ordered) + "\n", encoding="utf-8"
        )

    print(f"\nSaved {len(done)} graded questions to {OUT}")
    summarise(done)


if __name__ == "__main__":
    main()
