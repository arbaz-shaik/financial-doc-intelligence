from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_NAME: str = "Financial Document Intelligence API"
    sec_user_agent: str = "DefaultUser/1.0 default@email.com"
    news_api_key: str
    groq_api_key: str 
    model_name: str = "openai/gpt-oss-120b"



settings = Settings()       