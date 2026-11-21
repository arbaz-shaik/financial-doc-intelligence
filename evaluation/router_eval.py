"""Router-only evaluation: call just the router for every question, several times.

About 30 small LLM calls per repeat (vs ~90 for a full agent run), so prompt variants
can be compared cheaply. Repeats measure the noise: an improvement only counts if it is
bigger than the spread between repeats of the same prompt.

Writes RUN_DIR/router.json. Prompt version comes from ROUTER_PROMPT_VERSION.

Usage: python -m evaluation.router_eval [--repeats 3] [--pause 2]
"""

import argparse
import json
import statistics
import time

from evaluation.paths import GOLDEN_FILE, RUN_DIR
from src.agent.nodes import router
from src.config import settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--pause", type=float, default=2.0, help="seconds between calls (rate limits)")
    args = parser.parse_args()

    golden = [json.loads(line) for line in GOLDEN_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"Router prompt {settings.router_prompt_version}: {len(golden)} questions x {args.repeats} repeats")

    runs = []
    for i in range(1, args.repeats + 1):
        routes = {}
        for q in golden:
            routes[q["id"]] = router({"question": q["question"]})["route"]
            time.sleep(args.pause)
        acc = sum(routes[q["id"]] == q["expected_route"] for q in golden) / len(golden)
        answerable = [q for q in golden if q["type"] != "unanswerable"]
        acc_ans = sum(routes[q["id"]] == q["expected_route"] for q in answerable) / len(answerable)
        runs.append({"accuracy": acc, "accuracy_answerable": acc_ans, "routes": routes})
        print(f"  repeat {i}: {acc:.0%}  (answerable only: {acc_ans:.0%})")

    accs = [r["accuracy"] for r in runs]
    unstable = [q["id"] for q in golden if len({r["routes"][q["id"]] for r in runs}) > 1]
    always_wrong = [q["id"] for q in golden if all(r["routes"][q["id"]] != q["expected_route"] for r in runs)]

    summary = {
        "prompt_version": settings.router_prompt_version,
        "repeats": args.repeats,
        "metrics": {
            "router_accuracy_mean": statistics.mean(accs),
            "router_accuracy_min": min(accs),
            "router_accuracy_max": max(accs),
            "router_accuracy_answerable_mean": statistics.mean(r["accuracy_answerable"] for r in runs),
        },
        "unstable": unstable,
        "always_wrong": always_wrong,
        "runs": runs,
    }
    print(f"\nmean {statistics.mean(accs):.0%}  (min {min(accs):.0%}, max {max(accs):.0%})")
    print(f"unstable (route changed between repeats): {unstable}")
    print(f"always wrong: {always_wrong}")

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_DIR / "router.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()