"""Deterministic scores from saved agent results: no LLM calls.

- routing accuracy (overall, per type, and which routes were confused)
- end-to-end hit@5: did the agent's final sources include an expected chunk?
- abstention: unanswerable questions should abstain; answerable ones shouldn't
- latency

Writes RUN_DIR/deterministic.json (metrics for logging) and prints a summary.

Usage: python -m evaluation.score_deterministic
"""

import json
import statistics
from collections import Counter
from pathlib import Path

from evaluation.paths import GOLDEN_FILE, RUN_DIR

ANSWERS = RUN_DIR / "answers.jsonl"
ABSTAIN_PHRASES = (
    "don't have enough information",
    "do not have enough information",
    "not enough information",
)


def load(path: Path) -> dict[str, dict]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {r["id"]: r for r in rows}


def abstained(answer: str) -> bool:
    text = answer.lower().replace("\u2019", "'")
    return any(p in text for p in ABSTAIN_PHRASES)


def compute(golden: dict[str, dict], answers: dict[str, dict]) -> dict:
    """All deterministic metrics, plus the details behind them."""
    ids = [q for q in golden if q in answers]
    correct = [q for q in ids if answers[q]["route"] == golden[q]["expected_route"]]
    with_chunks = [q for q in ids if golden[q]["expected_chunk_ids"]]
    hits = [
        q
        for q in with_chunks
        if set(answers[q]["source_ids"]) & set(golden[q]["expected_chunk_ids"])
    ]
    unans = [q for q in ids if golden[q]["type"] == "unanswerable"]
    answerable = [q for q in ids if golden[q]["type"] != "unanswerable"]
    lat = sorted(answers[q]["latency_s"] for q in ids)

    return {
        "n": len(ids),
        "metrics": {
            "routing_accuracy": len(correct) / len(ids),
            "e2e_hit_at_5": len(hits) / len(with_chunks) if with_chunks else 0.0,
            "abstention_rate_unanswerable": (
                sum(abstained(answers[q]["answer"]) for q in unans) / len(unans)
                if unans
                else 0.0
            ),
            "false_abstention_rate": (
                sum(abstained(answers[q]["answer"]) for q in answerable)
                / len(answerable)
                if answerable
                else 0.0
            ),
            "latency_median_s": statistics.median(lat),
            "latency_p95_s": lat[max(0, int(round(0.95 * len(lat))) - 1)],
        },
        "routing_by_type": {
            t: [
                sum(q in correct for q in ids if golden[q]["type"] == t),
                sum(1 for q in ids if golden[q]["type"] == t),
            ]
            for t in ("sec", "news", "general", "unanswerable")
        },
        "misroutes": [
            {
                "id": q,
                "expected": golden[q]["expected_route"],
                "actual": answers[q]["route"],
            }
            for q in ids
            if q not in correct
        ],
        "e2e_misses": [q for q in with_chunks if q not in hits],
        "false_abstentions": [q for q in answerable if abstained(answers[q]["answer"])],
    }


def main() -> None:
    golden, answers = load(GOLDEN_FILE), load(ANSWERS)
    failed = [
        q
        for q, a in answers.items()
        if a.get("error") or "llm_failure" in a.get("risk_flags", [])
    ]
    if failed:
        raise SystemExit(
            f"Incomplete run: {len(failed)} failed questions {failed}. Re-run run_agent to retry them."
        )
    missing = [q for q in golden if q not in answers]
    if missing:
        raise SystemExit(
            f"Incomplete run: {len(missing)} questions have no answer {missing}. Run run_agent first."
        )
    s = compute(golden, answers)
    m = s["metrics"]
    print(f"{s['n']} questions scored\n")

    print(f"Routing accuracy: {m['routing_accuracy']:.0%}")
    for t, (ok, total) in s["routing_by_type"].items():
        print(f"  {t:<13} {ok}/{total}")
    print("  Misroutes (expected -> actual):")
    for (exp, act), n in Counter(
        (x["expected"], x["actual"]) for x in s["misroutes"]
    ).most_common():
        qs = [
            x["id"]
            for x in s["misroutes"]
            if x["expected"] == exp and x["actual"] == act
        ]
        print(f"    {exp} -> {act}: {n}  {qs}")

    print(f"\nEnd-to-end hit@5: {m['e2e_hit_at_5']:.0%}")
    print(f"  Misses: {s['e2e_misses']}")
    print(f"\nAbstention on unanswerable: {m['abstention_rate_unanswerable']:.0%}")
    print(
        f"False abstention on answerable: {m['false_abstention_rate']:.0%}  {s['false_abstentions']}"
    )
    print(
        f"\nLatency: median {m['latency_median_s']:.1f}s, p95 {m['latency_p95_s']:.1f}s"
    )

    (RUN_DIR / "deterministic.json").write_text(
        json.dumps(s, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
