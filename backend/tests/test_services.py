from datetime import date, timedelta
import math

import pytest

from app.services.ff import forward_factor, forward_vol
from app.services.occ import parse_occ_symbol
from app.services.pairing import Quote, build_pairs


# ---- Forward factor -------------------------------------------------------

def test_video_worked_example():
    # 30d IV 45%, 60d IV 35% -> forward vol ~20.6%
    fwd = forward_vol(0.45, 30, 0.35, 60)
    assert fwd == pytest.approx(0.2062, abs=1e-3)
    ff = forward_factor(0.45, 30, 0.35, 60)
    assert ff == pytest.approx(1.18, abs=0.02)


def test_matches_reference_calculator_formula():
    iv1, dte1, iv2, dte2 = 0.2475, 31, 0.2098, 45
    t1, t2 = dte1 / 365, dte2 / 365
    fwd = math.sqrt((iv2**2 * t2 - iv1**2 * t1) / (t2 - t1))
    assert forward_factor(iv1, dte1, iv2, dte2) == pytest.approx((iv1 - fwd) / fwd)


def test_flat_term_structure_gives_zero_ff():
    assert forward_factor(0.3, 30, 0.3, 60) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize(
    "args",
    [
        (0.3, 60, 0.3, 30),  # back before front
        (0.3, 30, 0.3, 30),  # same expiry
        (0.3, 0, 0.3, 30),  # expired front
        (0.0, 30, 0.3, 60),  # zero IV
        (0.9, 30, 0.2, 60),  # negative forward variance
    ],
)
def test_invalid_inputs_return_none(args):
    assert forward_factor(*args) is None


# ---- OCC parsing ----------------------------------------------------------

def test_parse_occ():
    o = parse_occ_symbol("AAPL260220C00290000")
    assert (o.underlying, o.expiration, o.option_type, o.strike) == (
        "AAPL", date(2026, 2, 20), "call", 290.0,
    )


def test_parse_occ_put_fractional_strike():
    o = parse_occ_symbol("KMI260130P00027500")
    assert o.option_type == "put" and o.strike == 27.5


def test_parse_occ_rejects_garbage():
    with pytest.raises(ValueError):
        parse_occ_symbol("AAPL")


# ---- Pairing --------------------------------------------------------------

AS_OF = date(2026, 1, 5)


def q(days, strike, iv, bid=1.0, ask=1.1):
    return Quote(AS_OF + timedelta(days=days), strike, bid, ask, iv)


def test_pairs_respect_dte_constraints():
    quotes = [
        q(10, 100, 0.40),  # front too soon (<14)
        q(20, 100, 0.35, 1.0, 1.1),
        q(30, 100, 0.30, 2.0, 2.1),  # gap 10 from 20 -> too small
        q(40, 100, 0.28, 2.5, 2.6),
        q(130, 100, 0.25, 4.0, 4.1),  # back > 120
    ]
    pairs = build_pairs(quotes, 100, AS_OF)
    got = {(p.front_dte, p.back_dte) for p in pairs}
    assert got == {(20, 40)}
    assert all(p.front_dte >= 14 and p.dte_gap >= 14 and p.back_dte <= 120 for p in pairs)
    assert all(p.dte_gap == p.back_dte - p.front_dte for p in pairs)


def test_both_legs_share_the_closest_common_strike():
    quotes = [
        q(20, 99, 0.35), q(20, 100, 0.35), q(20, 101, 0.35),
        q(50, 100, 0.30, 2.0, 2.1), q(50, 101, 0.30, 2.0, 2.1),  # no 99 in the back
    ]
    (p,) = build_pairs(quotes, 99.2, AS_OF)
    assert p.strike == 100  # 99 is closest to spot but not common to both


def test_skips_unusable_quotes_and_non_debit_pairs():
    quotes = [
        q(20, 100, 0.35, bid=0.0, ask=0.5),  # no bid
        q(50, 100, 0.30, 2.0, 2.1),
    ]
    assert build_pairs(quotes, 100, AS_OF) == []
    # back cheaper than front at mid -> not a debit calendar
    quotes = [q(20, 100, 0.35, 5.0, 5.1), q(50, 100, 0.30, 2.0, 2.1)]
    assert build_pairs(quotes, 100, AS_OF) == []


def test_debit_and_spread_pct():
    quotes = [q(20, 100, 0.35, 1.00, 1.10), q(50, 100, 0.30, 2.00, 2.20)]
    (p,) = build_pairs(quotes, 100, AS_OF)
    assert p.debit == pytest.approx(2.20 - 1.00)
    mid_debit = 2.10 - 1.05
    assert p.spread_pct == pytest.approx((0.10 + 0.20) / mid_debit)
