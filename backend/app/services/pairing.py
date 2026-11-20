"""Build call-calendar candidates from a ticker's option quotes.

Fixes a bug in the prototype notebook: both legs of a calendar must share one
strike, so we pick the strike common to both expiries that is closest to spot
(rather than the ATM strike of each expiry independently).
"""

from dataclasses import dataclass
from datetime import date

from .ff import forward_factor, forward_vol


@dataclass(frozen=True)
class Quote:
    expiration: date
    strike: float
    bid: float
    ask: float
    iv: float


@dataclass(frozen=True)
class CalendarPair:
    strike: float
    front_expiration: date
    back_expiration: date
    front_dte: int
    back_dte: int
    dte_gap: int
    front_iv: float
    back_iv: float
    forward_vol: float
    ff: float  # ratio
    front_bid: float
    back_ask: float
    debit: float  # back ask - front bid (conservative fill)
    spread_pct: float  # (front spread + back spread) / mid debit


def _usable(q: Quote) -> bool:
    return q.iv > 0 and q.bid > 0 and q.ask >= q.bid


def build_pairs(
    quotes: list[Quote],
    spot: float,
    as_of: date,
    *,
    min_front_dte: int = 14,
    min_gap: int = 14,
    max_back_dte: int = 120,
) -> list[CalendarPair]:
    by_exp: dict[date, dict[float, Quote]] = {}
    for q in quotes:
        if _usable(q):
            by_exp.setdefault(q.expiration, {})[q.strike] = q

    expirations = sorted(by_exp)
    pairs: list[CalendarPair] = []
    for i, e1 in enumerate(expirations):
        d1 = (e1 - as_of).days
        if d1 < min_front_dte:
            continue
        for e2 in expirations[i + 1 :]:
            d2 = (e2 - as_of).days
            if d2 > max_back_dte:
                break
            if d2 - d1 < min_gap:
                continue
            common = by_exp[e1].keys() & by_exp[e2].keys()
            if not common:
                continue
            strike = min(common, key=lambda k: (abs(k - spot), k))
            front, back = by_exp[e1][strike], by_exp[e2][strike]

            ff = forward_factor(front.iv, d1, back.iv, d2)
            fwd = forward_vol(front.iv, d1, back.iv, d2)
            if ff is None or fwd is None:
                continue

            mid_debit = (back.bid + back.ask) / 2 - (front.bid + front.ask) / 2
            if mid_debit <= 0:
                continue  # not a debit calendar at mid; bad/stale quotes
            spread = (front.ask - front.bid) + (back.ask - back.bid)

            pairs.append(
                CalendarPair(
                    strike=strike,
                    front_expiration=e1,
                    back_expiration=e2,
                    front_dte=d1,
                    back_dte=d2,
                    dte_gap=d2 - d1,
                    front_iv=front.iv,
                    back_iv=back.iv,
                    forward_vol=fwd,
                    ff=ff,
                    front_bid=front.bid,
                    back_ask=back.ask,
                    debit=back.ask - front.bid,
                    spread_pct=spread / mid_debit,
                )
            )
    return pairs
