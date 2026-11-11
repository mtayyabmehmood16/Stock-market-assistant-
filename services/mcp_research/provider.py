from __future__ import annotations

import os
import time
from typing import Any, Literal, Protocol

import httpx
import yfinance as yf
from pydantic import BaseModel, Field

from packages.shared_schemas.schemas import Citation, utc_now_iso


class CompanyProfile(BaseModel):
    ticker: str
    name: str
    sector: str
    industry: str
    cik: str | None = None
    exchange: str = "NASDAQ"
    description: str
    employees: int | None = None
    website: str | None = None
    recent_filings: list[dict[str, str]] = Field(default_factory=list)
    citation: Citation


class FinancialStatements(BaseModel):
    ticker: str
    statement_type: Literal["income", "balance", "cashflow", "all"]
    period: Literal["annual", "quarterly"]
    currency: str = "USD"
    statements: dict[str, dict[str, dict[str, float | None]]] = Field(default_factory=dict)
    citation: Citation


class ValuationAndEarnings(BaseModel):
    ticker: str
    market_cap: float | None = None
    pe_trailing: float | None = None
    pe_forward: float | None = None
    ev_to_ebitda: float | None = None
    price_to_book: float | None = None
    profit_margin_pct: float | None = None
    operating_margin_pct: float | None = None
    roe_pct: float | None = None
    revenue_growth_pct: float | None = None
    eps_trailing: float | None = None
    eps_forward: float | None = None
    earnings_history: list[dict[str, Any]] = Field(default_factory=list)
    citation: Citation


class CompanyResearchProvider(Protocol):
    def get_company_profile(self, ticker: str) -> CompanyProfile: ...
    def get_financial_statements(
        self,
        ticker: str,
        statement_type: Literal["income", "balance", "cashflow", "all"] = "all",
        period: Literal["annual", "quarterly"] = "annual",
    ) -> FinancialStatements: ...
    def get_valuation_and_earnings(self, ticker: str) -> ValuationAndEarnings: ...


_COMPANY_FIXTURES: dict[str, dict[str, Any]] = {
    "AAPL": {
        "name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "cik": "0000320193",
        "exchange": "NASDAQ",
        "description": "Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and services worldwide.",
        "employees": 161000,
        "website": "https://www.apple.com",
        "mcap": 3.25e12,
        "pe_trailing": 32.4,
        "pe_forward": 28.9,
        "ev_to_ebitda": 24.5,
        "price_to_book": 45.2,
        "profit_margin_pct": 25.3,
        "operating_margin_pct": 31.1,
        "roe_pct": 147.0,
        "revenue_growth_pct": 6.1,
        "eps_trailing": 6.57,
        "eps_forward": 7.36,
        "income": {
            "2023": {"Total Revenue": 383.29e9, "Gross Profit": 169.15e9, "Operating Income": 114.30e9, "Net Income": 97.00e9},
            "2024": {"Total Revenue": 391.04e9, "Gross Profit": 180.68e9, "Operating Income": 123.22e9, "Net Income": 93.74e9},
            "2025": {"Total Revenue": 414.89e9, "Gross Profit": 193.75e9, "Operating Income": 131.52e9, "Net Income": 105.10e9},
        },
        "balance": {
            "2023": {"Total Assets": 352.58e9, "Total Liabilities": 290.44e9, "Stockholders Equity": 62.15e9, "Cash & Equivalents": 29.97e9, "Total Debt": 111.09e9},
            "2024": {"Total Assets": 364.98e9, "Total Liabilities": 308.03e9, "Stockholders Equity": 56.95e9, "Cash & Equivalents": 29.94e9, "Total Debt": 106.63e9},
            "2025": {"Total Assets": 374.20e9, "Total Liabilities": 302.10e9, "Stockholders Equity": 72.10e9, "Cash & Equivalents": 35.10e9, "Total Debt": 101.40e9},
        },
        "cashflow": {
            "2023": {"Operating Cash Flow": 110.54e9, "Capital Expenditure": -10.96e9, "Free Cash Flow": 99.58e9},
            "2024": {"Operating Cash Flow": 118.25e9, "Capital Expenditure": -9.45e9, "Free Cash Flow": 108.81e9},
            "2025": {"Operating Cash Flow": 125.40e9, "Capital Expenditure": -10.20e9, "Free Cash Flow": 115.20e9},
        },
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "sector": "Technology",
        "industry": "Software - Infrastructure",
        "cik": "0000789019",
        "exchange": "NASDAQ",
        "description": "Microsoft Corporation develops and supports software, cloud infrastructure (Azure), productivity tools, and AI platforms globally.",
        "employees": 228000,
        "website": "https://www.microsoft.com",
        "mcap": 3.10e12,
        "pe_trailing": 34.8,
        "pe_forward": 30.2,
        "ev_to_ebitda": 23.1,
        "price_to_book": 11.4,
        "profit_margin_pct": 35.6,
        "operating_margin_pct": 44.6,
        "roe_pct": 36.2,
        "revenue_growth_pct": 15.7,
        "eps_trailing": 12.14,
        "eps_forward": 13.85,
        "income": {
            "2023": {"Total Revenue": 211.92e9, "Gross Profit": 146.05e9, "Operating Income": 88.52e9, "Net Income": 72.36e9},
            "2024": {"Total Revenue": 245.12e9, "Gross Profit": 171.01e9, "Operating Income": 109.43e9, "Net Income": 88.14e9},
            "2025": {"Total Revenue": 281.70e9, "Gross Profit": 195.80e9, "Operating Income": 125.60e9, "Net Income": 100.30e9},
        },
        "balance": {
            "2023": {"Total Assets": 411.98e9, "Total Liabilities": 205.75e9, "Stockholders Equity": 206.22e9, "Cash & Equivalents": 34.70e9, "Total Debt": 59.96e9},
            "2024": {"Total Assets": 512.16e9, "Total Liabilities": 243.69e9, "Stockholders Equity": 268.48e9, "Cash & Equivalents": 18.32e9, "Total Debt": 67.13e9},
            "2025": {"Total Assets": 548.40e9, "Total Liabilities": 246.20e9, "Stockholders Equity": 302.20e9, "Cash & Equivalents": 24.50e9, "Total Debt": 62.00e9},
        },
        "cashflow": {
            "2023": {"Operating Cash Flow": 87.58e9, "Capital Expenditure": -28.11e9, "Free Cash Flow": 59.48e9},
            "2024": {"Operating Cash Flow": 118.55e9, "Capital Expenditure": -44.48e9, "Free Cash Flow": 74.07e9},
            "2025": {"Operating Cash Flow": 134.20e9, "Capital Expenditure": -52.10e9, "Free Cash Flow": 82.10e9},
        },
    },
    "NVDA": {
        "name": "NVIDIA Corporation",
        "sector": "Technology",
        "industry": "Semiconductors",
        "cik": "0001045810",
        "exchange": "NASDAQ",
        "description": "NVIDIA Corporation provides accelerated computing GPUs, networking, and AI software stacks for data centers, gaming, and autonomous systems.",
        "employees": 32000,
        "website": "https://www.nvidia.com",
        "mcap": 3.05e12,
        "pe_trailing": 48.2,
        "pe_forward": 33.6,
        "ev_to_ebitda": 38.4,
        "price_to_book": 46.5,
        "profit_margin_pct": 55.0,
        "operating_margin_pct": 62.1,
        "roe_pct": 115.0,
        "revenue_growth_pct": 78.4,
        "eps_trailing": 2.57,
        "eps_forward": 3.69,
        "income": {
            "2023": {"Total Revenue": 26.97e9, "Gross Profit": 15.36e9, "Operating Income": 4.22e9, "Net Income": 4.37e9},
            "2024": {"Total Revenue": 60.92e9, "Gross Profit": 44.30e9, "Operating Income": 32.97e9, "Net Income": 29.76e9},
            "2025": {"Total Revenue": 130.50e9, "Gross Profit": 97.80e9, "Operating Income": 81.40e9, "Net Income": 72.88e9},
        },
        "balance": {
            "2023": {"Total Assets": 41.18e9, "Total Liabilities": 19.08e9, "Stockholders Equity": 22.10e9, "Cash & Equivalents": 3.39e9, "Total Debt": 10.95e9},
            "2024": {"Total Assets": 65.73e9, "Total Liabilities": 22.75e9, "Stockholders Equity": 42.98e9, "Cash & Equivalents": 7.28e9, "Total Debt": 9.71e9},
            "2025": {"Total Assets": 111.60e9, "Total Liabilities": 32.30e9, "Stockholders Equity": 79.30e9, "Cash & Equivalents": 14.20e9, "Total Debt": 8.46e9},
        },
        "cashflow": {
            "2023": {"Operating Cash Flow": 5.64e9, "Capital Expenditure": -1.83e9, "Free Cash Flow": 3.81e9},
            "2024": {"Operating Cash Flow": 28.09e9, "Capital Expenditure": -1.07e9, "Free Cash Flow": 27.02e9},
            "2025": {"Operating Cash Flow": 64.10e9, "Capital Expenditure": -3.20e9, "Free Cash Flow": 60.90e9},
        },
    },
}


class FixtureResearchProvider:
    """Deterministic fundamental research provider for offline dev, tests, and fallback."""

    def _entry(self, ticker: str) -> dict[str, Any]:
        t = ticker.upper()
        if t in _COMPANY_FIXTURES:
            return _COMPANY_FIXTURES[t]
        scale = 1.0 + (sum(ord(c) for c in t) % 5) * 0.35
        return {
            "name": f"{t} Holdings Corp.",
            "sector": "Industrials",
            "industry": "Diversified Operations",
            "cik": "0000000000",
            "exchange": "NYSE",
            "description": f"Synthetic benchmark company profile for {t} (offline fixture mode).",
            "employees": 25000,
            "website": f"https://example.com/{t.lower()}",
            "mcap": 4.2e10 * scale,
            "pe_trailing": round(21.5 * scale, 1),
            "pe_forward": round(18.8 * scale, 1),
            "ev_to_ebitda": round(14.2 * scale, 1),
            "price_to_book": round(4.5 * scale, 1),
            "profit_margin_pct": 14.5,
            "operating_margin_pct": 19.2,
            "roe_pct": 18.4,
            "revenue_growth_pct": 8.5,
            "eps_trailing": 5.12,
            "eps_forward": 5.85,
            "income": {
                "2023": {"Total Revenue": 18.0e9 * scale, "Gross Profit": 7.9e9 * scale, "Operating Income": 3.3e9 * scale, "Net Income": 2.4e9 * scale},
                "2024": {"Total Revenue": 19.6e9 * scale, "Gross Profit": 8.7e9 * scale, "Operating Income": 3.7e9 * scale, "Net Income": 2.8e9 * scale},
                "2025": {"Total Revenue": 21.3e9 * scale, "Gross Profit": 9.6e9 * scale, "Operating Income": 4.1e9 * scale, "Net Income": 3.1e9 * scale},
            },
            "balance": {
                "2023": {"Total Assets": 28.0e9 * scale, "Total Liabilities": 15.0e9 * scale, "Stockholders Equity": 13.0e9 * scale, "Cash & Equivalents": 3.2e9 * scale, "Total Debt": 6.4e9 * scale},
                "2024": {"Total Assets": 30.5e9 * scale, "Total Liabilities": 16.0e9 * scale, "Stockholders Equity": 14.5e9 * scale, "Cash & Equivalents": 3.9e9 * scale, "Total Debt": 6.0e9 * scale},
                "2025": {"Total Assets": 33.1e9 * scale, "Total Liabilities": 16.6e9 * scale, "Stockholders Equity": 16.5e9 * scale, "Cash & Equivalents": 4.6e9 * scale, "Total Debt": 5.5e9 * scale},
            },
            "cashflow": {
                "2023": {"Operating Cash Flow": 3.2e9 * scale, "Capital Expenditure": -0.7e9 * scale, "Free Cash Flow": 2.5e9 * scale},
                "2024": {"Operating Cash Flow": 3.7e9 * scale, "Capital Expenditure": -0.8e9 * scale, "Free Cash Flow": 2.9e9 * scale},
                "2025": {"Operating Cash Flow": 4.2e9 * scale, "Capital Expenditure": -0.9e9 * scale, "Free Cash Flow": 3.3e9 * scale},
            },
        }

    def get_company_profile(self, ticker: str) -> CompanyProfile:
        t = ticker.upper()
        d = self._entry(t)
        return CompanyProfile(
            ticker=t,
            name=d["name"],
            sector=d["sector"],
            industry=d["industry"],
            cik=d["cik"],
            exchange=d["exchange"],
            description=d["description"],
            employees=d["employees"],
            website=d["website"],
            recent_filings=[
                {"form": "10-K", "filingDate": "2025-11-01", "accessionNumber": "0000320193-25-000106"},
                {"form": "10-Q", "filingDate": "2026-08-01", "accessionNumber": "0000320193-26-000071"},
            ],
            citation=Citation(
                source="SEC EDGAR / Company Research Fixture",
                label=f"{t} company profile & filings",
                retrieved_at=utc_now_iso(),
            ),
        )

    def get_financial_statements(
        self,
        ticker: str,
        statement_type: Literal["income", "balance", "cashflow", "all"] = "all",
        period: Literal["annual", "quarterly"] = "annual",
    ) -> FinancialStatements:
        t = ticker.upper()
        d = self._entry(t)
        keys = ["income", "balance", "cashflow"] if statement_type == "all" else [statement_type]
        statements = {k: d[k] for k in keys}
        return FinancialStatements(
            ticker=t,
            statement_type=statement_type,
            period=period,
            statements=statements,
            citation=Citation(
                source="SEC EDGAR XBRL / Research Fixture",
                label=f"{t} {statement_type} statements ({period})",
                retrieved_at=utc_now_iso(),
            ),
        )

    def get_valuation_and_earnings(self, ticker: str) -> ValuationAndEarnings:
        t = ticker.upper()
        d = self._entry(t)
        eps_t = d["eps_trailing"]
        return ValuationAndEarnings(
            ticker=t,
            market_cap=d["mcap"],
            pe_trailing=d["pe_trailing"],
            pe_forward=d["pe_forward"],
            ev_to_ebitda=d["ev_to_ebitda"],
            price_to_book=d["price_to_book"],
            profit_margin_pct=d["profit_margin_pct"],
            operating_margin_pct=d["operating_margin_pct"],
            roe_pct=d["roe_pct"],
            revenue_growth_pct=d["revenue_growth_pct"],
            eps_trailing=eps_t,
            eps_forward=d["eps_forward"],
            earnings_history=[
                {"quarter": "Q1", "eps_estimate": round(eps_t * 0.22, 2), "eps_actual": round(eps_t * 0.24, 2), "surprise_pct": 9.1},
                {"quarter": "Q2", "eps_estimate": round(eps_t * 0.24, 2), "eps_actual": round(eps_t * 0.25, 2), "surprise_pct": 4.2},
                {"quarter": "Q3", "eps_estimate": round(eps_t * 0.25, 2), "eps_actual": round(eps_t * 0.26, 2), "surprise_pct": 4.0},
                {"quarter": "Q4", "eps_estimate": round(eps_t * 0.27, 2), "eps_actual": round(eps_t * 0.28, 2), "surprise_pct": 3.7},
            ],
            citation=Citation(
                source="Company Valuation & Earnings Fixture",
                label=f"{t} valuation & EPS metrics",
                retrieved_at=utc_now_iso(),
            ),
        )


class SecEdgarAndYFinanceProvider:
    """Fetches SEC EDGAR filings metadata + Yahoo Finance fundamentals, with fixture fallback."""

    def __init__(self, mode: str = "auto", cache_ttl_seconds: int = 300) -> None:
        self.mode = mode
        self.cache_ttl_seconds = cache_ttl_seconds
        self.user_agent = os.getenv("SEC_EDGAR_USER_AGENT", "StockMarketAssistant contact@example.com")
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cik_map: dict[str, str] | None = None
        self._fallback = FixtureResearchProvider()

    def _get_cached(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, val = entry
        if time.time() - ts > self.cache_ttl_seconds:
            self._cache.pop(key, None)
            return None
        return val

    def _set_cached(self, key: str, val: Any) -> None:
        self._cache[key] = (time.time(), val)

    def _lookup_cik_and_filings(self, ticker: str) -> tuple[str | None, list[dict[str, str]]]:
        t = ticker.upper()
        headers = {"User-Agent": self.user_agent}
        try:
            with httpx.Client(timeout=6.0, headers=headers) as client:
                if self._cik_map is None:
                    resp = client.get("https://www.sec.gov/files/company_tickers.json")
                    resp.raise_for_status()
                    raw = resp.json()
                    self._cik_map = {
                        str(item["ticker"]).upper(): str(item["cik_str"]).zfill(10)
                        for item in raw.values()
                    }
                cik = self._cik_map.get(t)
                if not cik:
                    return None, []
                sub_resp = client.get(f"https://data.sec.gov/submissions/CIK{cik}.json")
                sub_resp.raise_for_status()
                recent = sub_resp.json().get("filings", {}).get("recent", {})
                forms = recent.get("form", [])
                dates = recent.get("filingDate", [])
                acc_nums = recent.get("accessionNumber", [])
                filings: list[dict[str, str]] = []
                for form, fdate, acc in zip(forms, dates, acc_nums):
                    if form in {"10-K", "10-Q", "8-K"}:
                        filings.append({"form": form, "filingDate": fdate, "accessionNumber": acc})
                    if len(filings) >= 6:
                        break
                return cik, filings
        except Exception:
            return None, []

    def get_company_profile(self, ticker: str) -> CompanyProfile:
        t = ticker.upper()
        if self.mode == "fixture":
            return self._fallback.get_company_profile(t)
        cached = self._get_cached(f"profile:{t}")
        if cached is not None:
            return cached

        try:
            tk = yf.Ticker(t)
            info = tk.info or {}
            if not info.get("longName") and not info.get("shortName"):
                raise ValueError(f"Missing company info for {t}")
            cik, filings = self._lookup_cik_and_filings(t)
            profile = CompanyProfile(
                ticker=t,
                name=info.get("longName") or info.get("shortName") or t,
                sector=info.get("sector") or "Unknown",
                industry=info.get("industry") or "Unknown",
                cik=cik,
                exchange=info.get("exchange") or "US",
                description=info.get("longBusinessSummary") or f"Public equity profile for {t}.",
                employees=info.get("fullTimeEmployees"),
                website=info.get("website"),
                recent_filings=filings,
                citation=Citation(
                    source="SEC EDGAR & Yahoo Finance",
                    label=f"{t} profile & recent filings",
                    url=f"https://www.sec.gov/edgar/browse/?CIK={cik}" if cik else f"https://finance.yahoo.com/quote/{t}",
                    retrieved_at=utc_now_iso(),
                ),
            )
            self._set_cached(f"profile:{t}", profile)
            return profile
        except Exception:
            if self.mode == "auto":
                return self._fallback.get_company_profile(t)
            raise

    @staticmethod
    def _df_to_statement_dict(df: Any) -> dict[str, dict[str, float | None]]:
        if df is None or getattr(df, "empty", True):
            return {}
        result: dict[str, dict[str, float | None]] = {}
        for col in list(df.columns)[:4]:
            col_label = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
            col_dict: dict[str, float | None] = {}
            for idx_name, val in df[col].items():
                if val is None or str(val) == "nan":
                    col_dict[str(idx_name)] = None
                else:
                    try:
                        col_dict[str(idx_name)] = float(val)
                    except (TypeError, ValueError):
                        col_dict[str(idx_name)] = None
            result[col_label] = col_dict
        return result

    def get_financial_statements(
        self,
        ticker: str,
        statement_type: Literal["income", "balance", "cashflow", "all"] = "all",
        period: Literal["annual", "quarterly"] = "annual",
    ) -> FinancialStatements:
        t = ticker.upper()
        if self.mode == "fixture":
            return self._fallback.get_financial_statements(t, statement_type=statement_type, period=period)
        cache_key = f"stmt:{t}:{statement_type}:{period}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            tk = yf.Ticker(t)
            is_q = period == "quarterly"
            raw_map = {
                "income": tk.quarterly_income_stmt if is_q else tk.income_stmt,
                "balance": tk.quarterly_balance_sheet if is_q else tk.balance_sheet,
                "cashflow": tk.quarterly_cashflow if is_q else tk.cashflow,
            }
            keys = ["income", "balance", "cashflow"] if statement_type == "all" else [statement_type]
            statements = {k: self._df_to_statement_dict(raw_map[k]) for k in keys}
            if not any(statements.values()):
                raise ValueError(f"Empty financial statements for {t}")
            data = FinancialStatements(
                ticker=t,
                statement_type=statement_type,
                period=period,
                statements=statements,
                citation=Citation(
                    source="Yahoo Finance / SEC Filings",
                    label=f"{t} {statement_type} statements ({period})",
                    url=f"https://finance.yahoo.com/quote/{t}/financials",
                    retrieved_at=utc_now_iso(),
                ),
            )
            self._set_cached(cache_key, data)
            return data
        except Exception:
            if self.mode == "auto":
                return self._fallback.get_financial_statements(t, statement_type=statement_type, period=period)
            raise

    def get_valuation_and_earnings(self, ticker: str) -> ValuationAndEarnings:
        t = ticker.upper()
        if self.mode == "fixture":
            return self._fallback.get_valuation_and_earnings(t)
        cached = self._get_cached(f"val:{t}")
        if cached is not None:
            return cached

        try:
            tk = yf.Ticker(t)
            info = tk.info or {}
            if not info:
                raise ValueError(f"Missing valuation info for {t}")
            val = ValuationAndEarnings(
                ticker=t,
                market_cap=info.get("marketCap"),
                pe_trailing=info.get("trailingPE"),
                pe_forward=info.get("forwardPE"),
                ev_to_ebitda=info.get("enterpriseToEbitda"),
                price_to_book=info.get("priceToBook"),
                profit_margin_pct=round(info["profitMargins"] * 100.0, 2) if info.get("profitMargins") is not None else None,
                operating_margin_pct=round(info["operatingMargins"] * 100.0, 2) if info.get("operatingMargins") is not None else None,
                roe_pct=round(info["returnOnEquity"] * 100.0, 2) if info.get("returnOnEquity") is not None else None,
                revenue_growth_pct=round(info["revenueGrowth"] * 100.0, 2) if info.get("revenueGrowth") is not None else None,
                eps_trailing=info.get("trailingEps"),
                eps_forward=info.get("forwardEps"),
                earnings_history=[],
                citation=Citation(
                    source="Yahoo Finance Fundamentals",
                    label=f"{t} valuation multiples & margins",
                    url=f"https://finance.yahoo.com/quote/{t}/key-statistics",
                    retrieved_at=utc_now_iso(),
                ),
            )
            self._set_cached(f"val:{t}", val)
            return val
        except Exception:
            if self.mode == "auto":
                return self._fallback.get_valuation_and_earnings(t)
            raise
