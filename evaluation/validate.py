"""Check golden_set.jsonl against the rules in evaluation/README.md.

Usage: python -m evaluation.validate
"""

import json
from pathlib import Path
import sys

GOLDEN = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evaluation/golden_set.jsonl")
TYPES = {"sec", "news", "general", "unanswerable"}
ROUTES = {"sec", "news", "general"}
FIELDS = {
    "id",
    "type",
    "question",
    "expected_route",
    "reference_answer",
    "expected_chunk_ids",
    "evidence",
}

# Every chunk that really exists in the stored data: id -> text
chunk_text = {}
for path in Path("data/chunks").glob("*.jsonl"):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = json.loads(line)
            chunk_text[c["chunk_id"]] = c["text"]
known_ids = set(chunk_text)


def normalise(s: str) -> str:
    """Compare text ignoring case, curly vs straight quotes, and line breaks/spaces."""
    s = (
        s.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    return " ".join(s.lower().split())


problems, seen = [], set()
rows = []
for lineno, line in enumerate(GOLDEN.read_text(encoding="utf-8").splitlines(), start=1):
    if not line.strip():
        problems.append(f"line {lineno}: blank line (JSONL needs one object per line)")
        continue
    try:
        rows.append(json.loads(line))
    except json.JSONDecodeError as e:
        problems.append(f"line {lineno}: invalid JSON ({e.msg} at column {e.colno})")
for row in rows:
    qid = row.get("id", "?")
    missing = FIELDS - row.keys()
    if missing:
        problems.append(f"{qid}: missing fields {sorted(missing)}")
        continue
    if qid in seen:
        problems.append(f"{qid}: duplicate id")
    seen.add(qid)
    if row["type"] not in TYPES:
        problems.append(f"{qid}: unknown type {row['type']!r}")
    if row["expected_route"] not in ROUTES:
        problems.append(f"{qid}: invalid route {row['expected_route']!r}")
    if "TO_BE" in row["reference_answer"] or not row["reference_answer"].strip():
        problems.append(f"{qid}: reference answer is empty or a placeholder")
    ids = row["expected_chunk_ids"]
    if row["type"] in {"sec", "news"} and not ids:
        problems.append(f"{qid}: {row['type']} question has no expected chunks")
    if row["type"] in {"general", "unanswerable"} and ids:
        problems.append(f"{qid}: {row['type']} question should have no expected chunks")
    for cid in ids:
        if cid not in known_ids:
            problems.append(f"{qid}: chunk {cid} does not exist in data/chunks")
    if ids and all(cid in known_ids for cid in ids):
        combined = normalise(" ".join(chunk_text[cid] for cid in ids))
        if normalise(row["evidence"]) not in combined:
            problems.append(
                f"{qid}: evidence quote not found verbatim in its expected chunks"
            )
prefix = (
    rows[0]["id"].rstrip("0123456789") if rows else "q"
)  # "q" for the golden set, "h" for the holdout
expected = {f"{prefix}{i:02d}" for i in range(1, len(rows) + 1)}
gaps = sorted(expected - seen)
if gaps:
    problems.append(
        f"missing ids in the {prefix}01..{prefix}{len(rows):02d} sequence: {gaps}"
    )
counts = {t: sum(r.get("type") == t for r in rows) for t in sorted(TYPES)}
print(f"{len(rows)} questions  {counts}")
print("\n".join(problems) if problems else "All checks passed.")
