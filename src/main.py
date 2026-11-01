import threading
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from src.agent.graph import app as build_agent
from src.agent.nodes import get_embedder, get_store
from src.config import settings
from src.logger import get_logger
from src.models import AnswerResponse, Company, CompanyResponse, QuestionRequest
from src.rag.indexer import build_chunk_store, build_index
from src.storage import CompanyStore

store = CompanyStore()
logger = get_logger(__name__)

# "ready" when startup indexing is off (the index already exists, e.g. laptop/Compose).
# Otherwise "building" until the background job finishes, then "ready" or "failed".
_index_status = "building" if settings.index_on_startup else "ready"


def _run_startup_index() -> None:
    """Build the vector index in a background thread.

    Uses the same lazy getters as the agent nodes, so the model is loaded once
    and /ask reads exactly what was indexed.
    """
    global _index_status
    try:
        count = build_index(build_chunk_store(), get_embedder(), get_store())
        logger.info(f"Startup indexing complete: {count} chunks")
        _index_status = "ready"
    except Exception as e:
        logger.error(f"Startup indexing failed: {e}")
        _index_status = "failed"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup. Indexing runs in a background thread, so the app
    # starts serving (and /health answers) immediately.
    if settings.index_on_startup:
        threading.Thread(target=_run_startup_index, daemon=True).start()
    yield


app = FastAPI(title=settings.API_NAME, lifespan=lifespan)


@app.get("/health")
async def root():
    logger.info("Health check requested")
    return {"status": "Healthy"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello, {name}!"}


@app.get("/companies")
async def get_companies():
    results = store.list_all()
    return {"results": results, "count": len(results)}


# Plain def (not async def): the agent call blocks for seconds, so FastAPI runs
# it in a worker thread and /health stays responsive.
@app.post("/companies/ask/")
def ask(request: QuestionRequest):
    if _index_status == "building":
        raise HTTPException(status_code=503, detail="Index is still building - try again shortly.")
    if _index_status == "failed":
        raise HTTPException(status_code=503, detail="Index build failed - check the logs.")

    result = build_agent.invoke(
        input={
            "question": request.question,
            "chat_history": request.chat_history or [],
            "top_k": request.top_k,
            "source_filter": request.source_filter,
            "date_from": request.date_from,
        }
    )

    return AnswerResponse(
        question=request.question,
        answer=result.get("answer", ""),
        sources=result.get("sources", []),
        risk_flags=result.get("risk_flags") or [],
        route=result.get("route", "default"),
    )


@app.post("/companies", response_model=CompanyResponse)
async def new_company(company: Company):
    store.add(company.ticker, company)
    return CompanyResponse(company=company, added_at=datetime.now(UTC).isoformat())


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    logger.error(f"An error occurred: {str(exc)}")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.get("/companies/search/")
async def search_companies(sector: str = None, name: str = None):
    if sector:
        results = store.search_by_sector(sector)
    elif name:
        results = store.search_by_name(name)
    else:
        results = []
    return {"results": results, "count": len(results)}


@app.get("/companies/{ticker}")
async def get_company(ticker: str):
    company = store.get(ticker)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company