"""Run bookkeeping shared by all pipelines."""

import traceback
from collections.abc import Callable
from datetime import datetime

from sqlmodel import col, select

from ..db import SessionLocal
from ..models import PipelineRun

PIPELINES = ("universe", "options")
ACTIVE = ("queued", "running")


class Reporter:
    """Lets a pipeline publish progress (0..1) and a status message to its run row."""

    def __init__(self, run_id: int) -> None:
        self.run_id = run_id

    def __call__(self, progress: float, message: str) -> None:
        with SessionLocal() as db:
            run = db.get(PipelineRun, self.run_id)
            run.progress = min(max(progress, 0.0), 1.0)
            run.message = message[:500]
            db.add(run)
            db.commit()


def create_run(pipeline: str, params: dict) -> PipelineRun | None:
    """Create a queued run, or return None if any pipeline run is already active."""
    with SessionLocal() as db:
        active = db.exec(select(PipelineRun).where(col(PipelineRun.status).in_(ACTIVE))).first()
        if active is not None:
            return None
        run = PipelineRun(pipeline=pipeline, status="queued", params=params)
        db.add(run)
        db.commit()
        db.refresh(run)
        return run


def execute(run_id: int, fn: Callable[[dict, Reporter], str]) -> None:
    """Run `fn(params, report)` and record the outcome. `fn` returns a final message."""
    with SessionLocal() as db:
        run = db.get(PipelineRun, run_id)
        params = dict(run.params or {})
        run.status = "running"
        run.started_at = datetime.now()
        db.add(run)
        db.commit()

    report = Reporter(run_id)
    try:
        final_message = fn(params, report)
        status, error = "succeeded", None
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI
        traceback.print_exc()
        final_message, status, error = None, "failed", f"{type(exc).__name__}: {exc}"[:2000]

    with SessionLocal() as db:
        run = db.get(PipelineRun, run_id)
        run.status = status
        run.error = error
        run.finished_at = datetime.now()
        if status == "succeeded":
            run.progress = 1.0
            run.message = final_message
        db.add(run)
        db.commit()


def mark_interrupted_runs() -> None:
    """A server restart kills background threads, so runs left active can never finish."""
    with SessionLocal() as db:
        for run in db.exec(select(PipelineRun).where(col(PipelineRun.status).in_(ACTIVE))):
            run.status = "failed"
            run.error = "Interrupted by server restart"
            run.finished_at = datetime.now()
            db.add(run)
        db.commit()
