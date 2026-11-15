r"""Show the claims and verdicts behind q01's factual recall score. Runs in .venv-eval."""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import FactualCorrectness

load_dotenv()
llm = llm_factory(
    "qwen/qwen3.8-27b",
    provider="openai",
    client=OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1"),
    max_tokens=950,
)
recall = FactualCorrectness(llm=llm, mode="recall")


def load(path: str) -> dict[str, dict]:
    return {r["id"]: r for r in map(json.loads, Path(path).read_text(encoding="utf-8").splitlines())}


ref = load("evaluation/golden_set.jsonl")["q01"]["reference_answer"]
ans = load("evaluation/results/answers.jsonl")["q01"]["answer"]

# Step 1: split the REFERENCE into claims
claims = asyncio.run(recall._decompose_claims(ref))
print("CLAIMS FROM REFERENCE:")
print(claims, "\n")

# Step 2: check each claim against the ANSWER
verdicts = asyncio.run(recall._verify_claims(claims, ans))
print("VERDICTS AGAINST THE ANSWER:")
print(verdicts)