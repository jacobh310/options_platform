from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from ..db import get_db
from ..services.signals import SignalsResponse, compute_signals

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("", response_model=SignalsResponse)
def list_signals(
    min_ff_pct: float = Query(0, description="Minimum Forward Factor, in percent"),
    min_front_dte: int = Query(14, ge=1),
    min_gap: int = Query(14, ge=1, description="Minimum days between front and back expiry"),
    max_back_dte: int = Query(120, ge=1),
    max_spread_pct: float | None = Query(None, ge=0, description="Max combined bid/ask spread as % of mid debit"),
    exclude_earnings: bool = Query(False, description="Hide pairs with earnings on or before the back expiry"),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    return compute_signals(
        db,
        min_ff_pct=min_ff_pct,
        min_front_dte=min_front_dte,
        min_gap=min_gap,
        max_back_dte=max_back_dte,
        max_spread_pct=max_spread_pct,
        exclude_earnings=exclude_earnings,
        limit=limit,
    )
