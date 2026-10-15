![CI](https://github.com/arbaz-shaik/financial-doc-intelligence/actions/workflows/ci.yml/badge.svg)

# Financial Document Intelligence


An end-to-end AI platform that ingests SEC filings and financial news, answers natural language questions with cited sources, flags risk signals, and routes queries intelligently using a LangGraph agent.

Built in 6 phases over 40 days as a portfolio project targeting Applied AI / ML Engineer / MLOps roles in the UK.

---

## Architecture

```
User Question
     │
     ▼
  FastAPI (/ask)
     │
     ▼
  LangGraph Agent
     │
  ┌──▼──────────────┐
  │  Router Node     │  LLM classifies: sec / news / general
  └──┬───────────────┘
     │ conditional edge
     ▼
  ┌──────────────────┐
  │  Retrieve Node   │  Embeds query, ChromaDB search, Reranker
  └──┬───────────────┘
     ▼
  ┌──────────────────┐
  │  Generate Node   │  Builds prompt with context + chat history, LLM answer
  └──┬───────────────┘
     ▼
  ┌──────────────────┐
  │  Risk Flagger    │  Scans answer for compliance keywords
  └──┬───────────────┘
     ▼
  JSON Response: answer, sources, risk_flags, route
```

---

## Phases

### Phase 1 - REST API (Days 1-6)
**What it does:** FastAPI backend with 6 endpoints for company data management, health checks, and search.
**Tech:** FastAPI, Pydantic, pytest, structured JSON logging, Makefile.
**Hard part:** Understanding how Pydantic validates request data automatically and how to structure a Python project properly with config, logging, and error handling from the start.

### Phase 2 - Data Pipeline (Days 7-14)
**What it does:** Fetches SEC 10-K filings via EDGAR API and news articles via NewsAPI, parses HTML with BeautifulSoup, chunks text with sentence boundary detection and overlap, stores chunks as JSONL with full metadata.
**Tech:** httpx, BeautifulSoup4, custom Chunker with configurable size/overlap, JSONL storage.
**Hard part:** SEC filings contain messy XBRL/XML markup mixed with HTML. Getting clean text required iterative parsing and filtering. Chunking strategy (size, overlap, sentence boundaries) directly affects RAG quality downstream.

### Phase 3 - RAG Q&A (Days 15-22)
**What it does:** Embeds questions using sentence-transformers, searches ChromaDB for relevant chunks, reranks results using LLM-based relevance scoring, generates cited answers grounded in retrieved context.
**Tech:** sentence-transformers (all-MiniLM-L6-v2), ChromaDB, Groq (openai/gpt-oss-120b), LLM-based reranker.
**Hard part:** Implementing complex metadata filtering with `$and` conditions in ChromaDB, and building the reranker. Some chunks appear similar on the surface but provide no useful context for the actual question.

### Phase 4 - LangGraph Agent (Days 23-28)
**What it does:** Replaces the simple RAG pipeline with an intelligent agent that routes queries to the right data source, retrieves and reranks chunks, generates cited answers, flags financial risk signals, and maintains conversation memory across turns.
**Tech:** LangGraph (StateGraph, conditional edges), keyword-based risk detection.
**Key features:**
- **Query routing** - LLM classifies questions as sec/news/general and applies source-specific filtering
- **Risk flagging** - Scans answers for compliance keywords (litigation, material weakness, fraud, sanctions, etc.)
- **Conversation memory** - Chat history travels through state so follow-up questions like "What about their revenue?" resolve correctly
- **Error handling** - Try/except on every node with structured logging and graceful fallbacks

### Phase 5 - Cloud Deployment (Days 29-36)
*Coming next: Docker, AWS, Terraform, GitHub Actions, Prometheus + Grafana*

### Phase 6 - Evaluation and Polish (Days 37-40)
*Coming next: RAGAS evaluation, MLflow experiment tracking, React frontend*

---

## Example Response

**Question:** "What are Apple's key risk factors?"

**Route:** `sec` | **Risk flags:** `["litigation", "material adverse effect"]`

```json
{
  "answer": "Based on the provided context, Apple's key risk factors include: 1. Supply shortages and price increases [AAPL-10-K-chunk-0128] 2. Design and manufacturing defects [AAPL-10-K-chunk-0202] 3. Risks related to personal data collection and transfer [AAPL-10-K-chunk-0140] 4. Dependence on third-party software developers [AAPL-10-K-chunk-0176] 5. Litigation or government investigations [AAPL-10-K-chunk-0083]",
  "sources": [
    {"chunk_id": "AAPL-10-K-chunk-0128", "relevance": 0.64, "source": "sec"},
    {"chunk_id": "AAPL-10-K-chunk-0202", "relevance": 0.64, "source": "sec"},
    {"chunk_id": "AAPL-10-K-chunk-0140", "relevance": 0.59, "source": "sec"}
  ],
  "risk_flags": ["litigation", "material adverse effect"],
  "route": "sec"
}
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/companies` | Add a company |
| GET | `/companies` | List all companies |
| GET | `/companies/search/` | Search by sector or name |
| GET | `/companies/{ticker}` | Get company by ticker |
| POST | `/companies/ask/` | Ask a question (agent-powered) |

---

## How to Run

```bash
git clone https://github.com/your-username/financial-doc-intelligence.git
cd financial-doc-intelligence
python -m venv .venv
make test      # Windows
pip install -r requirements.txt
```

```bash
# Ingest data
make ingest

# Run API
make run

# Run tests
make test
```

---

## Tech Stack

Python 3.11 · FastAPI · Pydantic · LangGraph · ChromaDB · sentence-transformers · Groq (openai/gpt-oss-120b) · BeautifulSoup4 · httpx · pytest · ruff