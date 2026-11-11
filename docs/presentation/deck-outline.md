# Presentation Deck Outline — AI Stock Market Assistant

## Slide 1: Title & Problem Statement
- **Title:** AlphaPulse AI — Conversational Stock Market Research & Quantitative Assistant
- **Problem:** Retail and institutional analysts juggle fragmented tools for charts, SEC filings, and Excel what-if models, while generic AI chats lack live data grounding, reproducible math, and auditability.
- **Solution:** One conversational workspace unifying **MCP market/company data**, **isolated Python calculations**, **interactive charts/tables**, and **Celery background execution**.

## Slide 2: Core Product Features
- **Technical Analysis:** Interactive candlestick & volume charts with toggleable SMA 20/50, EMA 20, Bollinger Bands, RSI 14, and MACD.
- **Fundamental Research:** SEC EDGAR filings metadata (10-K/10-Q/8-K), Income/Balance/Cash Flow statements, margins, ROE, and valuation multiples.
- **Python-Powered Modeling:** Normalized multi-stock risk/return comparisons, 5-year DCF projections, WACC vs. terminal-growth sensitivity grids, and Monte Carlo simulations.
- **Trust & Explainability:** Expandable Sources, UTC timestamps, explicit model assumptions, and informational disclaimer on every response.

## Slide 3: Technical Implementation — AI Harness & MCP
- **AI Harness (`apps/api/app/harness/`):** Coordinates LLM planning, conversation ticker context, permission guardrails, and structured response formatting.
- **MCP Integrations (`services/mcp_market`, `services/mcp_research`):** Standardized Model Context Protocol servers wrapping `yfinance` and SEC EDGAR APIs with TTL caching and offline test fixtures.
- **Tool Calling:** Strongly typed JSON-schema tools (`get_technical_analysis`, `get_fundamental_research`, `compare_stocks_python`, `run_what_if_dcf`, `enqueue_deep_analysis`).

## Slide 4: Security & Scale — Python Sandbox & Celery Workers
- **Isolated Python Sandbox (`services/sandbox/`):**
  - AST pre-validation blocks dangerous imports (`os`, `subprocess`, `socket`) and builtins (`open`, `eval`, `exec`).
  - Runs in ephemeral Docker container (`--network none`, `--read-only`, 1 CPU, 512 MB RAM, non-root UID 65534).
- **Background Processing (`services/worker/`):**
  - Celery + Redis broker/pub-sub for long-running multi-ticker & Monte Carlo jobs.
  - Real-time SSE progress streaming (`10% -> 45% -> 75% -> 100%`), exponential backoff retries (`max_retries=3`), and persisted DB reports.

## Slide 5: AWS-Style Cloud Architecture
- Walk through `docs/architecture/aws-architecture.md`:
  - CloudFront + WAF -> ALB -> ECS Fargate (`FastAPI` + `MCP` + `Celery Workers`) -> ElastiCache Redis -> Isolated Sandbox Tasks -> RDS PostgreSQL + S3 + CloudWatch.

## Slide 6: Live Demo Script (3–4 Minutes)
1. **Technical Query:** *"Show AAPL technical candlestick chart, RSI, MACD, and volume"* -> Highlight interactive chart toggles and indicator table.
2. **Fundamental Query:** *"Analyze MSFT fundamentals, financial statements, and valuation"* -> Show SEC filing citations & income statement table.
3. **Python What-If DCF:** *"Run a what-if DCF valuation for NVDA with growth 18% and WACC 9.5%"* -> Inspect sensitivity grid & explicit assumptions drawer.
4. **Background Celery Job:** *"Run a deep background Monte Carlo and peer analysis for AAPL and MSFT"* -> Watch live progress bar reach 100% and click **Load Report**.
