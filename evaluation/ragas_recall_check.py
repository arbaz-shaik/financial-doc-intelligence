r"""Known-answer tests for reference coverage: the fraction of reference claims found in the answer.
Runs in .venv-eval:
    .venv-eval\Scripts\python.exe -m evaluation.ragas_recall_check
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import FactualCorrectness

from evaluation.grade_ragas import with_retry

load_dotenv()
llm = llm_factory(
    "qwen/qwen3.8-27b",
    provider="openai",
    client=OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1"),
    max_tokens=950,
)
fc = FactualCorrectness(llm=llm)


def reference_coverage(reference: str, answer: str) -> float:
    """Split the REFERENCE into atomic claims, check each against the ANSWER, return the share found.

    Uses a private RAGAS step (pinned ragas==0.4.4) because the library's own 'recall'
    mixes the answer's claims into its numerator (see FactualCorrectness.ascore).
    """
    verdicts = asyncio.run(fc._decompose_and_verify_claims(reference, answer))
    return round(float(verdicts.mean()), 2) if len(verdicts) else 0.0


def load(path: str) -> dict[str, dict]:
    return {r["id"]: r for r in map(json.loads, Path(path).read_text(encoding="utf-8").splitlines())}


ref = load("evaluation/golden_set.jsonl")["q01"]["reference_answer"]
ans = load("evaluation/results/answers.jsonl")["q01"]["answer"]

tests = {
    "A. reference as answer (expect 1.0)": ref,
    "B. answer + reference appended (expect 1.0)": ans + "\n\n" + ref,
    "C. unrelated text (expect 0.0)": "Apple sells iPhones and Macs.",
    "D. the real q01 answer (expect ~0.5: 2 of 4 facts)": ans,
}
for name, answer in tests.items():
    print(name, "->", with_retry(lambda: reference_coverage(ref, answer)))