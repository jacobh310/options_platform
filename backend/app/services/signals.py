"""Compute forward-factor calendar signals from the latest successful options run."""

from collections import defaultdict
from datetime import date

from pydantic import BaseModel
from sqlmodel import Session, select

from ..models import Earnings, OptionQuote, PipelineRun
from .pairing import Quote, build_pairs


class Signal(BaseModel):
    underlying: str
    spot: float
    strike: float
    front_expiration: date
    back_expiration: date
    front_dte: int
    back_dte: int
    dte_gap: int
    front_iv: float
    back_iv: float
    forward_vol_pct: float
    ff_pct: float
    debit: float
    spread_pct: float
    earnings_date: date | None
    days_to_earnings: int | None
    earnings_before_front: bool
    earnings_before_back: bool


class SignalsResponse(BaseModel):
    run_id: int | None
    as_of: str | None
    total_pairs: int  # before the min FF / spread / earnings filters
    signals: list[Signal]


def latest_options_run(db: Session) -> PipelineRun | None:
    return db.exec(
        select(PipelineRun)
        .where(PipelineRun.pipeline == "options", PipelineRun.status == "succeeded")
        .order_by(PipelineRun.id.desc())
    ).first()


def compute_signals(
    db: Session,
    *,
    min_ff_pct: float,
    min_front_dte: int,
    min_gap: int,
    max_back_dte: int,
    max_spread_pct: float | None,
    exclude_earnings: bool,
    limit: int,
) -> SignalsResponse:
    run = latest_options_run(db)
    if run is None:
        return SignalsResponse(run_id=None, as_of=None, total_pairs=0, signals=[])

    as_of = run.started_at.date()
    quotes: dict[str, list[Quote]] = defaultdict(list)
    spot: dict[str, float] = {}
    for r in db.exec(select(OptionQuote).where(OptionQuote.run_id == run.id)):
        quotes[r.underlying].append(Quote(r.expiration, r.strike, r.bid, r.ask, r.iv))
        spot[r.underlying] = r.underlying_price
    earnings = {e.symbol: e.next_date for e in db.exec(select(Earnings))}

    out: list[Signal] = []
    total = 0
    for sym, qs in quotes.items():
        e_date = earnings.get(sym)
        for p in build_pairs(
            qs, spot[sym], as_of, min_front_dte=min_front_dte, min_gap=min_gap, max_back_dte=max_back_dte
        ):
            total += 1
            before_back = e_date is not None and as_of <= e_date <= p.back_expiration
            before_front = e_date is not None and as_of <= e_date <= p.front_expiration
            ff_pct = p.ff * 100
            if ff_pct < min_ff_pct:
                continue
            if max_spread_pct is not None and p.spread_pct * 100 > max_spread_pct:
                continue
            if exclude_earnings and before_back:
                continue
            out.append(
                Signal(
                    underlying=sym,
                    spot=spot[sym],
                    strike=p.strike,
                    front_expiration=p.front_expiration,
                    back_expiration=p.back_expiration,
                    front_dte=p.front_dte,
                    back_dte=p.back_dte,
                    dte_gap=p.dte_gap,
                    front_iv=p.front_iv,
                    back_iv=p.back_iv,
                    forward_vol_pct=p.forward_vol * 100,
                    ff_pct=ff_pct,
                    debit=p.debit,
                    spread_pct=p.spread_pct * 100,
                    earnings_date=e_date,
                    days_to_earnings=(e_date - as_of).days if e_date else None,
                    earnings_before_front=before_front,
                    earnings_before_back=before_back,
                )
            )

    out.sort(key=lambda s: s.ff_pct, reverse=True)
    return SignalsResponse(run_id=run.id, as_of=run.started_at.isoformat(), total_pairs=total, signals=out[:limit])
