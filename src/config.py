from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_NAME: str = "Financial Document Intelligence API"
    sec_user_agent: str = "DefaultUser/1.0 default@email.com"
    news_api_key: str
    groq_api_key: str 
    model_name: str = "openai/gpt-oss-120b"

    chroma_mode: Literal["local", "http"] = "local"
    chroma_host : str = "localhost"
    chroma_port : int = 8001
    chroma_path : str = "./data/vectors"


settings = Settings()       