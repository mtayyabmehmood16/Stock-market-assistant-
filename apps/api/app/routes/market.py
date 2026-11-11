from __future__ import annotations

from fastapi import APIRouter, Query

from apps.api.app.config import get_settings
from services.mcp_market.provider import YFinanceMarketProvider
from services.mcp_research.provider import SecEdgarAndYFinanceProvider

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/{ticker}/chart")
def get_market_chart(
    ticker: str,
    period: str = Query(default="6mo"),
    interval: str = Query(default="1d"),
):
    settings = get_settings()
    provider = YFinanceMarketProvider(mode=settings.market_data_mode)
    quote = provider.get_quote(ticker.upper())
    tech = provider.get_technical_indicators(ticker.upper(), period=period, interval=interval)
    return {
        "quote": quote.model_dump(),
        "technical": tech.model_dump(),
    }


@router.get("/{ticker}/fundamentals")
def get_market_fundamentals(ticker: str):
    settings = get_settings()
    provider = SecEdgarAndYFinanceProvider(mode=settings.market_data_mode)
    t = ticker.upper()
    return {
        "profile": provider.get_company_profile(t).model_dump(),
        "valuation": provider.get_valuation_and_earnings(t).model_dump(),
        "statements": provider.get_financial_statements(t, statement_type="all", period="annual").model_dump(),
    }
