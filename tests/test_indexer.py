from dataclasses import dataclass

from src.rag.indexer import build_index
from src.rag.vector_store import VectorStore


@dataclass
class IndexChunk:
    """Fake chunk with every field VectorStore.add_chunk() reads."""
    chunk_id: str
    text: str
    source: str = "sec"
    company: str = "ACME"
    doc_type: str = "10-K"
    date: str = "2025-01-01"
    section: str = "unknown"

class FakeEmbedder:
    """Stands in for the real Embedder: no model is loaded."""
    def embed_batch(self, texts):
        # One 384-number vector per text, whatever the batch size
        return [[1.0] * 384 for _ in texts]


def test_build_index_dedupes_and_indexes(s3_store, tmp_path):
    # Arrange: 3 chunks across 2 files; "a" appears in both -> 2 unique
    s3_store.save_chunks([IndexChunk("a", "first A"), IndexChunk("b", "B")], "file1")
    s3_store.save_chunks([IndexChunk("a", "second A")], "file2")
    vector_store = VectorStore(chroma_mode="local", chroma_path=str(tmp_path))

    # Act
    count = build_index(s3_store, FakeEmbedder(), vector_store)

    # Assert: what it claims, and what it actually stored
    assert count == 2
    assert vector_store.count() == 2