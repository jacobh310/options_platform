"""Thin wrapper around alpaca-py so the rest of the app never touches the SDK."""

from collections import defaultdict
from datetime import date, datetime
from functools import lru_cache

from alpaca.data.enums import OptionsFeed
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import OptionBarsRequest, OptionChainRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.enums import ContractType

from ..config import settings


@lru_cache
def _stock_client() -> StockHistoricalDataClient:
    return StockHistoricalDataClient(settings.alpaca_key, settings.alpaca_secret)


@lru_cache
def _option_client() -> OptionHistoricalDataClient:
    return OptionHistoricalDataClient(settings.alpaca_key, settings.alpaca_secret)


def _feed() -> OptionsFeed:
    return OptionsFeed(settings.alpaca_option_feed)


def latest_prices(symbols: list[str], batch: int = 100) -> dict[str, float]:
    """Last trade price per symbol. Symbols Alpaca doesn't return are omitted."""
    out: dict[str, float] = {}
    for i in range(0, len(symbols), batch):
        chunk = symbols[i : i + batch]
        trades = _stock_client().get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=chunk))
        out.update({sym: t.price for sym, t in trades.items()})
    return out


def option_chain(
    underlying: str,
    exp_gte: date,
    exp_lte: date,
    strike_gte: float,
    strike_lte: float,
    calls_only: bool = True,
):
    """Snapshots (quote + vendor IV) keyed by OCC contract symbol."""
    req = OptionChainRequest(
        underlying_symbol=underlying,
        feed=_feed(),
        type=ContractType.CALL if calls_only else None,
        strike_price_gte=strike_gte,
        strike_price_lte=strike_lte,
        expiration_date_gte=exp_gte,
        expiration_date_lte=exp_lte,
    )
    return _option_client().get_option_chain(req)


def option_daily_volume(
    contract_symbols: list[str], start: datetime, end: datetime, batch: int = 1000
) -> dict[date, int]:
    """Total contract volume per trading day across the given contracts."""
    totals: dict[date, int] = defaultdict(int)
    for i in range(0, len(contract_symbols), batch):
        chunk = contract_symbols[i : i + batch]
        bars = _option_client().get_option_bars(
            OptionBarsRequest(symbol_or_symbols=chunk, timeframe=TimeFrame.Day, start=start, end=end)
        )
        for series in bars.data.values():
            for bar in series:
                totals[bar.timestamp.date()] += int(bar.volume)
    return dict(totals)
