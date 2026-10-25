FROM python:3.13-slim

WORKDIR /app

# CPU-only torch (no CUDA). Version must match requirements.txt
RUN pip install --no-cache-dir torch==2.11.0 --index-url https://download.pytorch.org/whl/cpu

# Copy dependencies first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the embedding model into the image (no runtime download).
# Name must match the Embedder default in src/rag/embedder.py
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Application code. pipeline/ is needed because startup indexing uses ChunkStore.
COPY src/ src/
COPY pipeline/ pipeline/

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]