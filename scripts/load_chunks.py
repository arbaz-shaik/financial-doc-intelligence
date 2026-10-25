"""Index chunks into ChromaDB by hand.

All the real work lives in src/rag/indexer.py (shared with the API's startup
indexing). This script only wires up the pieces, reports, and runs a smoke search.
"""

from src.config import settings
from src.rag.embedder import Embedder
from src.rag.indexer import build_chunk_store, build_index
from src.rag.vector_store import VectorStore


def main() -> None:
    chunk_store = build_chunk_store()
    embedder = Embedder()
    vector_store = VectorStore()

    try:
        indexed = build_index(chunk_store, embedder, vector_store)
    except ValueError as e:
        raise SystemExit(str(e))

    print(f"Indexed {indexed} chunks ({settings.storage_mode} mode)")
    print(f"Stored in ChromaDB: {vector_store.count()}")

    # Smoke test: a known question should return Apple 10-K chunks.
    hits = vector_store.search(
        embedder.embed("What are Apple's risk factors?"),
        top_k=3,
        company_filter="AAPL",
    )
    for h in hits:
        print(h["metadata"].get("source"), h["metadata"].get("date"), h["text"][:100])


if __name__ == "__main__":
    main()