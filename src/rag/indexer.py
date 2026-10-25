"""Build the vector index from stored chunks.

Shared by scripts/load_chunks.py (run by hand) and the API (startup indexing),
so the load -> deduplicate -> embed -> store logic exists in exactly one place.
"""

import boto3

from pipeline.store import ChunkStore
from src.config import settings
from src.logger import get_logger
from src.rag.embedder import Embedder
from src.rag.vector_store import VectorStore

logger = get_logger(__name__)

DEFAULT_BATCH_SIZE = 128


def build_chunk_store() -> ChunkStore:
    """Return a ChunkStore for the configured storage mode (local folder or S3)."""
    if settings.storage_mode == "s3":
        if not settings.s3_bucket:
            raise ValueError("S3_BUCKET must be set when STORAGE_MODE=s3")
        # Region is explicit: the account's SCP only allows eu-north-1, and boto3
        # would otherwise take the region from the profile or environment.
        client = boto3.client("s3", region_name=settings.aws_region)
        return ChunkStore(
            bucket=settings.s3_bucket,
            prefix=settings.s3_prefix,
            s3_client=client,
        )
    return ChunkStore(settings.chunks_dir)


def deduplicate(chunks: list[dict]) -> list[dict]:
    """Keep one chunk per chunk_id. If an ID appears more than once, the last one wins
    (a dict key assigned twice keeps its latest value)."""
    return list({c["chunk_id"]: c for c in chunks}.values())


def build_index(
    chunk_store: ChunkStore,
    embedder: Embedder,
    vector_store: VectorStore,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> int:
    """Load all chunks, deduplicate, embed in batches and upsert into the vector store.

    The three collaborators are passed in rather than created here, so tests can
    supply a moto-backed ChunkStore, a fake embedder and a throwaway vector store.

    Returns the number of unique chunks indexed.
    Raises ValueError if no chunks are found.
    """
    chunks = chunk_store.load_all_chunks()
    if not chunks:
        raise ValueError(
            "No chunks loaded - check STORAGE_MODE, S3_BUCKET and S3_PREFIX "
            "(or CHUNKS_DIR in local mode)."
        )

    unique = deduplicate(chunks)
    logger.info(
        f"Indexing {len(unique)} chunks "
        f"({len(chunks) - len(unique)} duplicates dropped)"
    )

    # Batches keep memory bounded and are much faster than one chunk at a time.
    for start in range(0, len(unique), batch_size):
        batch = unique[start:start + batch_size]  # slicing past the end just stops early
        vectors = embedder.embed_batch([c["text"] for c in batch])
        vector_store.add_chunk(batch, vectors)  # upsert: safe to re-run
        logger.info(f"Indexed {min(start + batch_size, len(unique))}/{len(unique)}")

    return len(unique)
