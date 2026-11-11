from __future__ import annotations

import math

import pytest

from apps.api.app.config import get_settings
from apps.api.app.db.session import SessionLocal, init_db
from apps.api.app.harness.reasoning import (
    compute_fundamental_reasoning,
    synthesize_cross_domain_insight,
)
from apps.api.app.routes.chat import ChatRequest, chat_turn
from services.mcp_research.provider import FixtureResearchProvider


@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "fixture")
    monkeypatch.setenv("SANDBOX_MODE", "local_restricted")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "true")
    get_settings.cache_clear()
    init_db()


def test_fundamental_reasoning_math_matches_ground_truth():
    provider = FixtureResearchProvider()

    # NVDA: hyper-growth, huge operating margin expansion, net cash balance sheet
    nvda_stmts = provider.get_financial_statements("NVDA", statement_type="all", period="annual")
    nvda_val = provider.get_valuation_and_earnings("NVDA").model_dump()
    nvda_r = compute_fundamental_reasoning("NVDA", nvda_stmts.statements, nvda_val)
    facts = nvda_r["facts"]

    expected_cagr = (((130.50e9 / 26.97e9) ** 0.5) - 1.0) * 100.0
    assert math.isclose(facts["revenue_cagr_pct"], expected_cagr, abs_tol=0.05)

    op_m0 = (4.22e9 / 26.97e9) * 100.0
    op_m1 = (81.40e9 / 130.50e9) * 100.0
    expected_bps = round((op_m1 - op_m0) * 100.0)
    assert abs(facts["operating_margin_delta_bps"] - expected_bps) <= 1

    # Cash 14.20B vs Debt 8.46B -> Net Cash +5.74B
    assert math.isclose(facts["net_cash"], 5.74e9, rel_tol=1e-3)
    # Forward P/E 33.6 vs Trailing P/E 48.2 -> +43.5% implied EPS growth
    expected_eps_g = ((48.2 / 33.6) - 1.0) * 100.0
    assert math.isclose(facts["implied_forward_eps_growth_pct"], expected_eps_g, abs_tol=0.2)

    # AAPL: high FCF conversion (>100%) and net debt position
    aapl_stmts = provider.get_financial_statements("AAPL", statement_type="all", period="annual")
    aapl_val = provider.get_valuation_and_earnings("AAPL").model_dump()
    aapl_r = compute_fundamental_reasoning("AAPL", aapl_stmts.statements, aapl_val)["facts"]
    assert math.isclose(aapl_r["fcf_conversion_pct"], (115.20 / 105.10) * 100.0, abs_tol=0.2)
    assert math.isclose(aapl_r["net_cash"], (35.10e9 - 101.40e9), rel_tol=1e-3)


def test_cross_domain_convergence_and_divergence_reasoning():
    strong_fund = {"operating_margin_delta_bps": 450, "fcf_conversion_pct": 105.0}
    weak_fund = {"operating_margin_delta_bps": -120, "fcf_conversion_pct": 65.0}
    val = {"pe_forward": 28.5, "roe_pct": 32.0}

    bull_aligned = synthesize_cross_domain_insight(
        "MSFT",
        {"trend": "bullish", "rsi_14": 62.0, "volume_ratio": 1.4},
        strong_fund,
        val,
    )
    assert bull_aligned["alignment"] == "convergent_bullish"
    assert "elevated at `1.4x`" in bull_aligned["summary"]

    divergent = synthesize_cross_domain_insight(
        "AAPL",
        {"trend": "bearish", "rsi_14": 28.0, "volume_ratio": 1.0},
        strong_fund,
        val,
    )
    assert divergent["alignment"] == "fundamental_strong_technical_weak"
    assert "oversold" in divergent["summary"]

    momentum_only = synthesize_cross_domain_insight(
        "TSLA",
        {"trend": "bullish", "rsi_14": 74.0, "volume_ratio": 1.1},
        weak_fund,
        {"pe_forward": 65.0, "roe_pct": 11.0},
    )
    assert momentum_only["alignment"] == "momentum_ahead_of_fundamentals"
    assert "overbought" in momentum_only["summary"]


def test_end_to_end_chat_narrative_contains_verified_reasoning():
    with SessionLocal() as db:
        res = chat_turn(
            ChatRequest(query="Analyze MSFT fundamentals, financial statements, and valuation"),
            db=db,
        )
        assert "Revenue Trajectory" in res.narrative
        assert "Operating Leverage" in res.narrative
        assert "Cash Conversion" in res.narrative
        assert "Balance Sheet Position" in res.narrative
        assert "Cross-Domain Synthesis (MSFT)" in res.narrative

        dcf_res = chat_turn(
            ChatRequest(query="Run a what-if DCF valuation for NVDA with growth 18% and wacc 9.5%"),
            db=db,
        )
        assert "Terminal Value represents" in dcf_res.narrative
