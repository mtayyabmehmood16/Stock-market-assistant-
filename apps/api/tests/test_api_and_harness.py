from __future__ import annotations

import pytest

from apps.api.app.config import get_settings
from apps.api.app.db.session import SessionLocal, init_db
from apps.api.app.harness.permissions import PermissionDeniedError, PermissionPolicy
from apps.api.app.main import app
from apps.api.app.routes.chat import ChatRequest, chat_turn, get_conversation, list_conversations
from apps.api.app.routes.health import health_check
from apps.api.app.routes.jobs import DeepAnalysisRequest, get_job, list_jobs, submit_deep_analysis
from apps.api.app.routes.market import get_market_chart, get_market_fundamentals


@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "fixture")
    monkeypatch.setenv("SANDBOX_MODE", "local_restricted")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "true")
    get_settings.cache_clear()
    init_db()


def test_permission_policy_blocks_disallowed_tool_and_bad_ticker():
    policy = PermissionPolicy()
    with pytest.raises(PermissionDeniedError):
        policy.authorize_tool_call("delete_database", {})
    with pytest.raises(PermissionDeniedError):
        policy.authorize_tool_call("get_technical_analysis", {"ticker": "INVALID123!"})


def test_openapi_routes_and_health_endpoint():
    schema = app.openapi()
    paths = set(schema["paths"].keys())
    assert "/api/health" in paths
    assert "/api/chat" in paths
    assert "/api/chat/stream" in paths
    assert "/api/jobs/deep-analysis" in paths
    assert "/api/market/{ticker}/chart" in paths

    health = health_check()
    assert health["status"] == "ok"
    assert health["llm_provider"] == "mock"


def test_chat_harness_technical_comparison_and_what_if():
    with SessionLocal() as db:
        # 1. Technical analysis turn
        tech_res = chat_turn(ChatRequest(query="Show AAPL technical candlestick chart and RSI"), db=db)
        assert "AAPL" in tech_res.tickers
        assert "get_technical_analysis" in tech_res.tools_used
        assert len(tech_res.charts) >= 1
        assert len(tech_res.citations) >= 1
        assert len(tech_res.assumptions) >= 1

        # 2. Comparison turn via isolated Python sandbox
        cmp_res = chat_turn(
            ChatRequest(query="Compare AAPL vs MSFT over 3m", conversation_id=tech_res.conversation_id),
            db=db,
        )
        assert "compare_stocks_python" in cmp_res.tools_used
        assert any(c.chart_type == "comparison_line" for c in cmp_res.charts)

        # 3. What-if DCF turn via isolated Python sandbox
        dcf_res = chat_turn(
            ChatRequest(
                query="Run a what-if DCF valuation for NVDA with growth 15% and wacc 10%",
                conversation_id=tech_res.conversation_id,
            ),
            db=db,
        )
        assert "run_what_if_dcf" in dcf_res.tools_used
        assert any("Sensitivity" in t.title for t in dcf_res.tables)

        # 4. Conversation persistence
        convs = list_conversations(db=db)
        assert any(c["id"] == tech_res.conversation_id for c in convs)
        conv_detail = get_conversation(tech_res.conversation_id, db=db)
        assert len(conv_detail["messages"]) == 6


def test_market_routes_and_deep_analysis_job_endpoints():
    mkt = get_market_chart("AAPL", period="3mo", interval="1d")
    assert mkt["quote"]["ticker"] == "AAPL"
    assert len(mkt["technical"]["candles"]) == 64

    fund = get_market_fundamentals("MSFT")
    assert fund["profile"]["ticker"] == "MSFT"
    assert "income" in fund["statements"]["statements"]

    with SessionLocal() as db:
        job = submit_deep_analysis(
            DeepAnalysisRequest(tickers=["AAPL", "MSFT"], period="3mo", n_paths=300, horizon_days=30),
            db=db,
        )
        assert job["status"] == "SUCCESS"
        assert job["progress"] == 100
        assert job["result"] is not None

        fetched = get_job(job["job_id"], db=db)
        assert fetched["job_id"] == job["job_id"]
        assert any(j["job_id"] == job["job_id"] for j in list_jobs(db=db))
