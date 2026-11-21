r"""Log one evaluation run folder to MLflow. Runs in .venv-eval (the app env never sees MLflow).

Reads from the run folder (whatever exists):
    retrieval.json, deterministic.json   -> metrics
    ragas_scores.jsonl + answers.jsonl   -> faithfulness (answered only) and reference coverage
and uploads every file in the folder as artifacts, so each number traces back to raw results.

Usage:
    .venv-eval\Scripts\python.exe -m evaluation.log_run <run_dir> --name <run name> [--param key=value ...]
"""

import argparse
import hashlib
import json
import os
import statistics
import subprocess
from pathlib import Path

import mlflow

from evaluation.paths import GOLDEN_FILE
from evaluation.score_deterministic import abstained

EXPERIMENT = "findoc-rag-eval"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def jsonl(path: Path) -> dict[str, dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {r["id"]: r for r in rows}


def judge_metrics(run_dir: Path) -> dict[str, float]:
    """Means of the LLM-judged scores, if this run was judged."""
    scores_file, answers_file = run_dir / "ragas_scores.jsonl", run_dir / "answers.jsonl"
    if not (scores_file.exists() and answers_file.exists()):
        return {}
    scores, answers = jsonl(scores_file), jsonl(answers_file)
    faith = [r["faithfulness"]["value"] for q, r in scores.items()
             if r["faithfulness"]["value"] is not None and not abstained(answers[q]["answer"])]
    cov = [r["reference_coverage"]["value"] for r in scores.values() if r["reference_coverage"]["value"] is not None]
    out = {}
    if faith:
        out["faithfulness_answered"] = statistics.mean(faith)
    if cov:
        out["reference_coverage"] = statistics.mean(cov)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--param", action="append", default=[], help="key=value, repeatable")
    args = parser.parse_args()

    metrics: dict[str, float] = {}
    for name in ("retrieval.json", "deterministic.json"):
        f = args.run_dir / name
        if f.exists():
            metrics.update(json.loads(f.read_text(encoding="utf-8"))["metrics"])
    metrics.update(judge_metrics(args.run_dir))

    params = dict(p.split("=", 1) for p in args.param)
    params["golden_set_sha256"] = hashlib.sha256(GOLDEN_FILE.read_bytes()).hexdigest()[:12]

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5001"))
    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=args.name):
        mlflow.log_params(params)
        mlflow.log_metrics(metrics)
        mlflow.set_tags({
            "git_commit": git("rev-parse", "--short", "HEAD"),
            "git_dirty": str(bool(git("status", "--porcelain"))),
        })
        mlflow.log_artifacts(str(args.run_dir))

    print(f"Logged '{args.name}': {len(params)} params, {len(metrics)} metrics, artifacts from {args.run_dir}")
    for k, v in sorted(metrics.items()):
        print(f"  {k:<30} {v:.3f}")


if __name__ == "__main__":
    main()