from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CandlestickPoint(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class LinePoint(BaseModel):
    time: str
    value: float | None = None


class IndicatorSeries(BaseModel):
    name: str
    pane: Literal["overlay", "oscillator"] = "overlay"
    color: str = "#38bdf8"
    points: list[LinePoint] = Field(default_factory=list)


class ChartSpec(BaseModel):
    id: str
    title: str
    ticker: str
    chart_type: Literal["candlestick", "comparison_line", "projection_cone"] = "candlestick"
    candlesticks: list[CandlestickPoint] = Field(default_factory=list)
    series: list[IndicatorSeries] = Field(default_factory=list)
    subtitle: str | None = None


class TableSpec(BaseModel):
    id: str
    title: str
    columns: list[str]
    rows: list[list[Any]]
    subtitle: str | None = None


class Citation(BaseModel):
    source: str
    label: str
    url: str | None = None
    retrieved_at: str = Field(default_factory=utc_now_iso)


class Assumption(BaseModel):
    key: str
    value: str
    rationale: str | None = None


class AnalysisResponse(BaseModel):
    conversation_id: str
    message_id: str
    narrative: str
    tickers: list[str] = Field(default_factory=list)
    charts: list[ChartSpec] = Field(default_factory=list)
    tables: list[TableSpec] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    job_id: str | None = None
    disclaimer: str = (
        "Informational analysis only — not personalized financial or investment advice. "
        "Verify figures against primary SEC filings before making investment decisions."
    )


class JobStatus(str, Enum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    PROGRESS = "PROGRESS"
    RETRY = "RETRY"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class JobProgressEvent(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    stage: str
    message: str
    retries: int = 0
    updated_at: str = Field(default_factory=utc_now_iso)


class SandboxRequest(BaseModel):
    code: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=15, ge=1, le=120)


class SandboxResult(BaseModel):
    success: bool
    mode: Literal["docker", "local_restricted"]
    outputs: dict[str, Any] = Field(default_factory=dict)
    stdout: str = ""
    error: str | None = None
    execution_ms: int = 0
