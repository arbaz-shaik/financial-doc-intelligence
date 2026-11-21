"""Run every golden-set question through the full agent and save the results.

Resumable: questions already answered successfully are skipped, so a crash or a
rate limit never costs the same LLM calls twice. Failed answers are retried on the
next run. Each source's FULL text is stored, because faithfulness grading checks
claims against the context.

Usage: python -m evaluation.run_agent
"""

import json
import time
from pathlib import Path

from evaluation.paths import GOLDEN_FILE, RUN_DIR

from src.agent.graph import app as agent

GOLDEN = GOLDEN_FILE
OUT = RUN_DIR / "answers.jsonl"
PAUSE_SECONDS = (
    6  # between questions: about 3 LLM calls each, kept under free-tier rate limits
)

# Full chunk text by ID, so stored contexts are complete
chunk_text = {}
for path in Path("data/chunks").glob("*.jsonl"):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = json.loads(line)
            chunk_text[c["chunk_id"]] = c["text"]


def load_done() -> dict[str, dict]:
    """Previously saved results that succeeded (no llm_failure), by question id."""
    done = {}
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if "llm_failure" not in r["risk_flags"] and not r.get("error"):
                    done[r["id"]] = r
    return done


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    golden = [
        json.loads(line)
        for line in GOLDEN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    done = load_done()
    todo = [q for q in golden if q["id"] not in done]
    print(f"{len(done)} already answered, {len(todo)} to run")

    for i, q in enumerate(todo, start=1):
        start = time.perf_counter()
        result = agent.invoke(
            input={
                "question": q["question"],
                "chat_history": [],
                "top_k": 5,
                "source_filter": None,
                "date_from": None,
            }
        )
        latency = time.perf_counter() - start

        source_ids = [s["chunk_id"] for s in result.get("sources", [])]
        record = {
            "id": q["id"],
            "type": q["type"],
            "question": q["question"],
            "route": result.get("route", "default"),
            "answer": result.get("answer", ""),
            "source_ids": source_ids,
            "contexts": [chunk_text.get(cid, "") for cid in source_ids],
            "risk_flags": result.get("risk_flags") or [],
            "error": result.get("error"),
            "latency_s": round(latency, 2),
        }
        done[q["id"]] = record

        # Rewrite the whole file each time: one line per question, latest result wins
        ordered = [done[g["id"]] for g in golden if g["id"] in done]
        OUT.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in ordered) + "\n",
            encoding="utf-8",
        )

        status = (
            "FAILED"
            if record["error"] or "llm_failure" in record["risk_flags"]
            else "ok"
        )
        print(
            f"[{i}/{len(todo)}] {q['id']} route={record['route']} {latency:.1f}s {status}"
        )
        if record["error"] and "per day" in record["error"]:
            print(
                "\nDaily token limit reached: stopping. Re-run later; only unfinished questions will run."
            )
            break
        time.sleep(PAUSE_SECONDS)

    print(f"\nSaved {len(done)} results to {OUT}")


if __name__ == "__main__":
    main()
