# Jira Backlog — AI Stock Market Assistant

## Epics Overview

| Epic Key | Epic Name | Owner Role | Target Sprint |
|---|---|---|---|
| **SMA-E1** | AI Harness, Permissions & Tool Calling Core | Backend / AI Engineer | Sprint 1 |
| **SMA-E2** | MCP Integrations (Market Data & SEC EDGAR) | Data / Integrations Engineer | Sprint 1 |
| **SMA-E3** | Isolated Python Quantitative Sandbox | Platform / Security Engineer | Sprint 1–2 |
| **SMA-E4** | Celery Background Workers & Progress Tracking | Backend / Distributed Systems | Sprint 2 |
| **SMA-E5** | Conversational UI, Interactive Charts & Tables | Frontend Engineer | Sprint 2–3 |
| **SMA-E6** | DevOps, CI/CD, AWS Architecture & Deliverables | Tech Lead / DevOps | Sprint 1–3 |

---

## Detailed Stories, Tasks & Acceptance Criteria

### SMA-E1: AI Harness, Permissions & Tool Calling Core
- **SMA-101 — Implement AI Harness Context & Workflow Orchestrator** *(Owner: Backend/AI Eng · 5 pts)*
  - **Tasks:** Build `ContextManager` for ticker entity extraction and turn history; build `AIHarness.run_turn` state machine; wire LLM planner abstraction (`mock`, `gemini`, `openai`).
  - **Acceptance Criteria:**
    - Given a user query mentioning a ticker or company name, the harness resolves the canonical ticker symbol and persists conversation history in DB.
    - Every response contains structured `narrative`, `charts`, `tables`, `citations`, `assumptions`, and `disclaimer`.
- **SMA-102 — Enforce Harness Permission Policy & Guardrails** *(Owner: Security/Backend Eng · 3 pts)*
  - **Tasks:** Implement `PermissionPolicy.authorize_tool_call` with tool allowlist, regex ticker sanitization, and AST pre-check for sandbox code.
  - **Acceptance Criteria:**
    - Disallowed tool names and malformed tickers raise `PermissionDeniedError`.
    - No raw Python script reaches the sandbox without passing AST validation.

### SMA-E2: MCP Integrations (Market Data & SEC EDGAR)
- **SMA-201 — Build `market-data-mcp` Server (`yfinance` + Technical Indicators)** *(Owner: Data Eng · 5 pts)*
  - **Tasks:** Implement `get_quote`, `get_ohlcv`, and `get_technical_indicators` (SMA 20/50, EMA 20, Bollinger Bands, RSI 14, MACD, ATR, volume ratio) with TTL cache and deterministic offline fixture fallback.
  - **Acceptance Criteria:**
    - MCP tools return normalized OHLCV candles, indicator series, trend classification, and source citations with UTC timestamps.
- **SMA-202 — Build `company-research-mcp` Server (SEC EDGAR + Financials)** *(Owner: Data Eng · 5 pts)*
  - **Tasks:** Implement `get_company_profile` (CIK + 10-K/10-Q/8-K metadata), `get_financial_statements` (Income, Balance, Cash Flow), and `get_valuation_and_earnings`.
  - **Acceptance Criteria:**
    - SEC EDGAR CIK lookup uses compliant `User-Agent` header and falls back cleanly in offline test mode.

### SMA-E3: Isolated Python Quantitative Sandbox
- **SMA-301 — Build Docker-Isolated Python Sandbox & AST Validator** *(Owner: Platform Eng · 8 pts)*
  - **Tasks:** Author `Dockerfile.sandbox` (`python:3.11-slim`, non-root UID 65534, `numpy`/`pandas`/`scipy`); implement `ast_guard.py` and `DockerSandboxRunner` (`--network none`, `--read-only`, CPU/memory/PID caps, timeouts).
  - **Acceptance Criteria:**
    - Scripts importing `os`, `subprocess`, `socket`, or calling `open()`/`eval()` are rejected before execution.
    - Validated scripts return JSON `outputs` and `execution_ms` within timeout.
- **SMA-302 — Implement Quantitative Templates (Comparison, DCF What-If, Monte Carlo)** *(Owner: Quant/Backend Eng · 5 pts)*
  - **Tasks:** Write and test `STOCK_COMPARISON_SCRIPT`, `DCF_WHAT_IF_SCRIPT` (with WACC vs terminal growth sensitivity matrix), and `MONTE_CARLO_SCRIPT`.
  - **Acceptance Criteria:**
    - All three templates execute deterministically in sandbox tests and produce chart/table-ready JSON outputs.

### SMA-E4: Celery Background Workers & Progress Tracking
- **SMA-401 — Configure Celery + Redis Worker & Deep Analysis Task** *(Owner: Backend Eng · 5 pts)*
  - **Tasks:** Configure `celery_app.py`, `run_deep_analysis_task` with `max_retries=3` and exponential backoff, Redis Pub/Sub progress events, and DB persistence in `AnalysisJob`.
  - **Acceptance Criteria:**
    - Task updates DB & publishes progress stages (`10%`, `45%`, `75%`, `100%`) and persists the final `AnalysisResponse` JSON.
- **SMA-402 — Expose Job Submission & SSE Progress Streaming Endpoints** *(Owner: Backend Eng · 3 pts)*
  - **Tasks:** Implement `POST /api/jobs/deep-analysis`, `GET /api/jobs`, `GET /api/jobs/{job_id}`, and `GET /api/jobs/{job_id}/stream`.
  - **Acceptance Criteria:**
    - Clients can submit a job, stream live progress over SSE, and retrieve saved results after completion.

### SMA-E5: Conversational UI, Interactive Charts & Tables
- **SMA-501 — Build Next.js Conversational Workspace & Quick Prompts** *(Owner: Frontend Eng · 5 pts)*
  - **Tasks:** Create `ChatWorkspace.tsx`, message stream, prompt chips, and `CitationsDrawer.tsx` displaying sources, timestamps, and model assumptions.
  - **Acceptance Criteria:**
    - Users can run technical, fundamental, comparison, what-if, and deep background queries from one conversational UI.
- **SMA-502 — Integrate TradingView Lightweight Charts & Sortable Financial Tables** *(Owner: Frontend Eng · 5 pts)*
  - **Tasks:** Build `CandlestickChart.tsx` (candlesticks, volume histogram, toggleable overlays, RSI/MACD sub-pane) and `DataTableCard.tsx` (sortable columns), plus `JobTracker.tsx`.
  - **Acceptance Criteria:**
    - Users can toggle indicator overlays, sort financial/sensitivity tables, and load saved Celery job reports into the workspace.

### SMA-E6: DevOps, CI/CD, AWS Architecture & Deliverables
- **SMA-601 — GitHub Actions CI, Docker Compose & PR Template** *(Owner: DevOps Lead · 3 pts)*
  - **Tasks:** Configure `.github/workflows/ci.yml` (`ruff`, `pytest`, sandbox Docker build, Next.js `tsc` + `build`), `docker-compose.yml`, and PR template.
  - **Acceptance Criteria:**
    - Every PR triggers automated lint, unit/integration tests, and container/frontend build checks.
- **SMA-602 — Architecture Diagram, Miro Blueprint & Presentation Deck** *(Owner: Tech Lead · 3 pts)*
  - **Tasks:** Author AWS-style Mermaid architecture, Jira JSON/Markdown exports, Miro research/journey/wireframe blueprint, and presentation deck outline.
  - **Acceptance Criteria:**
    - All 5 brief deliverables exist in `docs/` and align with the implemented codebase.
