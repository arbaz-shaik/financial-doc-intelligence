"""Hybrid retrieval: vector search + BM25 keyword search, fused with Reciprocal Rank Fusion.

Vector search captures meaning but can bury a rare, decisive phrase under common words;
BM25 weights terms by rarity (IDF), so it catches exact rare terms. RRF combines the two
rankings by rank alone, because their scores are on incompatible scales.
"""

import re

from rank_bm25 import BM25Okapi

from src.config import settings
from src.rag.vector_store import VectorStore


def tokenize(text: str) -> list[str]:
    """Lowercase words and numbers; punctuation is dropped."""
    return re.findall(r"[a-z0-9]+", text.lower())


def rrf_fuse(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score(id) = sum over rankings of 1 / (k + rank)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


class HybridSearcher:
    def __init__(self, store: VectorStore):
        self.store = store
        self._bm25 = None
        self._ids: list[str] = []
        self._docs: list[str] = []
        self._metas: list[dict] = []

    def _ensure_index(self) -> None:
        """Build the BM25 index from ChromaDB's own contents; rebuild if the chunk count changed."""
        if self._bm25 is not None and len(self._ids) == self.store.count():
            return
        data = self.store.collection.get(include=["documents", "metadatas"])
        self._ids, self._docs, self._metas = data["ids"], data["documents"], data["metadatas"]
        self._bm25 = BM25Okapi([tokenize(d) for d in self._docs])

    def _bm25_ranking(self, question: str, pool: int, source_filter, company_filter, date_from) -> list[str]:
        scores = self._bm25.get_scores(tokenize(question))
        allowed = [
            i for i, m in enumerate(self._metas)
            if (not source_filter or m.get("source") == source_filter)
            and (not company_filter or m.get("company") == company_filter)
            and (not date_from or (m.get("date") or "") >= date_from)
            and scores[i] > 0
        ]
        allowed.sort(key=lambda i: scores[i], reverse=True)
        return [self._ids[i] for i in allowed[:pool]]

    def search(
        self,
        question: str,
        query_embedding: list[float],
        top_k: int = 5,
        source_filter: str | None = None,
        company_filter: str | None = None,
        date_from: str | None = None,
    ) -> list[dict]:
        self._ensure_index()
        pool = max(settings.hybrid_pool, top_k)
        vector_hits = self.store.search(
            query_embedding, top_k=pool, source_filter=source_filter,
            company_filter=company_filter, date_from=date_from,
        )
        bm25_ids = self._bm25_ranking(question, pool, source_filter, company_filter, date_from)

        fused = rrf_fuse([[h["id"] for h in vector_hits], bm25_ids], k=settings.rrf_k)[:top_k]

        by_id = {h["id"]: h for h in vector_hits}
        index = {cid: i for i, cid in enumerate(self._ids)}
        results = []
        for chunk_id, score in fused:
            if chunk_id in by_id:
                hit = dict(by_id[chunk_id])
            else:  # found by BM25 only: no vector distance exists
                i = index[chunk_id]
                hit = {"id": chunk_id, "text": self._docs[i], "metadata": self._metas[i], "distance": None}
            hit["rrf_score"] = score
            results.append(hit)
        return results