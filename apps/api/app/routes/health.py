from __future__ import annotations

from fastapi import APIRouter

from apps.api.app.config import get_settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.app_env,
        "llm_provider": settings.llm_provider,
        "market_data_mode": settings.market_data_mode,
        "sandbox_mode": settings.sandbox_mode,
    }
