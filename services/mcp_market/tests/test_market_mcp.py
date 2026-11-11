from __future__ import annotations

from services.mcp_market.provider import FixtureMarketProvider, YFinanceMarketProvider
from services.mcp_market.server import get_ohlcv, get_quote, get_technical_indicators


def test_fixture_market_provider_ohlcv_and_indicators():
    provider = FixtureMarketProvider()
    quote = provider.get_quote("AAPL")
    assert quote.ticker == "AAPL"
    assert quote.price > 0
    assert quote.citation.source

    tech = provider.get_technical_indicators("AAPL", period="6mo")
    assert len(tech.candles) == 126
    names = {s.name for s in tech.indicators}
    assert "SMA 20" in names
    assert "RSI 14" in names
    assert "MACD (12,26)" in names
    assert tech.summary["trend"] in {"bullish", "bearish", "mixed / consolidating"}


def test_yfinance_provider_in_fixture_mode_and_mcp_tools(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "fixture")
    provider = YFinanceMarketProvider(mode="fixture")
    ohlcv = provider.get_ohlcv("NVDA", period="3mo")
    assert ohlcv.ticker == "NVDA"
    assert len(ohlcv.candles) == 64

    # Verify MCP tool wrappers return serializable dicts
    q = get_quote("MSFT")
    assert q["ticker"] == "MSFT"
    o = get_ohlcv("MSFT", period="1mo")
    assert len(o["candles"]) > 10
    t = get_technical_indicators("MSFT", period="3mo")
    assert "summary" in t
