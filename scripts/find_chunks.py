"""Search the stored chunks by keyword, to find expected chunk IDs for the golden set.

Usage: python -m scripts.find_chunks supply shortages
Every word must appear in the chunk (case-insensitive).
"""

import json
import sys
from pathlib import Path

words = [w.lower() for w in sys.argv[1:]]
if not words:
    raise SystemExit("Usage: python -m scripts.find_chunks <word> [<word> ...]")

hits = 0
for path in sorted(Path("data/chunks").glob("*.jsonl")):
    for line in path.read_text(encoding="utf-8").splitlines():
        chunk = json.loads(line)
        text = chunk["text"]
        lower = text.lower()
        if all(w in lower for w in words):
            hits += 1
            pos = lower.find(words[0])
            snippet = text[max(0, pos - 80) : pos + 160].replace("\n", " ")
            print(f"{chunk['chunk_id']}  [{chunk['source']}]\n    ...{snippet}...\n")

print(f"{hits} matching chunk(s)")
