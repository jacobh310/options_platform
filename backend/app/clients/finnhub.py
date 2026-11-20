"""Finnhub client: market cap (profile2) and next earnings date.

The free tier allows 60 calls/minute, so calls are throttled to ~1 per second
and 429s are retried.
"""

import time
from datetime import date

import httpx

from ..config import settings

BASE = "https://finnhub.io/api/v1"
_MIN_INTERVAL = 1.05


class FinnhubClient:
    def __init__(self) -> None:
        if not settings.finnhub_key:
            raise RuntimeError("FINNHUB_KEY is not set (see .env)")
        self._http = httpx.Client(
            base_url=BASE, timeout=20, headers={"X-Finnhub-Token": settings.finnhub_key}
        )
        self._last_call = 0.0

    def close(self) -> None:
        self._http.close()

    def _get(self, path: str, **params) -> dict:
        for attempt in range(4):
            wait = _MIN_INTERVAL - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            resp = self._http.get(path, params=params)
            if resp.status_code == 429:
                time.sleep(2 + 2 * attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"Finnhub rate limit not clearing for {path}")

    def profile(self, symbol: str) -> tuple[str | None, float | None]:
        """(name, market cap in USD). Finnhub reports market cap in millions."""
        data = self._get("/stock/profile2", symbol=symbol)
        cap = data.get("marketCapitalization")
        return data.get("name"), (float(cap) * 1_000_000 if cap else None)

    def next_earnings(self, symbol: str, start: date, end: date) -> date | None:
        data = self._get(
            "/calendar/earnings", symbol=symbol, **{"from": start.isoformat(), "to": end.isoformat()}
        )
        dates = sorted(
            date.fromisoformat(r["date"]) for r in data.get("earningsCalendar", []) if r.get("date")
        )
        dates = [d for d in dates if d >= start]
        return dates[0] if dates else None
