# AI Stock Market Assistant

Conversational AI stock market assistant combining technical analysis, fundamental research (SEC EDGAR & Yahoo Finance), isolated Python quantitative modeling, Celery background workers, and interactive charts.

## Architecture Overview
- **Frontend (`apps/web`)**: Next.js (TypeScript, Tailwind CSS) + TradingView Lightweight Charts
- **API & AI Harness (`apps/api`)**: FastAPI, permission/policy layer, context manager, tool router, SSE streaming
- **MCP Integrations (`services/mcp_market`, `services/mcp_research`)**: Model Context Protocol servers for market OHLCV/technicals and SEC EDGAR/company fundamentals
- **Python Sandbox (`services/sandbox`)**: AST-validated, Docker-isolated execution environment (`--network=none`, `--read-only`)
- **Background Workers (`services/worker`)**: Celery + Redis broker/pub-sub with progress tracking, exponential retries, and saved DB results
- **Deliverables (`docs/`)**: AWS-style architecture diagram, Jira backlog, Miro blueprint, and brief presentation outline

## Quick Start (Backend & Tests)
```bash
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[dev]"
pytest -v
uvicorn apps.api.app.main:app --reload --port 8000
```

## Quick Start (Full Stack via Docker Compose)
```bash
cp .env.example .env
docker compose up --build
```
