from __future__ import annotations

import os
from typing import Any

from mcp.server.mcpserver import MCPServer

from services.mcp_market.provider import YFinanceMarketProvider

mcp = MCPServer("market-data-mcp")


def _get_provider() -> YFinanceMarketProvider:
    return YFinanceMarketProvider(mode=os.getenv("MARKET_DATA_MODE", "auto"))


@mcp.tool()
def get_quote(ticker: str) -> dict[str, Any]:
    """Fetch latest quote, change, volume, and market cap for a stock ticker."""
    return _get_provider().get_quote(ticker).model_dump()


@mcp.tool()
def get_ohlcv(ticker: str, period: str = "6mo", interval: str = "1d") -> dict[str, Any]:
    """Fetch historical OHLCV candlestick and volume bars for a ticker."""
    return _get_provider().get_ohlcv(ticker, period=period, interval=interval).model_dump()


@mcp.tool()
def get_technical_indicators(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
    indicators: list[str] | None = None,
) -> dict[str, Any]:
    """Compute technical indicators (SMA, EMA, Bollinger Bands, RSI, MACD) and trend signals."""
    return _get_provider().get_technical_indicators(
        ticker=ticker,
        period=period,
        interval=interval,
        indicators=indicators,
    ).model_dump()


if __name__ == "__main__":
    mcp.run()
