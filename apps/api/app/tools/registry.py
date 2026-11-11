from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from apps.api.app.config import Settings
from apps.api.app.db.models import AnalysisJob
from packages.shared_schemas.schemas import SandboxRequest
from services.mcp_market.provider import YFinanceMarketProvider
from services.mcp_research.provider import SecEdgarAndYFinanceProvider
from services.sandbox.runner import SandboxService
from services.sandbox.templates import DCF_WHAT_IF_SCRIPT, STOCK_COMPARISON_SCRIPT

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_technical_analysis",
        "description": "Fetch OHLCV candlesticks, volume, and technical indicators (SMA, EMA, Bollinger, RSI, MACD) for a stock.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "period": {"type": "string", "default": "6mo"},
                "interval": {"type": "string", "default": "1d"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_fundamental_research",
        "description": "Fetch company profile, SEC filings, financial statements, valuation multiples, and earnings.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "statement_type": {"type": "string", "default": "all"},
                "period": {"type": "string", "default": "annual"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "compare_stocks_python",
        "description": "Compare 2+ tickers on normalized return, annualized volatility, Sharpe proxy, and max drawdown using the isolated Python sandbox.",
        "parameters": {
            "type": "object",
            "properties": {
                "tickers": {"type": "array", "items": {"type": "string"}},
                "period": {"type": "string", "default": "6mo"},
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "run_what_if_dcf",
        "description": "Run a custom DCF projection and WACC/terminal-growth sensitivity what-if analysis in the isolated Python sandbox.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "fcf_growth_rate": {"type": "number", "default": 0.12},
                "wacc": {"type": "number", "default": 0.09},
                "terminal_growth": {"type": "number", "default": 0.03},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "run_python_sandbox",
        "description": "Execute custom validated quantitative Python analysis in the isolated sandbox.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "inputs": {"type": "object", "default": {}},
            },
            "required": ["code"],
        },
    },
    {
        "name": "enqueue_deep_analysis",
        "description": "Dispatch a long-running Celery background job for multi-stock comparison, Monte Carlo, and DCF sensitivity with progress tracking.",
        "parameters": {
            "type": "object",
            "properties": {
                "tickers": {"type": "array", "items": {"type": "string"}},
                "horizon_days": {"type": "integer", "default": 90},
                "n_paths": {"type": "integer", "default": 2000},
                "period": {"type": "string", "default": "6mo"},
            },
            "required": ["tickers"],
        },
    },
]


class ToolExecutor:
    """Executes MCP, Sandbox, and Celery background tools on behalf of the AI harness."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.market = YFinanceMarketProvider(mode=settings.market_data_mode)
        self.research = SecEdgarAndYFinanceProvider(mode=settings.market_data_mode)
        self.sandbox = SandboxService(
            mode="local_restricted" if settings.sandbox_mode == "local_restricted" else "docker",
            docker_image=settings.sandbox_docker_image,
        )

    def execute(self, name: str, args: dict[str, Any], db: Session, conversation_id: str) -> dict[str, Any]:
        if name == "get_technical_analysis":
            ticker = str(args["ticker"]).upper()
            period = str(args.get("period", "6mo"))
            interval = str(args.get("interval", "1d"))
            quote = self.market.get_quote(ticker)
            tech = self.market.get_technical_indicators(ticker, period=period, interval=interval)
            return {
                "quote": quote.model_dump(),
                "technical": tech.model_dump(),
            }

        if name == "get_fundamental_research":
            ticker = str(args["ticker"]).upper()
            statement_type = args.get("statement_type", "all")
            period = args.get("period", "annual")
            profile = self.research.get_company_profile(ticker)
            statements = self.research.get_financial_statements(
                ticker, statement_type=statement_type, period=period
            )
            valuation = self.research.get_valuation_and_earnings(ticker)
            return {
                "profile": profile.model_dump(),
                "statements": statements.model_dump(),
                "valuation": valuation.model_dump(),
            }

        if name == "compare_stocks_python":
            tickers = [str(t).upper() for t in args.get("tickers", [])][:5]
            period = str(args.get("period", "6mo"))
            series_map: dict[str, list[dict[str, Any]]] = {}
            citations: list[dict[str, Any]] = []
            valuations: list[dict[str, Any]] = []
            for t in tickers:
                ohlcv = self.market.get_ohlcv(t, period=period, interval="1d")
                val = self.research.get_valuation_and_earnings(t)
                series_map[t] = [c.model_dump() for c in ohlcv.candles]
                citations.append(ohlcv.citation.model_dump())
                citations.append(val.citation.model_dump())
                valuations.append(val.model_dump())

            sb_res = self.sandbox.run(
                SandboxRequest(
                    code=STOCK_COMPARISON_SCRIPT,
                    inputs={"series": series_map},
                    timeout_seconds=self.settings.sandbox_timeout_seconds,
                )
            )
            return {
                "tickers": tickers,
                "period": period,
                "sandbox": sb_res.model_dump(),
                "valuations": valuations,
                "citations": citations,
            }

        if name == "run_what_if_dcf":
            ticker = str(args["ticker"]).upper()
            fcf_growth = float(args.get("fcf_growth_rate", 0.12))
            wacc = float(args.get("wacc", 0.09))
            terminal_growth = float(args.get("terminal_growth", 0.03))

            quote = self.market.get_quote(ticker)
            stmt = self.research.get_financial_statements(ticker, statement_type="cashflow", period="annual")
            cf_dict = stmt.statements.get("cashflow", {})
            years = sorted(cf_dict.keys())
            base_fcf = 25.0e9
            if years:
                latest = cf_dict[years[-1]]
                raw_fcf = latest.get("Free Cash Flow") or latest.get("Operating Cash Flow")
                if raw_fcf:
                    base_fcf = float(raw_fcf)
            shares_est = (quote.market_cap / quote.price) if (quote.market_cap and quote.price > 0) else 1.0e9

            sb_res = self.sandbox.run(
                SandboxRequest(
                    code=DCF_WHAT_IF_SCRIPT,
                    inputs={
                        "base_fcf": base_fcf,
                        "shares_outstanding": shares_est,
                        "fcf_growth_rate": fcf_growth,
                        "wacc": wacc,
                        "terminal_growth": terminal_growth,
                        "current_price": quote.price,
                    },
                    timeout_seconds=self.settings.sandbox_timeout_seconds,
                )
            )
            return {
                "ticker": ticker,
                "inputs": {
                    "base_fcf": base_fcf,
                    "shares_outstanding": shares_est,
                    "fcf_growth_rate": fcf_growth,
                    "wacc": wacc,
                    "terminal_growth": terminal_growth,
                    "current_price": quote.price,
                },
                "sandbox": sb_res.model_dump(),
                "citations": [quote.citation.model_dump(), stmt.citation.model_dump()],
            }

        if name == "run_python_sandbox":
            sb_res = self.sandbox.run(
                SandboxRequest(
                    code=str(args["code"]),
                    inputs=dict(args.get("inputs", {})),
                    timeout_seconds=self.settings.sandbox_timeout_seconds,
                )
            )
            return {"sandbox": sb_res.model_dump()}

        if name == "enqueue_deep_analysis":
            from services.worker.tasks import run_deep_analysis_task

            tickers = [str(t).upper() for t in args.get("tickers", [])][:5] or ["AAPL", "MSFT"]
            job_id = str(uuid.uuid4())
            params = {
                "conversation_id": conversation_id,
                "period": str(args.get("period", "6mo")),
                "horizon_days": int(args.get("horizon_days", 90)),
                "n_paths": int(args.get("n_paths", 2000)),
                "fcf_growth_rate": float(args.get("fcf_growth_rate", 0.12)),
                "wacc": float(args.get("wacc", 0.09)),
                "terminal_growth": float(args.get("terminal_growth", 0.03)),
            }
            job = AnalysisJob(
                id=job_id,
                job_type="deep_analysis",
                tickers_json=json.dumps(tickers),
                params_json=json.dumps(params),
                status="PENDING",
                progress=0,
                stage="queued",
                message=f"Queued deep analysis for {', '.join(tickers)}",
            )
            db.add(job)
            db.commit()

            run_deep_analysis_task.delay(
                job_id=job_id,
                tickers=tickers,
                analysis_type="peer_and_what_if",
                params=params,
            )
            return {
                "job_id": job_id,
                "tickers": tickers,
                "status": "queued_or_completed",
            }

        raise ValueError(f"Unknown tool '{name}'")
