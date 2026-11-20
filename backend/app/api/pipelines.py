from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from ..db import get_db
from ..models import PipelineRun, Ticker
from ..pipelines import options as options_pipeline
from ..pipelines import runner
from ..pipelines import universe as universe_pipeline

router = APIRouter(prefix="/api", tags=["pipelines"])


class UniverseParams(BaseModel):
    top_n: int = Field(250, ge=1, le=600)
    min_avg_option_volume: float = Field(10_000, ge=0)
    volume_lookback_days: int = Field(20, ge=1, le=60)
    market_cap_max_age_days: int = Field(7, ge=0, description="Reuse market caps newer than this")


class OptionsParams(BaseModel):
    min_dte: int = Field(14, ge=1)
    max_dte: int = Field(120, ge=2)
    strike_window_pct: float = Field(5.0, gt=0, le=50, description="Strikes within +/- this % of spot")


def _start(pipeline: str, params: BaseModel, fn, background: BackgroundTasks) -> PipelineRun:
    run = runner.create_run(pipeline, params.model_dump())
    if run is None:
        raise HTTPException(409, "A pipeline is already running. Wait for it to finish.")
    background.add_task(runner.execute, run.id, fn)
    return run


@router.post("/pipelines/universe/run", response_model=PipelineRun, status_code=202)
def run_universe(params: UniverseParams, background: BackgroundTasks):
    return _start("universe", params, universe_pipeline.run, background)


@router.post("/pipelines/options/run", response_model=PipelineRun, status_code=202)
def run_options(params: OptionsParams, background: BackgroundTasks):
    return _start("options", params, options_pipeline.run, background)


@router.get("/pipelines/runs", response_model=list[PipelineRun])
def list_runs(limit: int = 20, db: Session = Depends(get_db)):
    return db.exec(select(PipelineRun).order_by(col(PipelineRun.id).desc()).limit(limit)).all()


@router.get("/pipelines/runs/{run_id}", response_model=PipelineRun)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(PipelineRun, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/universe", response_model=list[Ticker])
def get_universe(selected_only: bool = True, db: Session = Depends(get_db)):
    stmt = select(Ticker).order_by(col(Ticker.market_cap).desc())
    if selected_only:
        stmt = stmt.where(Ticker.selected)
    return db.exec(stmt).all()
