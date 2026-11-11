from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.db.session import init_db
from apps.api.app.routes import chat, health, jobs, market, ui


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AI Stock Market Assistant API",
    version="0.1.0",
    description="Conversational AI stock assistant with MCP integrations, Python sandbox, and Celery background jobs.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ui.router)
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(market.router)
app.include_router(jobs.router)
