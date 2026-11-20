from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.db import SessionLocal, init_db
from app.main import app
from app.models import Earnings, OptionQuote, PipelineRun
from app.pipelines import runner


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    with SessionLocal() as db:
        for model in (OptionQuote, Earnings, PipelineRun):
            for row in db.exec(select(model)):
                db.delete(row)
        db.commit()


def seed(front_iv=0.40, back_iv=0.30, earnings_in_days=None):
    today = date.today()
    with SessionLocal() as db:
        run = PipelineRun(
            pipeline="options", status="succeeded", started_at=datetime.now(), params={}
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        for days, iv, bid, ask in [(21, front_iv, 1.00, 1.05), (56, back_iv, 2.00, 2.10)]:
            db.add(
                OptionQuote(
                    run_id=run.id, underlying="TEST", contract_symbol=f"TEST{days}",
                    expiration=today + timedelta(days=days), strike=100.0,
                    bid=bid, ask=ask, iv=iv, underlying_price=100.2,
                )
            )
        if earnings_in_days is not None:
            db.add(Earnings(symbol="TEST", next_date=today + timedelta(days=earnings_in_days)))
        db.commit()


def test_health():
    with TestClient(app) as c:
        assert c.get("/api/health").json()["status"] == "ok"


def test_signals_empty_before_any_run():
    with TestClient(app) as c:
        body = c.get("/api/signals").json()
    assert body["run_id"] is None and body["signals"] == []


def test_signals_returns_gap_and_ff_and_filters_by_threshold():
    seed()
    with TestClient(app) as c:
        body = c.get("/api/signals").json()
        (s,) = body["signals"]
        assert s["dte_gap"] == 35 and s["front_dte"] == 21 and s["back_dte"] == 56
        assert s["ff_pct"] > 0
        assert c.get("/api/signals", params={"min_ff_pct": s["ff_pct"] + 1}).json()["signals"] == []
        assert c.get("/api/signals", params={"min_gap": 40}).json()["signals"] == []


def test_earnings_flags_and_exclusion():
    seed(earnings_in_days=30)  # after front expiry (21d), before back expiry (56d)
    with TestClient(app) as c:
        (s,) = c.get("/api/signals").json()["signals"]
        assert s["earnings_before_back"] is True and s["earnings_before_front"] is False
        assert s["days_to_earnings"] == 30
        assert c.get("/api/signals", params={"exclude_earnings": True}).json()["signals"] == []


def test_only_one_active_run_at_a_time():
    first = runner.create_run("universe", {})
    assert first is not None
    assert runner.create_run("options", {}) is None  # blocked while first is queued


def test_interrupted_runs_are_failed_on_restart():
    run = runner.create_run("universe", {})
    runner.mark_interrupted_runs()
    with SessionLocal() as db:
        assert db.get(PipelineRun, run.id).status == "failed"
    assert runner.create_run("options", {}) is not None
