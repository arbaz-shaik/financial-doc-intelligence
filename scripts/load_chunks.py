from  pipeline.store import ChunkStore
from src.rag.embedder import Embedder
from src.rag.vector_store import VectorStore

def test():
    chunkstore = ChunkStore("data/chunks")
    chunks =  chunkstore.load_all_chunks()

    print (f"total chunks {len(chunks)}")


    print(chunks[len(chunks) // 2]["text"][:200])
    print(chunks[len(chunks) // 2]["company"], chunks[len(chunks) // 2]["source"])
    print(chunks[-1]["text"][:200])
    print(chunks[-1]["company"], chunks[-1]["source"])
    print(chunks[0]["text"][:200])
    print(chunks[0]["company"], chunks[0]["source"])

    embed = Embedder()

 
    seen_ids = set()
    unique_chunks = []
    for chunk in chunks:
        if chunk["chunk_id"] not in seen_ids:
            seen_ids.add(chunk["chunk_id"])
            unique_chunks.append(chunk)


    

    chunk_list = [
        chunk["text"]
        for chunk in unique_chunks
]
    embed_chunks = embed.embed_batch(chunk_list)

    vector_store = VectorStore()
    
    vector_store.add_chunk(unique_chunks, embed_chunks)
    vector_store.count()
    print(f"Stored in ChromaDB: {vector_store.count()}")

    query ="What are Apple's risk factors?"
    embed_query = embed.embed(query)

    result = vector_store.search(embed_query, top_k=3, company_filter="AAPL")
    print (result)





if __name__ == "__main__":
    test()