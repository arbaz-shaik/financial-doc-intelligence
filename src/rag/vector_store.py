
import chromadb
from src.config import settings



class VectorStore:
    def __init__(
        self,
        chroma_mode: str = settings.chroma_mode,
        chroma_host: str = settings.chroma_host,
        chroma_port: int = settings.chroma_port,
        chroma_path: str = settings.chroma_path,
    ):
        if chroma_mode == "local":
            self.client = chromadb.PersistentClient(
                path=chroma_path
            )
        elif chroma_mode == "http":
            self.client = chromadb.HttpClient(
                host=chroma_host,
                port=chroma_port,
            )
        else:
            raise ValueError(
                f"Unsupported ChromaDB mode: {chroma_mode}"
            )

        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )



    def add_chunk(self, chunks: list[dict], embeddings: list[list[float]] ) -> int:
        ids =[]
        metadatas=[]
        documents=[]

        for chunk in chunks :
            ids.append (chunk["chunk_id"])
            documents.append (chunk["text"])
            metadatas.append(
                 {
        "source": chunk.get("source"),
        "company": chunk.get("company"),
        "doc_type": chunk.get("doc_type"),
        "date": chunk.get("date"),
        "section": chunk.get("section") or "unknown"
    
            })
        self.collection.upsert(
            ids= ids,
            documents = documents,
            metadatas= metadatas,
            embeddings = embeddings
        )

        return len(chunks)
    
    def search(
        self,
        query_embedding: list[float],
        top_k: int | None = 5,
        source_filter: str | None = None,
        company_filter: str | None = None,
        date_from: str | None = None
    ) -> list[dict]:

        where_clause = {}

        conditions = []

        if source_filter:
            conditions.append({"source": source_filter})

        if company_filter:
            conditions.append({"company": company_filter})

        # Build where_clause based on count
        if len(conditions) == 0:
            where_clause = None
        elif len(conditions) == 1:
            where_clause = conditions[0]
        else:
            where_clause = {"$and": conditions}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_clause if where_clause else None
        )

        output = []


        for i in range(len(results["ids"][0])):
            output.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]
            })

        
        if date_from:
            output = [r for r in output if r["metadata"]["date"] >= date_from]


        return output
            
    def count(self) -> int:
        return self.collection.count()


