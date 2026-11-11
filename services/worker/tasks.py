from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import redis

from apps.api.app.db.models import AnalysisJob
from apps.api.app.db.session import SessionLocal, init_db
from packages.shared_schemas.schemas import (
    AnalysisResponse,
    Assumption,
    ChartSpec,
    Citation,
    IndicatorSeries,
    JobProgressEvent,
    JobStatus,
    LinePoint,
    SandboxRequest,
    TableSpec,
)
from services.mcp_market.provider import YFinanceMarketProvider
from services.mcp_research.provider import SecEdgarAndYFinanceProvider
from services.sandbox.runner import SandboxService
from services.sandbox.templates import (
    DCF_WHAT_IF_SCRIPT,
    MONTE_CARLO_SCRIPT,
    STOCK_COMPARISON_SCRIPT,
)
from services.worker.celery_app import celery_app


def _publish_progress(
    job_id: str,
    status: JobStatus,
    progress: int,
    stage: str,
    message: str,
    retries: int = 0,
    result_json: str | None = None,
    error: str | None = None,
) -> None:
    init_db()
    with SessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        if job is not None:
            job.status = status.value
            job.progress = progress
            job.stage = stage
            job.message = message
            job.retries = retries
            job.updated_at = datetime.now(timezone.utc)
            if result_json is not None:
                job.result_json = result_json
            if error is not None:
                job.error = error
            db.commit()

    event = JobProgressEvent(
        job_id=job_id,
        status=status,
        progress=progress,
        stage=stage,
        message=message,
        retries=retries,
    )
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        client = redis.Redis.from_url(redis_url, socket_connect_timeout=0.5, socket_timeout=0.5)
        client.publish(f"job_progress:{job_id}", event.model_dump_json())
    except Exception:
        # Local dev without Redis running still persists progress in SQLite/PostgreSQL.
        pass


@celery_app.task(
    bind=True,
    name="services.worker.tasks.run_deep_analysis_task",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=30,
    max_retries=3,
)
def run_deep_analysis_task(
    self: Any,
    job_id: str,
    tickers: list[str],
    analysis_type: str = "peer_and_what_if",
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Long-running deep stock comparison, Monte Carlo, and DCF sensitivity analysis."""
    params = params or {}
    retries = getattr(self.request, "retries", 0)
    clean_tickers = [t.upper() for t in tickers if t.strip()][:5] or ["AAPL", "MSFT"]

    try:
        _publish_progress(
            job_id,
            JobStatus.STARTED,
            10,
            "fetching_market_data",
            f"Fetching OHLCV & fundamentals for {', '.join(clean_tickers)} via MCP...",
            retries=retries,
        )

        mode = os.getenv("MARKET_DATA_MODE", "auto")
        mkt = YFinanceMarketProvider(mode=mode)
        res = SecEdgarAndYFinanceProvider(mode=mode)
        sandbox = SandboxService(mode=os.getenv("SANDBOX_MODE", "local_restricted"))

        series_map: dict[str, list[dict[str, Any]]] = {}
        citations: list[Citation] = []
        valuation_rows: list[list[Any]] = []
        primary_ticker = clean_tickers[0]
        primary_fcf = 50.0e9
        primary_price = 150.0

        for idx, t in enumerate(clean_tickers):
            ohlcv = mkt.get_ohlcv(t, period=params.get("period", "6mo"), interval="1d")
            val = res.get_valuation_and_earnings(t)
            stmt = res.get_financial_statements(t, statement_type="cashflow", period="annual")
            series_map[t] = [c.model_dump() for c in ohlcv.candles]
            citations.extend([ohlcv.citation, val.citation, stmt.citation])

            cf_years = sorted(stmt.statements.get("cashflow", {}).keys())
            latest_fcf = None
            if cf_years:
                latest_cf = stmt.statements["cashflow"][cf_years[-1]]
                latest_fcf = latest_cf.get("Free Cash Flow") or latest_cf.get("Operating Cash Flow")
            if idx == 0:
                primary_price = ohlcv.candles[-1].close if ohlcv.candles else 150.0
                if latest_fcf:
                    primary_fcf = float(latest_fcf)

            valuation_rows.append(
                [
                    t,
                    f"${ohlcv.candles[-1].close:.2f}" if ohlcv.candles else "N/A",
                    f"{val.pe_trailing:.1f}x" if val.pe_trailing else "N/A",
                    f"{val.pe_forward:.1f}x" if val.pe_forward else "N/A",
                    f"{val.ev_to_ebitda:.1f}x" if val.ev_to_ebitda else "N/A",
                    f"{val.profit_margin_pct:.1f}%" if val.profit_margin_pct is not None else "N/A",
                    f"{val.revenue_growth_pct:.1f}%" if val.revenue_growth_pct is not None else "N/A",
                ]
            )

        _publish_progress(
            job_id,
            JobStatus.PROGRESS,
            45,
            "running_comparison_sandbox",
            "Running cross-stock return, volatility, and drawdown models in isolated Python sandbox...",
            retries=retries,
        )

        comp_res = sandbox.run(
            SandboxRequest(
                code=STOCK_COMPARISON_SCRIPT,
                inputs={"series": series_map},
                timeout_seconds=30,
            )
        )
        if not comp_res.success:
            raise RuntimeError(f"Comparison sandbox error: {comp_res.error}")

        _publish_progress(
            job_id,
            JobStatus.PROGRESS,
            75,
            "running_what_if_and_monte_carlo",
            f"Running Monte Carlo & DCF sensitivity grid for {primary_ticker} in sandbox...",
            retries=retries,
        )

        mc_res = sandbox.run(
            SandboxRequest(
                code=MONTE_CARLO_SCRIPT,
                inputs={
                    "closes": [c["close"] for c in series_map[primary_ticker]],
                    "horizon_days": int(params.get("horizon_days", 90)),
                    "n_paths": int(params.get("n_paths", 2000)),
                },
                timeout_seconds=30,
            )
        )

        shares_est = (
            (mkt.get_quote(primary_ticker).market_cap or (primary_price * 1e9)) / primary_price
            if primary_price > 0
            else 1e9
        )
        dcf_res = sandbox.run(
            SandboxRequest(
                code=DCF_WHAT_IF_SCRIPT,
                inputs={
                    "base_fcf": primary_fcf,
                    "shares_outstanding": shares_est,
                    "fcf_growth_rate": float(params.get("fcf_growth_rate", 0.12)),
                    "wacc": float(params.get("wacc", 0.09)),
                    "terminal_growth": float(params.get("terminal_growth", 0.03)),
                    "current_price": primary_price,
                },
                timeout_seconds=30,
            )
        )

        palette = ["#38bdf8", "#a78bfa", "#22c55e", "#f59e0b", "#f43f5e"]
        norm_series = comp_res.outputs.get("normalized_series", {})
        comparison_chart = ChartSpec(
            id=f"comp-{job_id[:8]}",
            title=f"Normalized Performance Comparison ({', '.join(clean_tickers)}, Base = 100)",
            ticker=", ".join(clean_tickers),
            chart_type="comparison_line",
            series=[
                IndicatorSeries(
                    name=t,
                    pane="overlay",
                    color=palette[i % len(palette)],
                    points=[LinePoint(time=p["time"], value=p["value"]) for p in pts],
                )
                for i, (t, pts) in enumerate(norm_series.items())
            ],
        )

        comp_metrics = comp_res.outputs.get("metrics", [])
        perf_table = TableSpec(
            id=f"perf-{job_id[:8]}",
            title="Quantitative Risk & Return Comparison",
            columns=["Ticker", "Start", "End", "Return %", "Ann. Vol %", "Sharpe Proxy", "Max Drawdown %"],
            rows=[
                [
                    m["ticker"],
                    f"${m['start_price']}",
                    f"${m['end_price']}",
                    f"{m['total_return_pct']}%",
                    f"{m['annualized_vol_pct']}%",
                    m["sharpe_proxy"],
                    f"{m['max_drawdown_pct']}%",
                ]
                for m in comp_metrics
            ],
        )

        val_table = TableSpec(
            id=f"val-{job_id[:8]}",
            title="Fundamental Valuation & Profitability Comparison",
            columns=["Ticker", "Price", "Trailing P/E", "Forward P/E", "EV/EBITDA", "Net Margin", "Rev Growth"],
            rows=valuation_rows,
        )

        tables = [perf_table, val_table]
        if dcf_res.success and dcf_res.outputs.get("sensitivity_matrix"):
            sens_rows = dcf_res.outputs["sensitivity_matrix"]
            cols = ["WACC %"] + [k for k in sens_rows[0].keys() if k != "wacc_pct"]
            tables.append(
                TableSpec(
                    id=f"dcf-sens-{job_id[:8]}",
                    title=f"{primary_ticker} DCF What-If Sensitivity (Implied Value / Share)",
                    columns=cols,
                    rows=[[r["wacc_pct"]] + [r[c] for c in cols[1:]] for r in sens_rows],
                )
            )

        mc_out = mc_res.outputs if mc_res.success else {}
        dcf_out = dcf_res.outputs if dcf_res.success else {}

        narrative_parts = [
            f"### Deep Analysis Complete: {', '.join(clean_tickers)}",
            "",
            f"- **Risk & Return:** Computed normalized performance, annualized volatility, and max drawdown across {len(clean_tickers)} tickers in the isolated Python sandbox (`{sandbox.mode}`).",
        ]
        if mc_out:
            narrative_parts.append(
                f"- **{primary_ticker} {mc_out.get('horizon_days', 90)}-Day Monte Carlo ({mc_out.get('n_paths', 2000)} paths):** "
                f"P10 = **${mc_out.get('terminal_p10')}**, Median P50 = **${mc_out.get('terminal_p50')}**, "
                f"P90 = **${mc_out.get('terminal_p90')}** (P(positive return) = {mc_out.get('prob_positive_return_pct')}%)."
            )
        if dcf_out:
            narrative_parts.append(
                f"- **{primary_ticker} Baseline DCF:** Implied fair value **${dcf_out.get('intrinsic_value_per_share')}** "
                f"vs current **${dcf_out.get('current_price')}** ({dcf_out.get('implied_upside_pct')}% implied upside)."
            )

        assumptions = [
            Assumption(key="Period", value=str(params.get("period", "6mo")), rationale="Historical window for return & volatility estimation"),
            Assumption(key="FCF Growth Rate", value=f"{float(params.get('fcf_growth_rate', 0.12))*100:.1f}%", rationale="5-year baseline annual FCF growth for DCF"),
            Assumption(key="WACC / Terminal Growth", value=f"{float(params.get('wacc', 0.09))*100:.1f}% / {float(params.get('terminal_growth', 0.03))*100:.1f}%", rationale="Discount rate & perpetuity growth"),
            Assumption(key="Monte Carlo Paths", value=str(params.get("n_paths", 2000)), rationale="Geometric Brownian Motion using empirical log-return drift & volatility"),
        ]

        # Deduplicate citations by label
        seen_labels: set[str] = set()
        unique_citations: list[Citation] = []
        for c in citations:
            if c.label not in seen_labels:
                seen_labels.add(c.label)
                unique_citations.append(c)

        response = AnalysisResponse(
            conversation_id=params.get("conversation_id", "background-job"),
            message_id=f"job-{job_id}",
            narrative="\n".join(narrative_parts),
            tickers=clean_tickers,
            charts=[comparison_chart],
            tables=tables,
            citations=unique_citations,
            assumptions=assumptions,
            tools_used=["market-data-mcp", "company-research-mcp", "python-sandbox", "celery-worker"],
            job_id=job_id,
        )

        result_payload = response.model_dump()
        _publish_progress(
            job_id,
            JobStatus.SUCCESS,
            100,
            "completed",
            "Deep analysis finished and results persisted.",
            retries=retries,
            result_json=json.dumps(result_payload),
        )
        return result_payload
    except Exception as exc:
        _publish_progress(
            job_id,
            JobStatus.FAILURE,
            100,
            "failed",
            f"Deep analysis failed: {exc}",
            retries=retries,
            error=str(exc),
        )
        raise
