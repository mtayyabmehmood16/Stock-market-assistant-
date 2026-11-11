from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from apps.api.app.config import Settings
from apps.api.app.harness.context import ContextManager
from apps.api.app.harness.llm import AnalystPlannerLLM
from apps.api.app.harness.permissions import PermissionPolicy
from apps.api.app.harness.reasoning import (
    compute_fundamental_reasoning,
    synthesize_cross_domain_insight,
)
from apps.api.app.tools.registry import ToolExecutor
from packages.shared_schemas.schemas import (
    AnalysisResponse,
    Assumption,
    CandlestickPoint,
    ChartSpec,
    Citation,
    IndicatorSeries,
    LinePoint,
    TableSpec,
)


def _fmt_big(val: float | None) -> str:
    if val is None:
        return "N/A"
    abs_v = abs(val)
    if abs_v >= 1e12:
        return f"${val / 1e12:.2f}T"
    if abs_v >= 1e9:
        return f"${val / 1e9:.2f}B"
    if abs_v >= 1e6:
        return f"${val / 1e6:.2f}M"
    return f"${val:,.2f}"


class AIHarness:
    """Coordinates LLM planning, context, permissions, MCP/sandbox tool execution, and structured outputs."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.context_mgr = ContextManager()
        self.policy = PermissionPolicy()
        self.planner = AnalystPlannerLLM(settings)
        self.executor = ToolExecutor(settings)

    def run_turn(self, db: Session, conversation_id: str, user_query: str) -> AnalysisResponse:
        ctx = self.context_mgr.load_or_create(db, conversation_id, user_query)
        planned_calls = self.planner.plan_tools(user_query, ctx.active_tickers)

        tool_outputs: dict[str, Any] = {}
        tools_used: list[str] = []
        charts: list[ChartSpec] = []
        tables: list[TableSpec] = []
        citations: list[Citation] = []
        assumptions: list[Assumption] = []
        narrative_sections: list[str] = []
        job_id: str | None = None
        tech_summary_by_ticker: dict[str, dict[str, Any]] = {}
        fund_facts_by_ticker: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}

        for call in planned_calls:
            safe_args = self.policy.authorize_tool_call(call.name, call.args)
            result = self.executor.execute(call.name, safe_args, db=db, conversation_id=conversation_id)
            tool_outputs[call.name] = result
            tools_used.append(call.name)

            if call.name == "get_technical_analysis":
                self._append_technical_artifacts(result, charts, tables, citations, assumptions, narrative_sections)
                t_sym = result["technical"]["ticker"]
                tech_summary_by_ticker[t_sym] = result["technical"]["summary"]
            elif call.name == "get_fundamental_research":
                fund_facts = self._append_fundamental_artifacts(result, tables, citations, assumptions, narrative_sections)
                p_sym = result["profile"]["ticker"]
                fund_facts_by_ticker[p_sym] = (fund_facts, result["valuation"])
            elif call.name == "compare_stocks_python":
                self._append_comparison_artifacts(result, charts, tables, citations, assumptions, narrative_sections)
            elif call.name == "run_what_if_dcf":
                self._append_dcf_artifacts(result, tables, citations, assumptions, narrative_sections)
            elif call.name == "enqueue_deep_analysis":
                job_id = result["job_id"]
                narrative_sections.append(
                    f"### Background Deep Analysis Queued (`{job_id[:8]}`)\n"
                    f"- Dispatched Celery task for **{', '.join(result['tickers'])}** with live progress tracking, retries, and saved results."
                )

        for t_sym, (f_facts, val_data) in fund_facts_by_ticker.items():
            if t_sym in tech_summary_by_ticker:
                cross = synthesize_cross_domain_insight(
                    ticker=t_sym,
                    tech_summary=tech_summary_by_ticker[t_sym],
                    fund_facts=f_facts,
                    valuation=val_data,
                )
                if cross.get("summary"):
                    narrative_sections.append(cross["summary"])
                tool_outputs[f"reasoning_{t_sym}"] = {"fundamental_facts": f_facts, "cross_domain": cross}

        fallback_narrative = "\n\n".join(narrative_sections) if narrative_sections else "Analysis complete."
        final_narrative = self.planner.synthesize_narrative(user_query, tool_outputs, fallback_narrative)

        # Deduplicate citations
        seen_cites: set[str] = set()
        unique_citations: list[Citation] = []
        for c in citations:
            if c.label not in seen_cites:
                seen_cites.add(c.label)
                unique_citations.append(c)

        user_msg_id = str(uuid.uuid4())
        assistant_msg_id = str(uuid.uuid4())
        response = AnalysisResponse(
            conversation_id=conversation_id,
            message_id=assistant_msg_id,
            narrative=final_narrative,
            tickers=ctx.active_tickers,
            charts=charts,
            tables=tables,
            citations=unique_citations,
            assumptions=assumptions,
            tools_used=tools_used,
            job_id=job_id,
        )

        self.context_mgr.save_turn(
            db=db,
            conversation_id=conversation_id,
            user_msg_id=user_msg_id,
            user_query=user_query,
            assistant_msg_id=assistant_msg_id,
            assistant_narrative=response.narrative,
            response_payload_json=response.model_dump_json(),
            active_tickers=ctx.active_tickers,
        )
        return response

    @staticmethod
    def _append_technical_artifacts(
        result: dict[str, Any],
        charts: list[ChartSpec],
        tables: list[TableSpec],
        citations: list[Citation],
        assumptions: list[Assumption],
        narrative_sections: list[str],
    ) -> None:
        quote = result["quote"]
        tech = result["technical"]
        ticker = tech["ticker"]
        summary = tech["summary"]

        charts.append(
            ChartSpec(
                id=f"tech-{ticker}",
                title=f"{ticker} Price, Volume & Technical Indicators ({tech['period']})",
                subtitle=f"Trend: {summary.get('trend', 'neutral').title()} | Close: ${quote['price']:.2f} ({quote['change_pct']:+.2f}%)",
                ticker=ticker,
                chart_type="candlestick",
                candlesticks=[CandlestickPoint(**c) for c in tech["candles"]],
                series=[IndicatorSeries(**s) for s in tech["indicators"]],
            )
        )

        tables.append(
            TableSpec(
                id=f"tech-metrics-{ticker}",
                title=f"{ticker} Technical Indicator Snapshot",
                columns=["Metric", "Value"],
                rows=[
                    ["Last Close", f"${summary.get('latest_close', 'N/A')}"],
                    ["Period Return", f"{summary.get('period_return_pct', 'N/A')}%"],
                    ["SMA 20 / SMA 50", f"{summary.get('sma_20', 'N/A')} / {summary.get('sma_50', 'N/A')}"],
                    ["RSI (14)", str(summary.get("rsi_14", "N/A"))],
                    ["MACD / Signal", f"{summary.get('macd', 'N/A')} / {summary.get('macd_signal', 'N/A')}"],
                    ["ATR (14)", str(summary.get("atr_14", "N/A"))],
                    ["Latest / 20D Avg Vol", f"{summary.get('latest_volume', 0):,} / {summary.get('avg_volume_20d', 0):,} ({summary.get('volume_ratio', 'N/A')}x)"],
                    ["Overall Trend", str(summary.get("trend", "N/A")).title()],
                ],
            )
        )

        citations.append(Citation(**quote["citation"]))
        citations.append(Citation(**tech["citation"]))
        assumptions.append(
            Assumption(
                key=f"{ticker} Technical Window",
                value=f"{tech['period']} ({tech['interval']} bars)",
                rationale="SMA(20/50), EMA(20), Bollinger(20,2), RSI(14), MACD(12,26,9)",
            )
        )

        sig_bullets = "\n".join(f"  - {s}" for s in summary.get("signals", []))
        narrative_sections.append(
            f"### {ticker} Technical Analysis (`${quote['price']:.2f}`, `{quote['change_pct']:+.2f}%`)\n"
            f"- **Regime:** {str(summary.get('trend', 'neutral')).title()} over the `{tech['period']}` window ({summary.get('period_return_pct', 0):+.2f}% period return).\n"
            f"- **Volume:** {summary.get('latest_volume', 0):,} shares vs. 20-day average {summary.get('avg_volume_20d', 0):,} (`{summary.get('volume_ratio', 'N/A')}x`).\n"
            f"- **Signals:**\n{sig_bullets}"
        )

    @staticmethod
    def _append_fundamental_artifacts(
        result: dict[str, Any],
        tables: list[TableSpec],
        citations: list[Citation],
        assumptions: list[Assumption],
        narrative_sections: list[str],
    ) -> dict[str, Any]:
        profile = result["profile"]
        val = result["valuation"]
        stmts = result["statements"]
        ticker = profile["ticker"]

        tables.append(
            TableSpec(
                id=f"fund-val-{ticker}",
                title=f"{ticker} Valuation & Profitability Snapshot",
                columns=["Metric", "Value"],
                rows=[
                    ["Company", f"{profile['name']} ({profile['sector']} / {profile['industry']})"],
                    ["Market Cap", _fmt_big(val.get("market_cap"))],
                    ["Trailing / Forward P/E", f"{val.get('pe_trailing', 'N/A')} / {val.get('pe_forward', 'N/A')}"],
                    ["EV / EBITDA", str(val.get("ev_to_ebitda", "N/A"))],
                    ["Price / Book", str(val.get("price_to_book", "N/A"))],
                    ["Operating / Net Margin", f"{val.get('operating_margin_pct', 'N/A')}% / {val.get('profit_margin_pct', 'N/A')}%"],
                    ["ROE", f"{val.get('roe_pct', 'N/A')}%"],
                    ["Revenue Growth (YoY)", f"{val.get('revenue_growth_pct', 'N/A')}%"],
                    ["EPS (Trailing / Forward)", f"{val.get('eps_trailing', 'N/A')} / {val.get('eps_forward', 'N/A')}"],
                ],
            )
        )

        income = stmts.get("statements", {}).get("income", {})
        if income:
            years = sorted(income.keys())
            line_items = list(income[years[-1]].keys())[:6]
            tables.append(
                TableSpec(
                    id=f"fund-income-{ticker}",
                    title=f"{ticker} Income Statement ({stmts['period'].title()})",
                    columns=["Line Item"] + years,
                    rows=[[item] + [_fmt_big(income[y].get(item)) for y in years] for item in line_items],
                )
            )

        citations.append(Citation(**profile["citation"]))
        citations.append(Citation(**stmts["citation"]))
        citations.append(Citation(**val["citation"]))
        assumptions.append(
            Assumption(
                key=f"{ticker} Fundamentals Basis",
                value=f"{stmts['period'].title()} reported statements",
                rationale="Sourced from SEC EDGAR / Yahoo Finance",
            )
        )

        reasoning = compute_fundamental_reasoning(
            ticker=ticker,
            statements=stmts.get("statements", {}),
            valuation=val,
        )
        reasoning_bullets = "\n".join(f"- {b}" for b in reasoning["bullets"])
        narrative_sections.append(
            f"### {ticker} Fundamental Research — {profile['name']}\n"
            f"- **Sector & Business:** {profile['sector']} ({profile['industry']}). {profile['description']}\n"
            f"- **Valuation & Quality:** Market Cap {_fmt_big(val.get('market_cap'))}, Trailing P/E `{val.get('pe_trailing', 'N/A')}`, "
            f"Forward P/E `{val.get('pe_forward', 'N/A')}`, Net Margin `{val.get('profit_margin_pct', 'N/A')}%`, ROE `{val.get('roe_pct', 'N/A')}%`."
            + (f"\n{reasoning_bullets}" if reasoning_bullets else "")
        )
        return reasoning["facts"]

    @staticmethod
    def _append_comparison_artifacts(
        result: dict[str, Any],
        charts: list[ChartSpec],
        tables: list[TableSpec],
        citations: list[Citation],
        assumptions: list[Assumption],
        narrative_sections: list[str],
    ) -> None:
        sb = result["sandbox"]
        tickers = result["tickers"]
        outputs = sb.get("outputs", {})
        norm_series = outputs.get("normalized_series", {})
        metrics = outputs.get("metrics", [])

        palette = ["#38bdf8", "#a78bfa", "#22c55e", "#f59e0b", "#f43f5e"]
        if norm_series:
            charts.append(
                ChartSpec(
                    id=f"cmp-{'-'.join(tickers)}",
                    title=f"Normalized Comparison ({', '.join(tickers)}, Base = 100)",
                    subtitle=f"Computed in Python sandbox ({sb.get('mode')})",
                    ticker=", ".join(tickers),
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
            )

        if metrics:
            tables.append(
                TableSpec(
                    id=f"cmp-table-{'-'.join(tickers)}",
                    title="Python Sandbox Risk & Return Comparison",
                    columns=["Ticker", "Start", "End", "Total Return %", "Ann. Volatility %", "Sharpe Proxy", "Max Drawdown %"],
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
                        for m in metrics
                    ],
                )
            )

        for c in result.get("citations", []):
            citations.append(Citation(**c))
        assumptions.append(
            Assumption(
                key="Comparison Normalization",
                value=f"Base = 100 over {result['period']} (252 trading days/yr)",
                rationale=f"Calculated in isolated Python sandbox ({sb.get('mode')})",
            )
        )
        if metrics:
            leader = max(metrics, key=lambda x: x["total_return_pct"])
            sharpe_leader = max(metrics, key=lambda x: x["sharpe_proxy"])
            risk_note = (
                f"**{sharpe_leader['ticker']}** also led on risk-adjusted return (Sharpe proxy `{sharpe_leader['sharpe_proxy']}`)."
                if sharpe_leader["ticker"] == leader["ticker"]
                else f"However, **{sharpe_leader['ticker']}** delivered the best risk-adjusted Sharpe proxy (`{sharpe_leader['sharpe_proxy']}` vs. `{leader['sharpe_proxy']}`), indicating lower volatility per unit of return."
            )
            narrative_sections.append(
                f"### Python Comparison: {' vs '.join(tickers)}\n"
                f"- **Top Return:** **{leader['ticker']}** led with `{leader['total_return_pct']}%` return "
                f"(annualized volatility `{leader['annualized_vol_pct']}%`, max drawdown `{leader['max_drawdown_pct']}%`).\n"
                f"- **Risk-Adjusted Assessment:** {risk_note}"
            )

    @staticmethod
    def _append_dcf_artifacts(
        result: dict[str, Any],
        tables: list[TableSpec],
        citations: list[Citation],
        assumptions: list[Assumption],
        narrative_sections: list[str],
    ) -> None:
        ticker = result["ticker"]
        inputs = result["inputs"]
        sb = result["sandbox"]
        out = sb.get("outputs", {})

        if out.get("yearly_projection"):
            tables.append(
                TableSpec(
                    id=f"dcf-proj-{ticker}",
                    title=f"{ticker} 5-Year FCF Projection (Python Sandbox)",
                    columns=["Year", "Projected FCF", "Present Value of FCF"],
                    rows=[
                        [f"Year {r['year']}", _fmt_big(r["projected_fcf"]), _fmt_big(r["pv_fcf"])]
                        for r in out["yearly_projection"]
                    ],
                )
            )

        if out.get("sensitivity_matrix"):
            sens = out["sensitivity_matrix"]
            cols = ["WACC %"] + [k for k in sens[0].keys() if k != "wacc_pct"]
            tables.append(
                TableSpec(
                    id=f"dcf-sens-{ticker}",
                    title=f"{ticker} What-If Sensitivity Grid (Implied Value / Share)",
                    columns=cols,
                    rows=[[r["wacc_pct"]] + [r[c] for c in cols[1:]] for r in sens],
                )
            )

        for c in result.get("citations", []):
            citations.append(Citation(**c))

        assumptions.extend(
            [
                Assumption(key="Base Free Cash Flow", value=_fmt_big(inputs["base_fcf"]), rationale="Latest annual FCF from statement"),
                Assumption(key="FCF Growth Rate", value=f"{inputs['fcf_growth_rate']*100:.1f}%", rationale="User/baseline 5-year FCF CAGR"),
                Assumption(key="WACC / Terminal Growth", value=f"{inputs['wacc']*100:.1f}% / {inputs['terminal_growth']*100:.1f}%", rationale="Discount rate & perpetuity growth rate"),
            ]
        )

        tv_share = out.get("terminal_value_share_pct")
        tv_note = (
            f" Terminal Value represents `{tv_share}%` of Enterprise Value"
            + (" (high sensitivity to WACC/terminal growth assumptions — review the sensitivity matrix closely)." if tv_share and tv_share >= 75 else ".")
            if tv_share is not None
            else ""
        )
        narrative_sections.append(
            f"### {ticker} What-If DCF Valuation (Python Sandbox)\n"
            f"- **Implied Fair Value:** **${out.get('intrinsic_value_per_share', 'N/A')}** vs. current **${out.get('current_price', 'N/A')}** "
            f"(`{out.get('implied_upside_pct', 'N/A')}%` implied upside/downside).\n"
            f"- **Valuation Structure & Sensitivity:**{tv_note} See the WACC vs. Terminal Growth sensitivity table below for alternative what-if scenarios."
        )


def serialize_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
