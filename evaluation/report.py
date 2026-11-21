"""Join golden set, agent answers and RAGAS scores into one per-question report.

Classifies each answerable question's outcome by pipeline stage:
  routing    -> wrong route (searched the wrong documents)
  retrieval  -> right route, but no expected chunk in the final sources
  abstained  -> the answer says it lacks information
  incomplete -> answered, but reference coverage < 1
  ok         -> answered with full reference coverage
Faithfulness is reported only for answers that actually answered: on abstentions
it is undefined (no factual claims) and the judge's values there are noise.

Usage: python -m evaluation.report
"""

import json
import statistics
from pathlib import Path

from evaluation.score_deterministic import abstained

GOLDEN = Path("evaluation/golden_set.jsonl")
ANSWERS = Path("evaluation/results/answers.jsonl")
RAGAS = Path("evaluation/results/ragas_scores.jsonl")


def load(path: Path) -> dict[str, dict]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {r["id"]: r for r in rows}


def stage(g: dict, a: dict, cov) -> str:
    if a["route"] != g["expected_route"]:
        return "routing"
    if g["expected_chunk_ids"] and not set(a["source_ids"]) & set(
        g["expected_chunk_ids"]
    ):
        return "retrieval"
    if abstained(a["answer"]):
        return "abstained"
    if cov is not None and cov < 1.0:
        return "incomplete"
    return "ok"


def main() -> None:
    golden, answers, ragas = load(GOLDEN), load(ANSWERS), load(RAGAS)
    rows = []
    for qid, g in golden.items():
        if g["type"] == "unanswerable":
            continue
        a, r = answers[qid], ragas.get(qid, {})
        cov = r.get("reference_coverage", {}).get("value")
        faith = r.get("faithfulness", {}).get("value")
        answered = not abstained(a["answer"])
        rows.append(
            {
                "id": qid,
                "type": g["type"],
                "route": a["route"],
                "expected": g["expected_route"],
                "stage": stage(g, a, cov),
                "faith": faith if answered else None,  # undefined on abstentions
                "cov": cov,
            }
        )

    print(
        f"{'id':<4} {'type':<8} {'route':<8} {'expected':<8} {'stage':<11} {'faith':>5} {'cov':>5}"
    )
    for x in rows:
        f = "-" if x["faith"] is None else f"{x['faith']:.2f}"
        c = "-" if x["cov"] is None else f"{x['cov']:.2f}"
        print(
            f"{x['id']:<4} {x['type']:<8} {x['route']:<8} {x['expected']:<8} {x['stage']:<11} {f:>5} {c:>5}"
        )

    print("\nOutcome by stage:")
    for s in ("routing", "retrieval", "abstained", "incomplete", "ok"):
        ids = [x["id"] for x in rows if x["stage"] == s]
        print(f"  {s:<11} {len(ids):>2}  {ids}")

    faiths = [x["faith"] for x in rows if x["faith"] is not None]
    covs = [x["cov"] for x in rows if x["cov"] is not None]
    print(
        f"\nFaithfulness (answered questions only): {statistics.mean(faiths):.2f}  (n={len(faiths)})"
    )
    print(
        f"Reference coverage (all answerable):     {statistics.mean(covs):.2f}  (n={len(covs)})"
    )

    worst = sorted(
        (x for x in rows if x["cov"] is not None),
        key=lambda x: (x["cov"], x["faith"] or 0),
    )[:5]
    print(
        "\nWorst 5 by reference coverage:", [f"{x['id']} ({x['stage']})" for x in worst]
    )


if __name__ == "__main__":
    main()
