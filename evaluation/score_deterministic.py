"""Deterministic scores from saved agent results: no LLM calls.

- routing accuracy (overall, per type, and which routes were confused)
- end-to-end hit@5: did the agent's final sources include an expected chunk?
- abstention: unanswerable questions should abstain; answerable ones shouldn't
- latency

Usage: python -m evaluation.score_deterministic
"""

import json
import statistics
from collections import Counter
from pathlib import Path

GOLDEN = Path("evaluation/golden_set.jsonl")
ANSWERS = Path("evaluation/results/answers.jsonl")
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


def main() -> None:
    golden, answers = load(GOLDEN), load(ANSWERS)
    ids = [qid for qid in golden if qid in answers]
    print(f"{len(ids)} questions scored\n")

    # Routing
    correct = [q for q in ids if answers[q]["route"] == golden[q]["expected_route"]]
    print(
        f"Routing accuracy: {len(correct) / len(ids):.0%} ({len(correct)}/{len(ids)})"
    )
    for t in ("sec", "news", "general", "unanswerable"):
        of_type = [q for q in ids if golden[q]["type"] == t]
        ok = [q for q in of_type if q in correct]
        print(f"  {t:<13} {len(ok)}/{len(of_type)}")
    confusions = Counter(
        (golden[q]["expected_route"], answers[q]["route"])
        for q in ids
        if q not in correct
    )
    print("  Misroutes (expected -> actual):")
    for (exp, act), n in confusions.most_common():
        qs = [
            q
            for q in ids
            if q not in correct
            and golden[q]["expected_route"] == exp
            and answers[q]["route"] == act
        ]
        print(f"    {exp} -> {act}: {n}  {qs}")

    # End-to-end retrieval: what the agent actually used (after routing + reranking)
    with_chunks = [q for q in ids if golden[q]["expected_chunk_ids"]]
    hits = [
        q
        for q in with_chunks
        if set(answers[q]["source_ids"]) & set(golden[q]["expected_chunk_ids"])
    ]
    print(
        f"\nEnd-to-end hit@5: {len(hits) / len(with_chunks):.0%} ({len(hits)}/{len(with_chunks)})"
    )
    print(f"  Misses: {[q for q in with_chunks if q not in hits]}")

    # Abstention
    unans = [q for q in ids if golden[q]["type"] == "unanswerable"]
    answerable = [q for q in ids if golden[q]["type"] != "unanswerable"]
    good = [q for q in unans if abstained(answers[q]["answer"])]
    false_abst = [q for q in answerable if abstained(answers[q]["answer"])]
    print(
        f"\nAbstention on unanswerable: {len(good)}/{len(unans)}  (missed: {[q for q in unans if q not in good]})"
    )
    print(
        f"False abstention on answerable: {len(false_abst)}/{len(answerable)}  {false_abst}"
    )

    # Latency
    lat = sorted(answers[q]["latency_s"] for q in ids)
    p95 = lat[max(0, int(round(0.95 * len(lat))) - 1)]
    print(f"\nLatency: median {statistics.median(lat):.1f}s, p95 {p95:.1f}s")


if __name__ == "__main__":
    main()
