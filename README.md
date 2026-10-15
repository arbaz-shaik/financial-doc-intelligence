![CI](https://github.com/arbaz-shaik/financial-doc-intelligence/actions/workflows/ci.yml/badge.svg)

# Financial Document Intelligence

An end-to-end AI system that ingests SEC 10-K filings and financial news, answers natural-language questions with cited sources, flags risk signals, and routes each query through a LangGraph agent. It runs as a two-service Docker Compose stack (FastAPI + ChromaDB) and every pull request is checked by GitHub Actions CI.

Built as a portfolio project over a phased 40-day plan, targeting Applied AI / ML Engineer / MLOps roles in the UK.

---

## Highlights

| What | Result |
|------|--------|
| **Docker image size** | 8.98 GB → **2.49 GB** on disk (3.05 GB → **528 MB** compressed) by switching to CPU-only PyTorch. Diagnosed with `docker history` and `pip list` inside the container: Linux PyTorch from PyPI pulled 15 `nvidia-*` CUDA packages the app never uses. |
| **Offline-capable container** | The embedding model is baked into the image at build time. Verified with `HF_HUB_OFFLINE=1`: the API starts and embeds with no network access to Hugging Face. |
| **Persistent vector store** | ChromaDB runs as its own container with a named volume. Verified by `docker compose down` → `up`: 665 chunks still present, `/ask` still returns sources. |
| **Startup resilience** | Models and clients are created lazily, on first use. The API starts and `/health` returns 200 even when ChromaDB is unreachable; only `/ask` is affected. |
| **CI quality gate** | Lint, tests and a Docker build run on every pull request (~3.5 min). Branch protection blocks merging into `main` until all three pass. |
| **LLM provider change** | When Groq retired the original model, structured logs pinpointed `model_not_found` across all agent nodes. The model name now lives in config, so the next migration is a one-line `.env` change. |

---

## Architecture

### Request flow (LangGraph agent)

```
POST /companies/ask/
        │
        ▼
 ┌──────────────┐
 │    Router    │  LLM classifies the question: sec / news / general
 └──────┬───────┘  (invalid output falls back to "general")
        ▼
 ┌──────────────┐
 │   Retrieve   │  embed question → ChromaDB search (source filter by route)
 └──────┬───────┘  → LLM reranker keeps the most relevant chunks
        ▼
 ┌──────────────┐
 │   Generate   │  prompt = context + chat history → cited answer
 └──────┬───────┘
        │ conditional edge
        ├── llm_failure ──────────────► END   (flag preserved for the caller)
        ▼
 ┌──────────────┐
 │ Risk Flagger │  scans the answer for compliance keywords
 └──────┬───────┘
        ▼
 JSON response: answer · sources · risk_flags · route
```

### Runtime (Docker Compose)

```
 ┌──────────────── docker compose network ────────────────┐
 │                                                        │
 │   ┌──────────────┐   http://chromadb:8000   ┌────────┐ │
 │   │  api         │ ───────────────────────► │chromadb│ │
 │   │  FastAPI +   │                          │ 1.5.5  │ │
 │   │  LangGraph   │                          └───┬────┘ │
 │   │  (model baked│                              │      │
 │   │   into image)│                     named volume:   │
 │   └──────┬───────┘                     chromadb_data   │
 │          │                             mounted at /data│
 └──────────┼─────────────────────────────────────────────┘
            │ localhost:8000                 localhost:8001
        your browser                    laptop scripts (loading)
```

The API waits for ChromaDB to pass a healthcheck (`depends_on: condition: service_healthy`) before starting. The healthcheck uses bash's `/dev/tcp`, because the ChromaDB image ships without curl, wget or Python.

---

## Project status

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | REST API: FastAPI, Pydantic, pytest, structured JSON logging | ✅ |
| 2 | Data pipeline: SEC EDGAR + NewsAPI ingestion, HTML parsing, chunking, JSONL storage | ✅ |
| 3 | RAG: sentence-transformers embeddings, ChromaDB, LLM reranker, cited answers | ✅ |
| 4 | LangGraph agent: routing, risk flagging, conversation memory, error handling | ✅ |
| 5 | Deployment | 🟡 In progress |
|   | ↳ Docker image (CPU torch, baked model) | ✅ |
|   | ↳ Docker Compose stack with persistent ChromaDB | ✅ |
|   | ↳ GitHub Actions CI + branch protection | ✅ |
|   | ↳ AWS (ECR, ECS), Terraform, Prometheus + Grafana | ⏳ |
| 6 | Evaluation (RAGAS, golden test set), MLflow, React frontend | ⏳ |

---

## Quick start

### Option A: Docker Compose (recommended)

Requires Docker Desktop.

```bash
git clone https://github.com/arbaz-shaik/financial-doc-intelligence.git
cd financial-doc-intelligence

# 1. Configure secrets: copy the template, then add your keys
cp .env.example .env

# 2. Start the stack (API + ChromaDB) in the background
make docker-up
```

The API is now at http://localhost:8000 (Swagger UI at `/docs`), and ChromaDB at http://localhost:8001.

**Load documents into the ChromaDB container.** This runs from your laptop, against the exposed port:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt

python -m pipeline.run                          # fetch + parse + chunk → data/chunks/
CHROMA_MODE=http python -m scripts.load_chunks  # embed + store in the ChromaDB container
```

On Windows PowerShell, set the variable first: `$env:CHROMA_MODE="http"; python -m scripts.load_chunks`.

> `pipeline.run` appends to the JSONL files in `data/chunks/`. Empty that folder before re-running it, to avoid duplicate chunks.

Stop the stack with `make docker-down`. Data persists in the `chromadb_data` volume. **Do not add `-v`**, which deletes the volume.

### Option B: Local development (no Docker)

```bash
pip install -r requirements-dev.txt
python -m pipeline.run
python -m scripts.load_chunks     # local mode: writes to ./data/vectors
make run                          # uvicorn on http://localhost:8000
make test                         # pytest
```

---

## Configuration

All settings are read by Pydantic `Settings` (`src/config.py`) from environment variables or `.env`. Secrets have **no defaults**, so the app fails fast at startup if they are missing.

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GROQ_API_KEY` | ✅ | — | LLM provider key |
| `NEWS_API_KEY` | ✅ | — | NewsAPI key for news ingestion |
| `SEC_USER_AGENT` | | placeholder | Required by SEC EDGAR (`Name/1.0 email`) |
| `MODEL_NAME` | | `openai/gpt-oss-120b` | Groq model ID |
| `CHROMA_MODE` | | `local` | `local` (embedded `PersistentClient`) or `http` (ChromaDB server). Validated: any other value fails at startup |
| `CHROMA_HOST` | | `localhost` | Server host in `http` mode (`chromadb` inside Compose) |
| `CHROMA_PORT` | | `8001` | Server port in `http` mode (`8000` inside Compose) |
| `CHROMA_PATH` | | `./data/vectors` | Storage path in `local` mode |

> When passing `.env` to `docker run --env-file`, use plain `NAME=value` lines with **no quotes and no spaces** around `=`. Docker keeps them literally.

---

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (independent of ChromaDB and the LLM) |
| POST | `/companies` | Add a company |
| GET | `/companies` | List all companies |
| GET | `/companies/search/` | Search by sector or name |
| GET | `/companies/{ticker}` | Get a company by ticker |
| POST | `/companies/ask/` | Ask a question (agent-powered) |

### Example

Request:

```json
{
  "question": "What are Apple's key risk factors in their latest 10-K filing?",
  "top_k": 5,
  "chat_history": []
}
```

Response (abridged):

```json
{
  "route": "sec",
  "answer": "Apple's 2025 Form 10-K lists risk factors that could materially adversely affect its business... Supply shortages and price increases [AAPL-10-K-0000320193-25-000079-chunk-0149] ... frequent product and service transitions [AAPL-10-K-0000320193-25-000079-chunk-0134] ... privacy and security changes [AAPL-10-K-0000320193-25-000079-chunk-0241] ...",
  "sources": [
    {"chunk_id": "AAPL-10-K-0000320193-25-000079-chunk-0094", "relevance": 0.72},
    {"chunk_id": "AAPL-10-K-0000320193-25-000079-chunk-0134", "relevance": 0.66},
    {"chunk_id": "AAPL-10-K-0000320193-25-000079-chunk-0241", "relevance": 0.65}
  ],
  "risk_flags": ["material adverse effect"]
}
```

For follow-up questions, send previous turns in `chat_history` as `{"question": ..., "answer": ...}` objects. The API is stateless: the client keeps the history.

---

## CI/CD

`.github/workflows/ci.yml` runs on every pull request to `main` and every push to `main`:

| Job | What it does | Notes |
|-----|--------------|-------|
| `lint` | `ruff check .` | Installs only ruff, not the full dependency set |
| `test` | `pytest` with dummy API keys | CPU-only torch installed first; pip cache keyed on both requirements files; 60 s per-test timeout |
| `build` | `docker build` | Runs only after `lint` and `test` pass |

A repository ruleset requires all three checks before anything merges into `main`. This was verified by pushing a deliberately broken test to an open PR: the PR went red and merging was blocked until it was fixed.

**Dependencies are split:** `requirements.txt` holds runtime packages only (what the Docker image installs), and `requirements-dev.txt` includes it with `-r` and adds pytest, pytest-timeout and ruff.

---

## Testing

- **11 tests**: API endpoints, chunker behaviour, HTML parsing, and the SEC client, with HTTP mocked via `unittest.mock.patch`.
- Tests pass with **dummy API keys**, so no test calls Groq or NewsAPI.
- `pytest.ini` limits collection to `tests/`.

**Known gap:** the agent nodes (router, retrieve, generate, risk flagger) are not yet unit-tested. The lazy getters in `src/agent/nodes.py` make this possible by patching `get_llm()` / `get_store()` with fakes.

---

## Engineering notes

Problems hit during the build, and what fixed them:

- **Chunker never terminated** when the final chunk was shorter than `chunk_size` (`start` reset to `end - overlap` forever). Fixed by stopping after the final chunk and forcing `start` to advance by at least one character. This also explained a hanging test.
- **88 news articles collapsed into 1 stored chunk**, because chunk IDs restarted at 0 per document (`AAPL-news-chunk-0000` every time). IDs now include a required `doc_id`: the SEC accession number for filings, and a short MD5 of the URL for news. A rebuild gave 665 chunks with 665 unique IDs.
- **`depends_on` alone doesn't wait for readiness:** it waits for a container to *start*, not for its service to accept connections. That was combined with import-time client creation, so a slow database could take down the whole API. Fixed with a healthcheck gate plus lazy initialisation.
- **PowerShell `>` wrote `requirements.txt` as UTF-16**, which was caught by inspecting the first bytes with `Format-Hex` and converted to UTF-8.

---

## Known limitations / roadmap

- Parser leaves some XBRL markup in early chunks, and financial tables are flattened into unstructured text
- No section extraction yet (Risk Factors, MD&A)
- Risk flagger uses exact-phrase matching on the answer, so it misses word variants and trusts unsupported claims
- Citation format varies between model runs; citations should be parsed and validated
- Retrieval ignores chat history (follow-ups need query rewriting before retrieval)
- No company filter at query time (needed before ingesting multiple companies)
- News ingestion queries by ticker, which returns some irrelevant results
- If the LLM is unavailable, the reranker failure also empties retrieval results
- Planned: AWS deployment (ECR + ECS), Terraform, Prometheus + Grafana, RAGAS evaluation, MLflow, React frontend

---

## Project structure

```
financial-doc-intelligence/
├── .github/workflows/ci.yml   # lint → test → docker build
├── Dockerfile                 # python:3.13-slim, CPU torch, baked embedding model
├── docker-compose.yml         # api + chromadb, named volume, healthcheck
├── Makefile                   # run, test, docker-up, docker-down
├── pytest.ini
├── requirements.txt           # runtime dependencies
├── requirements-dev.txt       # -r requirements.txt + pytest, ruff
├── src/
│   ├── config.py              # Pydantic Settings (all configuration)
│   ├── logger.py              # structured JSON logging
│   ├── main.py                # FastAPI app
│   ├── models.py              # request/response schemas
│   ├── rag/                   # embedder, vector_store, llm, reranker, prompts
│   └── agent/                 # state, nodes (lazy getters), graph
├── pipeline/                  # sec_client, news_client, parser, chunker, store, run
├── scripts/                   # load_chunks and experiment scripts
└── tests/                     # test_api.py, test_pipeline.py
```

---

## Tech stack

Python 3.13 · FastAPI · Pydantic · LangGraph · ChromaDB · sentence-transformers (all-MiniLM-L6-v2) · Groq (openai/gpt-oss-120b) · BeautifulSoup4 · httpx · pytest · ruff · Docker · Docker Compose · GitHub Actions