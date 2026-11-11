from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./data/stock_assistant.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_task_always_eager: bool = True

    llm_provider: str = "mock"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    market_data_mode: str = "auto"
    sec_edgar_user_agent: str = "StockMarketAssistant contact@example.com"

    sandbox_mode: str = "local_restricted"
    sandbox_docker_image: str = "stock-assistant-sandbox:latest"
    sandbox_timeout_seconds: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
