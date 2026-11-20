"""Pipeline 1: stock universe selection.

S&P 500 (Wikipedia) + Nasdaq-100 (Nasdaq list API) constituents -> market cap (Finnhub) -> top N by
market cap -> average daily option volume (Alpaca) -> `Ticker.selected`.

Option volume here is summed over near-the-money contracts expiring within ~45 days,
not the whole chain. It is a liquidity proxy and runs far faster than scanning every
contract; tune `min_avg_option_volume` with that in mind.
"""

import io
import statistics
from datetime import date, datetime, timedelta

import httpx
import pandas as pd
from sqlmodel import select

from ..clients import alpaca
from ..clients.finnhub import FinnhubClient
from ..db import SessionLocal
from ..models import Ticker
from .runner import Reporter

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NDX_URL = "https://api.nasdaq.com/api/quote/list-type/nasdaq100"
_UA = {"User-Agent": "Mozilla/5.0 (options-platform local app)"}

DEFAULTS = {
    "top_n": 250,
    "min_avg_option_volume": 10_000,
    "volume_lookback_days": 20,
    "market_cap_max_age_days": 7,
}


def _tables(url: str) -> list[pd.DataFrame]:
    resp = httpx.get(url, headers=_UA, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return pd.read_html(io.StringIO(resp.text))


def fetch_constituents() -> dict[str, dict]:
    """symbol -> {name, sp500, nasdaq100}. Dotted share classes (BRK.B) are skipped:
    Alpaca lists their options under a different root."""
    out: dict[str, dict] = {}

    sp = next((t for t in _tables(SP500_URL) if "Symbol" in t.columns and len(t) > 400), None)
    if sp is None:
        raise RuntimeError(f"S&P 500 constituents table not found at {SP500_URL} (page layout changed?)")
    for sym, name in zip(sp["Symbol"], sp["Security"]):
        out.setdefault(str(sym).strip(), {"name": name, "sp500": False, "nasdaq100": False})["sp500"] = True

    ndx = _nasdaq100_members()
    if len(ndx) < 90:
        raise RuntimeError(f"Expected ~100 Nasdaq-100 members, got {len(ndx)}")
    for sym, name in ndx:
        out.setdefault(sym, {"name": name, "sp500": False, "nasdaq100": False})["nasdaq100"] = True

    return {s: v for s, v in out.items() if s and "." not in s}


def _nasdaq100_members() -> list[tuple[str, str]]:
    """(symbol, name) from Nasdaq's own list endpoint. Wikipedia's Nasdaq-100 article no
    longer carries the constituents table."""
    resp = httpx.get(NDX_URL, headers={**_UA, "Accept": "application/json"}, timeout=30)
    resp.raise_for_status()
    rows = resp.json()["data"]["data"]["rows"]
    return [(r["symbol"].strip(), r["companyName"]) for r in rows]


def average_option_volume(symbol: str, spot: float, lookback_days: int) -> float | None:
    today = date.today()
    chain = alpaca.option_chain(
        symbol, today, today + timedelta(days=45), spot * 0.9, spot * 1.1, calls_only=False
    )
    if not chain:
        return None
    start = datetime.now() - timedelta(days=int(lookback_days * 1.6) + 2)
    per_day = alpaca.option_daily_volume(list(chain), start, datetime.now())
    if not per_day:
        return None
    recent = [v for _, v in sorted(per_day.items())[-lookback_days:]]
    return statistics.fmean(recent)


def run(params: dict, report: Reporter) -> str:
    p = {**DEFAULTS, **params}
    top_n = int(p["top_n"])
    min_volume = float(p["min_avg_option_volume"])
    lookback = int(p["volume_lookback_days"])
    max_age = timedelta(days=int(p["market_cap_max_age_days"]))
    now = datetime.now()

    # 1. Constituents -> tickers table
    report(0.0, "Fetching S&P 500 and Nasdaq-100 constituents")
    constituents = fetch_constituents()
    with SessionLocal() as db:
        existing = {t.symbol: t for t in db.exec(select(Ticker))}
        for sym, info in constituents.items():
            t = existing.get(sym) or Ticker(symbol=sym)
            t.name = info["name"]
            t.in_sp500, t.in_nasdaq100 = info["sp500"], info["nasdaq100"]
            db.add(t)
        for sym, t in existing.items():  # dropped from both indexes
            if sym not in constituents:
                t.in_sp500 = t.in_nasdaq100 = t.selected = False
                db.add(t)
        db.commit()
        stale = [
            t.symbol
            for t in db.exec(select(Ticker).where(Ticker.in_sp500 | Ticker.in_nasdaq100))
            if t.market_cap is None or t.market_cap_updated_at is None or now - t.market_cap_updated_at > max_age
        ]

    # 2. Market caps (Finnhub, ~1 call/sec; skips fresh values)
    fh = FinnhubClient()
    try:
        failures = 0
        for i, sym in enumerate(stale):
            report(0.02 + 0.43 * i / max(len(stale), 1), f"Market cap {sym} ({i + 1}/{len(stale)})")
            try:
                name, cap = fh.profile(sym)
            except Exception:  # noqa: BLE001 - one bad symbol shouldn't kill the run
                failures += 1
                continue
            with SessionLocal() as db:
                t = db.get(Ticker, sym)
                t.market_cap, t.market_cap_updated_at = cap, now
                t.name = name or t.name
                db.add(t)
                db.commit()
    finally:
        fh.close()

    # 3. Rank
    with SessionLocal() as db:
        ranked = db.exec(
            select(Ticker)
            .where((Ticker.in_sp500 | Ticker.in_nasdaq100) & Ticker.market_cap.is_not(None))
            .order_by(Ticker.market_cap.desc())
        ).all()
    candidates = [t.symbol for t in ranked[:top_n]]
    report(0.46, f"Ranked {len(candidates)} candidates by market cap")

    # 4. Option volume
    prices = alpaca.latest_prices(candidates)
    selected: set[str] = set()
    volumes: dict[str, float | None] = {}
    for i, sym in enumerate(candidates):
        report(0.48 + 0.5 * i / max(len(candidates), 1), f"Option volume {sym} ({i + 1}/{len(candidates)})")
        spot = prices.get(sym)
        if not spot:
            continue
        try:
            vol = average_option_volume(sym, spot, lookback)
        except Exception:  # noqa: BLE001
            vol = None
        volumes[sym] = vol
        if vol is not None and vol >= min_volume:
            selected.add(sym)

    # 5. Persist selection
    with SessionLocal() as db:
        for t in db.exec(select(Ticker)):
            t.selected = t.symbol in selected
            if t.symbol in volumes:
                t.avg_option_volume = volumes[t.symbol]
            t.updated_at = now
            db.add(t)
        db.commit()

    return (
        f"Selected {len(selected)} of {len(candidates)} tickers "
        f"(avg option volume >= {min_volume:,.0f}); {failures} market-cap lookups failed"
    )
