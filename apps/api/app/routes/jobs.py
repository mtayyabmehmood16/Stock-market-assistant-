from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.db.models import AnalysisJob
from apps.api.app.db.session import SessionLocal, get_db
from apps.api.app.harness.workflow import serialize_sse
from services.worker.tasks import run_deep_analysis_task

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class DeepAnalysisRequest(BaseModel):
    tickers: list[str] = Field(min_length=1, max_length=5)
    period: str = "6mo"
    horizon_days: int = Field(default=90, ge=10, le=365)
    n_paths: int = Field(default=2000, ge=200, le=10000)
    fcf_growth_rate: float = 0.12
    wacc: float = 0.09
    terminal_growth: float = 0.03


@router.post("/deep-analysis")
def submit_deep_analysis(req: DeepAnalysisRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    clean_tickers = [t.strip().upper() for t in req.tickers if t.strip()]
    job_id = str(uuid.uuid4())
    params = req.model_dump(exclude={"tickers"})

    job = AnalysisJob(
        id=job_id,
        job_type="deep_analysis",
        tickers_json=json.dumps(clean_tickers),
        params_json=json.dumps(params),
        status="PENDING",
        progress=0,
        stage="queued",
        message=f"Queued deep analysis for {', '.join(clean_tickers)}",
    )
    db.add(job)
    db.commit()

    run_deep_analysis_task.delay(
        job_id=job_id,
        tickers=clean_tickers,
        analysis_type="peer_and_what_if",
        params=params,
    )

    db.refresh(job)
    return _serialize_job(job)


@router.get("")
def list_jobs(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(AnalysisJob).order_by(AnalysisJob.created_at.desc()).limit(25)).all()
    return [_serialize_job(j) for j in rows]


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    job = db.get(AnalysisJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _serialize_job(job)


@router.get("/{job_id}/stream")
async def stream_job_progress(job_id: str) -> StreamingResponse:
    async def event_stream():
        last_key = None
        for _ in range(60):
            with SessionLocal() as db:
                job = db.get(AnalysisJob, job_id)
                if job is None:
                    yield serialize_sse("error", {"message": "Job not found"})
                    return
                key = (job.status, job.progress, job.stage)
                if key != last_key:
                    yield serialize_sse("progress", _serialize_job(job))
                    last_key = key
                if job.status in {"SUCCESS", "FAILURE"}:
                    return
            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _serialize_job(job: AnalysisJob) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "job_type": job.job_type,
        "tickers": json.loads(job.tickers_json or "[]"),
        "status": job.status,
        "progress": job.progress,
        "stage": job.stage,
        "message": job.message,
        "retries": job.retries,
        "result": json.loads(job.result_json) if job.result_json else None,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }
