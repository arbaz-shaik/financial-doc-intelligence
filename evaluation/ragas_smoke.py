r"""LLM-judged scores (RAGAS) for saved agent answers. Runs in .venv-eval.

Metrics:
- faithfulness: are the answer's claims supported by the retrieved contexts?
- factual recall (FactualCorrectness, mode="recall"): does the answer contain
  the reference answer's key facts? (Precision is covered by faithfulness, and
  our references are deliberately minimal, so F1 would penalise correct extra detail.)

Unanswerable questions are skipped: abstention is scored deterministically.
Resumable: finished questions are skipped; each result is saved immediately.

Usage:
    .venv-eval\\Scripts\\python.exe -m evaluation.grade_ragas            # all questions
    .venv-eval\\Scripts\\python.exe -m evaluation.grade_ragas q01 q02    # only these
"""

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import FactualCorrectness, Faithfulness

JUDGE = "qwen/qwen3.8-27b"  # different family from the generator (openai/gpt-oss-120b)
GOLDEN = Path("evaluation/golden_set.jsonl")
ANSWERS = Path("evaluation/results/answers.jsonl")
OUT = Path("evaluation/results/ragas_scores.jsonl")


def load(path: Path) -> dict[str, dict]:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["id"]: r for r in rows}


def with_retry(fn, attempts: int = 8, wait: int = 65):
    """Free tier: ~1000 output tokens/minute. On a rate limit, wait for the budget to refill."""
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:
            if "rate_limit" not in str(e) and "429" not in str(e):
                raise
            print(f"    rate limited ({i}/{attempts}), waiting {wait}s")
            time.sleep(wait)
    raise RuntimeError("still rate limited after retries")


def score_one(metric_fn) -> dict:
    """Run one metric; record the value, or the error, without stopping the whole run."""
    try:
        return {"value": with_retry(metric_fn).value, "error": None}
    except Exception as e:
        return {"value": None, "error": type(e).__name__ + ": " + str(e)[:200]}


def main() -> None:
    load_dotenv()
    llm = llm_factory(
        JUDGE,
        provider="openai",
        client=OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1"),
        max_tokens=950,  # just under the 1000 output-tokens/minute limit, so requests are admitted
    )
    faithfulness = Faithfulness(llm=llm)
    recall = FactualCorrectness(llm=llm, mode="recall")

    golden, answers = load(GOLDEN), load(ANSWERS)
    done = load(OUT) if OUT.exists() else {}
    only = set(sys.argv[1:])

    todo = [q for q in golden
            if golden[q]["type"] != "unanswerable"
            and (not only or q in only)
            and not (q in done and all(done[q][m]["error"] is None for m in ("faithfulness", "factual_recall")))]
    print(f"{len(todo)} questions to grade with {JUDGE}")

    for i, qid in enumerate(todo, start=1):
        g, a = golden[qid], answers[qid]
        print(f"[{i}/{len(todo)}] {qid} ({g['type']})")
        record = {"id": qid, "type": g["type"]}
        record["faithfulness"] = (
            score_one(lambda: faithfulness.score(
                user_input=g["question"], response=a["answer"], retrieved_contexts=a["contexts"]))
            if a["contexts"] else {"value": None, "error": "no contexts"}
        )
        record["factual_recall"] = score_one(
            lambda: recall.score(response=a["answer"], reference=g["reference_answer"]))
        print(f"    faithfulness={record['faithfulness']['value']}  "
              f"factual_recall={record['factual_recall']['value']}")

        done[qid] = record
        ordered = [done[q] for q in golden if q in done]
        OUT.write_text("\n".join(json.dumps(r) for r in ordered) + "\n", encoding="utf-8")

    print(f"\nSaved {len(done)} graded questions to {OUT}")


if __name__ == "__main__":
    main()