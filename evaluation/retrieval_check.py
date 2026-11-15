"""Deterministic retrieval check: does vector search find the expected chunks?

No router, no reranker, no LLM: free, instant and repeatable.
Each question is searched within its expected source (as if routing were perfect),
so routing mistakes can't show up as retrieval misses.

Usage: python -m evaluation.retrieval_check
"""

import json
from pathlib import Path

from src.rag.embedder import Embedder
from src.rag.vector_store import VectorStore

GOLDEN = Path("evaluation/golden_set.jsonl")
KS = (1, 3, 5, 10)


def first_hit_rank(retrieved: list[str], expected: set[str]) -> int | None:
    """1-based rank of the first expected chunk in the results, or None if absent."""
    for rank, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in expected:
            return rank
    return None


def main() -> None:
    rows = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [r for r in rows if r["expected_chunk_ids"]]  # only sec/news questions have expected chunks

    embedder, store = Embedder(), VectorStore()
    results = []
    for r in rows:
        hits = store.search(  # <-
            embedder.embed(r["question"]),  # <-
            top_k=max(KS),
            source_filter=r["expected_route"],
        )
        retrieved = [h["id"] for h in hits]
        results.append((r, first_hit_rank(retrieved, set(r["expected_chunk_ids"]))))

    n = len(results)
    print(f"Retrieval check: {n} questions (vector search only)\n")
    for k in KS:
        hit = sum(1 for _, rank in results if rank and rank <= k)
        print(f"hit@{k:<3} {hit / n:6.0%}   ({hit}/{n})")
    mrr = sum(1 / rank for _, rank in results if rank) / n
    print(f"MRR@{max(KS)}  {mrr:6.2f}\n")

    print("Not in the top 5:")
    for r, rank in results:
        if not rank or rank > 5:
            where = f"rank {rank}" if rank else "not in top 10"
            print(f"  {r['id']} [{r['type']}] {where}: {r['question'][:70]}")


if __name__ == "__main__":
    main()