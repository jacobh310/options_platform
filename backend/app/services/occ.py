"""OCC option symbol parsing, e.g. AAPL260220C00290000."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class OccSymbol:
    underlying: str
    expiration: date
    option_type: str  # "call" | "put"
    strike: float


def parse_occ_symbol(symbol: str) -> OccSymbol:
    s = symbol.strip()
    if len(s) < 16:
        raise ValueError(f"Not an OCC symbol: {symbol!r}")
    tail = s[-15:]  # YYMMDD + C/P + 8-digit strike (x1000)
    underlying = s[:-15].lstrip("1")  # some feeds prefix adjusted roots with '1'
    expiration = date(2000 + int(tail[0:2]), int(tail[2:4]), int(tail[4:6]))
    cp = tail[6]
    if cp not in ("C", "P"):
        raise ValueError(f"Not an OCC symbol: {symbol!r}")
    return OccSymbol(
        underlying=underlying,
        expiration=expiration,
        option_type="call" if cp == "C" else "put",
        strike=int(tail[7:]) / 1000.0,
    )
