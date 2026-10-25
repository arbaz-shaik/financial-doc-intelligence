import boto3

from pipeline.store import ChunkStore
from src.config import settings
from src.rag.embedder import Embedder
from src.rag.vector_store import VectorStore

BATCH_SIZE = 128


def build_chunk_store() -> ChunkStore:
    if settings.storage_mode == "s3":
        if not settings.s3_bucket:
            raise ValueError("S3_BUCKET must be set when STORAGE_MODE=s3")
        client = boto3.client("s3", region_name=settings.aws_region)  # SCP: eu-north-1 only
        return ChunkStore(bucket=settings.s3_bucket, prefix=settings.s3_prefix, s3_client=client)
    return ChunkStore(settings.chunks_dir)


def main() -> None:
    store = build_chunk_store()
    chunks = store.load_all_chunks()
    print(f"Loaded {len(chunks)} chunks ({settings.storage_mode} mode)")
    if not chunks:
        raise SystemExit("No chunks loaded, nothing to index. Check bucket and prefix.")

    unique = list({c["chunk_id"]: c for c in chunks}.values())  # safety net, last wins

    embedder = Embedder()
    vector_store = VectorStore()
    for i in range(0, len(unique), BATCH_SIZE):
        batch = unique[i:i + BATCH_SIZE]
        vectors = embedder.embed_batch([c["text"] for c in batch])
        vector_store.add_chunk(batch, vectors)
        print(f"Indexed {min(i + BATCH_SIZE, len(unique))}/{len(unique)}")

    print(f"Stored in ChromaDB: {vector_store.count()}")

    hits = vector_store.search(
        embedder.embed("What are Apple's risk factors?"), top_k=3, company_filter="AAPL"
    )
    for h in hits:
        print(h["metadata"].get("source"), h["metadata"].get("date"), h["text"][:100])


if __name__ == "__main__":
    main()
