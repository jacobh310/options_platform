"""Forward volatility and Forward Factor math.

Matches references/calculator.py:
    T = DTE / 365, IV as a decimal (0.25 = 25%)
    forward_variance = (iv2^2 * T2 - iv1^2 * T1) / (T2 - T1)
    forward_vol      = sqrt(forward_variance)
    FF               = (iv1 - forward_vol) / forward_vol      (a ratio; x100 for %)

FF > 0 means the front month is rich vs the forward vol (backwardation).
"""

import math


def forward_vol(iv1: float, dte1: float, iv2: float, dte2: float) -> float | None:
    """Annualized forward vol between two expiries, or None if inputs are invalid."""
    if dte1 <= 0 or dte2 <= dte1 or iv1 <= 0 or iv2 <= 0:
        return None
    t1, t2 = dte1 / 365.0, dte2 / 365.0
    fwd_var = (iv2**2 * t2 - iv1**2 * t1) / (t2 - t1)
    if fwd_var <= 0:
        return None  # inconsistent term structure: no real forward vol
    return math.sqrt(fwd_var)


def forward_factor(iv1: float, dte1: float, iv2: float, dte2: float) -> float | None:
    """(front IV - forward vol) / forward vol as a ratio, or None if undefined."""
    fwd = forward_vol(iv1, dte1, iv2, dte2)
    if fwd is None or fwd == 0:
        return None
    return (iv1 - fwd) / fwd
