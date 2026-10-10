from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    chunk_id: str
    source: str
    company: str
    doc_type: str
    date: str
    section: str | None
    chunk_index: int
    total_chunks: int


class Chunker:
    def __init__(self, chunk_size: int, chunk_overlap: int):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")

        if chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")

        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str, metadata: dict) -> list[Chunk]:
        if not text.strip():
            return []

        # Require a stable document identifier.
        doc_id = metadata["doc_id"]

        chunks = []
        start = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk_text = text[start:end]

            # Split at the last sentence boundary only if it is
            # reasonably far into the chunk.
            if end < len(text):
                last_period = chunk_text.rfind(".")

                if last_period >= self.chunk_size // 2:
                    end = start + last_period + 1
                    chunk_text = text[start:end]

            chunk_index = len(chunks)

            # Include the document ID to prevent cross-document
            # chunk ID collisions.
            chunk_id = (
                f"{metadata['company']}-"
                f"{metadata['doc_type']}-"
                f"{doc_id}-"
                f"chunk-{chunk_index:04d}"
            )

            chunks.append(
                Chunk(
                    text=chunk_text,
                    chunk_id=chunk_id,
                    source=metadata["source"],
                    company=metadata["company"],
                    doc_type=metadata["doc_type"],
                    date=metadata["date"],
                    section=metadata["section"],
                    chunk_index=chunk_index,
                    total_chunks=0,
                )
            )

            # Stop after processing the final chunk.
            if end == len(text):
                break

            # Ensure forward progress while preserving overlap.
            next_start = end - self.chunk_overlap
            start = max(next_start, start + 1)

        # Update total_chunks for every chunk.
        total = len(chunks)

        for chunk in chunks:
            chunk.total_chunks = total

        return chunks


if __name__ == "__main__":
    chunker = Chunker(chunk_size=512, chunk_overlap=50)

    with open(
        "data/processed/AAPL-10K-2025-09-27.txt",
        "r",
        encoding="utf-8",
    ) as f:
        text = f.read()

    metadata = {
        "doc_id": "0000320193-25-000079",
        "source": "sec",
        "company": "AAPL",
        "doc_type": "10-K",
        "date": "2025-09-27",
        "section": None,
    }

    chunks = chunker.chunk_text(text, metadata)

    print(f"Total chunks: {len(chunks)}")

    for chunk in chunks[100:103]:
        print(f"Chunk ID: {chunk.chunk_id}")
        print(f"Chunk index: {chunk.chunk_index}")
        print(chunk.text[:200])
        print("---")