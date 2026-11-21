from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_NAME: str = "Financial Document Intelligence API"
    sec_user_agent: str = "DefaultUser/1.0 default@email.com"
    news_api_key: str | None = None
    groq_api_key: str
    model_name: str = "openai/gpt-oss-120b"

    chroma_mode: Literal["local", "http"] = "local"
    chroma_host : str = "localhost"
    chroma_port : int = 8001
    chroma_path : str = "./data/vectors"

    storage_mode: Literal["local", "s3"] = "local"
    chunks_dir: str = "./data/chunks"
    s3_bucket: str | None = None
    s3_prefix: str = "chunks"
    aws_region: str = "eu-north-1"
    index_on_startup: bool = False
    router_prompt_version: str = "v1"
    latest_filing_fiscal_year: int = 2025  # most recent annual report in the index
    retrieval_mode: str = "vector"  # "vector" or "hybrid" (vector + BM25, fused with RRF)
    hybrid_pool: int = 20           # candidates taken from each method before fusion
    rrf_k: int = 60                 # Reciprocal Rank Fusion damping constant

settings = Settings()
