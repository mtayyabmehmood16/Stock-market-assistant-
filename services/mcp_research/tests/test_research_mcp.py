from __future__ import annotations

from services.mcp_research.provider import FixtureResearchProvider, SecEdgarAndYFinanceProvider
from services.mcp_research.server import (
    get_company_profile,
    get_financial_statements,
    get_valuation_and_earnings,
)


def test_fixture_research_provider():
    provider = FixtureResearchProvider()
    profile = provider.get_company_profile("AAPL")
    assert profile.ticker == "AAPL"
    assert profile.cik == "0000320193"
    assert len(profile.recent_filings) >= 2

    stmts = provider.get_financial_statements("MSFT", statement_type="income")
    assert "income" in stmts.statements
    assert "2024" in stmts.statements["income"]

    val = provider.get_valuation_and_earnings("NVDA")
    assert val.pe_trailing is not None
    assert len(val.earnings_history) == 4


def test_research_mcp_tool_wrappers(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "fixture")
    provider = SecEdgarAndYFinanceProvider(mode="fixture")
    assert provider.get_company_profile("AAPL").name == "Apple Inc."

    p = get_company_profile("AAPL")
    assert p["ticker"] == "AAPL"
    s = get_financial_statements("AAPL", statement_type="cashflow")
    assert "cashflow" in s["statements"]
    v = get_valuation_and_earnings("AAPL")
    assert v["citation"]["source"]
