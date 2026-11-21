"""Deterministic retrieval check: does vector search find the expected chunks?

No router, no reranker, no LLM: free, instant and repeatable.
Each question is searched within its expected source (as if routing were perfect),
so routing mistakes can't show up as retrieval misses.

Writes RUN_DIR/retrieval.json (metrics for logging) and prints a summary.

Usage: python -m evaluation.retrieval_check
"""

import json

from evaluation.paths import GOLDEN_FILE, RUN_DIR
from src.rag.embedder import Embedder
from src.rag.vector_store import VectorStore

KS = (1, 3, 5, 10)


def first_hit_rank(retrieved: list[str], expected: set[str]) -> int | None:
    """1-based rank of the first expected chunk in the results, or None if absent."""
    for rank, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in expected:
            return rank
    return None


def main() -> None:
    rows = [
        json.loads(line)
        for line in GOLDEN_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows = [
        r for r in rows if r["expected_chunk_ids"]
    ]  # only sec/news questions have expected chunks

    embedder, store = Embedder(), VectorStore()
    results = []
    for r in rows:
        hits = store.search(
            embedder.embed(r["question"]),
            top_k=max(KS),
            source_filter=r["expected_route"],
        )
        retrieved = [h["id"] for h in hits]
        results.append((r, first_hit_rank(retrieved, set(r["expected_chunk_ids"]))))

    n = len(results)
    metrics = {
        f"retrieval_hit_at_{k}": sum(1 for _, rank in results if rank and rank <= k) / n
        for k in KS
    }
    metrics[f"retrieval_mrr_at_{max(KS)}"] = (
        sum(1 / rank for _, rank in results if rank) / n
    )

    print(f"Retrieval check: {n} questions (vector search only)\n")
    for k in KS:
        hit = metrics[f"retrieval_hit_at_{k}"]
        print(f"hit@{k:<3} {hit:6.0%}   ({round(hit * n)}/{n})")
    print(f"MRR@{max(KS)}  {metrics[f'retrieval_mrr_at_{max(KS)}']:6.2f}\n")

    misses = [
        {"id": r["id"], "rank": rank} for r, rank in results if not rank or rank > 5
    ]
    print("Not in the top 5:")
    for r, rank in results:
        if not rank or rank > 5:
            where = f"rank {rank}" if rank else "not in top 10"
            print(f"  {r['id']} [{r['type']}] {where}: {r['question'][:70]}")

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_DIR / "retrieval.json").write_text(
        json.dumps({"n": n, "metrics": metrics, "misses_top5": misses}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
