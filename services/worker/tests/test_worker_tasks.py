from __future__ import annotations

import json
import uuid

from apps.api.app.db.models import AnalysisJob
from apps.api.app.db.session import SessionLocal, init_db
from services.worker.tasks import run_deep_analysis_task


def test_celery_deep_analysis_task_eager_execution(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "fixture")
    monkeypatch.setenv("SANDBOX_MODE", "local_restricted")
    init_db()

    job_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(
            AnalysisJob(
                id=job_id,
                job_type="deep_analysis",
                tickers_json=json.dumps(["AAPL", "NVDA"]),
                params_json=json.dumps({"period": "3mo"}),
                status="PENDING",
                progress=0,
                stage="queued",
                message="Queued",
            )
        )
        db.commit()

    res = run_deep_analysis_task.delay(
        job_id=job_id,
        tickers=["AAPL", "NVDA"],
        analysis_type="peer_and_what_if",
        params={"period": "3mo", "n_paths": 300, "horizon_days": 30},
    ).get()

    assert res["job_id"] == job_id
    assert len(res["charts"]) == 1
    assert len(res["tables"]) == 3

    with SessionLocal() as db:
        saved = db.get(AnalysisJob, job_id)
        assert saved is not None
        assert saved.status == "SUCCESS"
        assert saved.progress == 100
        assert saved.result_json is not None
