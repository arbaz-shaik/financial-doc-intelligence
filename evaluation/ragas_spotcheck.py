r"""Spot-check the judge: per-claim verdicts for raw vs formatting-stripped answers.
Runs in .venv-eval:
    .venv-eval\Scripts\python.exe -m evaluation.ragas_spotcheck q23 q24
"""

import asyncio
import json
import os
import re
import sys
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
    client=OpenAI(
        api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1"
    ),
    max_tokens=950,
)
fc = FactualCorrectness(llm=llm)


def clean(text: str) -> str:
    """Remove formatting that isn't content: citation markers, markdown bold, unusual hyphens."""
    text = re.sub(r"【[^】]*】", "", text)  # citation markers
    text = text.replace("**", "")  # markdown bold
    for ch in (
        "\u2011",
        "\u2010",
        "\u2012",
        "\u2013",
    ):  # non-breaking hyphen and dashes
        text = text.replace(ch, "-")
    return text.strip()


def load(path: str) -> dict[str, dict]:
    return {
        r["id"]: r
        for r in map(json.loads, Path(path).read_text(encoding="utf-8").splitlines())
    }


golden = load("evaluation/golden_set.jsonl")
answers = load("evaluation/results/answers.jsonl")

for qid in sys.argv[1:]:
    ref = golden[qid]["reference_answer"]
    claims = with_retry(lambda: asyncio.run(fc._decompose_claims(ref)))
    print(f"===== {qid} =====\nCLAIMS: {claims}")
    for label, ans in (
        ("RAW", answers[qid]["answer"]),
        ("CLEAN", clean(answers[qid]["answer"])),
    ):
        result = with_retry(lambda: asyncio.run(fc._verify_claims(claims, ans)))
        verdicts = [s.verdict for s in result.statements]
        print(f"\n{label} answer: {ans}")
        for s in result.statements:
            print(f"  [{s.verdict}] {s.statement}  --  {s.reason}")
        print(f"  coverage = {sum(verdicts) / len(verdicts):.2f}")
    print()
