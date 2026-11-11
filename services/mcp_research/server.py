from __future__ import annotations

import os
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

from services.mcp_research.provider import SecEdgarAndYFinanceProvider

mcp = MCPServer("company-research-mcp")


def _get_provider() -> SecEdgarAndYFinanceProvider:
    return SecEdgarAndYFinanceProvider(mode=os.getenv("MARKET_DATA_MODE", "auto"))


@mcp.tool()
def get_company_profile(ticker: str) -> dict[str, Any]:
    """Fetch company overview, sector, CIK, and recent SEC 10-K/10-Q/8-K filings."""
    return _get_provider().get_company_profile(ticker).model_dump()


@mcp.tool()
def get_financial_statements(
    ticker: str,
    statement_type: Literal["income", "balance", "cashflow", "all"] = "all",
    period: Literal["annual", "quarterly"] = "annual",
) -> dict[str, Any]:
    """Fetch normalized income statement, balance sheet, and cash flow data."""
    return _get_provider().get_financial_statements(
        ticker=ticker,
        statement_type=statement_type,
        period=period,
    ).model_dump()


@mcp.tool()
def get_valuation_and_earnings(ticker: str) -> dict[str, Any]:
    """Fetch valuation multiples (P/E, EV/EBITDA, P/B), margins, ROE, and EPS history."""
    return _get_provider().get_valuation_and_earnings(ticker).model_dump()


if __name__ == "__main__":
    mcp.run()
