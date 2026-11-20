"""Pipeline 2: option data for the selected universe.

For each selected ticker, pull call snapshots (bid/ask + Alpaca's implied vol) within a
strike window around spot and the expiry window [min_dte, max_dte], store them against
this run, then refresh next-earnings dates from Finnhub. Forward factors are computed
at query time from the latest successful run (see services/signals.py).
"""

import time
from datetime import date, datetime, timedelta

from sqlmodel import select

from ..clients import alpaca
from ..clients.finnhub import FinnhubClient
from ..db import SessionLocal
from ..models import Earnings, OptionQuote, Ticker
from ..services.occ import parse_occ_symbol
from .runner import Reporter

DEFAULTS = {
    "min_dte": 14,
    "max_dte": 120,
    "strike_window_pct": 5.0,
}


def run(params: dict, report: Reporter) -> str:
    p = {**DEFAULTS, **params}
    min_dte, max_dte = int(p["min_dte"]), int(p["max_dte"])
    window = float(p["strike_window_pct"]) / 100
    today = date.today()

    run_id = report.run_id
    with SessionLocal() as db:
        symbols = sorted(t.symbol for t in db.exec(select(Ticker).where(Ticker.selected)))
    if not symbols:
        raise RuntimeError("No selected tickers. Run the universe pipeline first.")

    report(0.0, f"Fetching prices for {len(symbols)} tickers")
    prices = alpaca.latest_prices(symbols)

    stored, skipped = 0, []
    for i, sym in enumerate(symbols):
        report(0.02 + 0.6 * i / len(symbols), f"Option chain {sym} ({i + 1}/{len(symbols)})")
        spot = prices.get(sym)
        if not spot:
            skipped.append(sym)
            continue
        try:
            chain = alpaca.option_chain(
                sym,
                today + timedelta(days=min_dte),
                today + timedelta(days=max_dte),
                spot * (1 - window),
                spot * (1 + window),
            )
        except Exception:  # noqa: BLE001
            skipped.append(sym)
            continue

        rows = []
        for contract, snap in chain.items():
            occ = parse_occ_symbol(contract)
            quote = snap.latest_quote
            iv = snap.implied_volatility
            if occ.option_type != "call" or quote is None or not iv:
                continue
            rows.append(
                OptionQuote(
                    run_id=run_id,
                    underlying=sym,
                    contract_symbol=contract,
                    expiration=occ.expiration,
                    strike=occ.strike,
                    bid=quote.bid_price or 0.0,
                    ask=quote.ask_price or 0.0,
                    iv=float(iv),
                    underlying_price=spot,
                )
            )
        with SessionLocal() as db:
            db.add_all(rows)
            db.commit()
        stored += len(rows)
        time.sleep(0.2)  # stay well inside Alpaca's per-minute request limit

    # Earnings (Finnhub, ~1 call/sec)
    fh = FinnhubClient()
    earnings_failures = 0
    try:
        for i, sym in enumerate(symbols):
            report(0.62 + 0.37 * i / len(symbols), f"Earnings date {sym} ({i + 1}/{len(symbols)})")
            try:
                nxt = fh.next_earnings(sym, today, today + timedelta(days=max_dte + 7))
            except Exception:  # noqa: BLE001
                earnings_failures += 1
                continue
            with SessionLocal() as db:
                db.merge(Earnings(symbol=sym, next_date=nxt, updated_at=datetime.now()))
                db.commit()
    finally:
        fh.close()

    msg = f"Stored {stored:,} call quotes for {len(symbols) - len(skipped)} tickers"
    if skipped:
        msg += f"; skipped {len(skipped)} (no price/chain)"
    if earnings_failures:
        msg += f"; {earnings_failures} earnings lookups failed"
    return msg
