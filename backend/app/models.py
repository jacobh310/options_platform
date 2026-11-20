"""Database tables. SQLModel classes are Pydantic models and SQLAlchemy tables at once."""

from datetime import date, datetime

from pydantic import NaiveDatetime
from sqlalchemy import JSON, Column, Index
from sqlmodel import Field, SQLModel


class Ticker(SQLModel, table=True):
    """A stock considered by the universe pipeline. `selected` marks the current universe."""

    __tablename__ = "tickers"

    symbol: str = Field(primary_key=True, max_length=16)
    name: str | None = None
    market_cap: float | None = None  # USD
    market_cap_updated_at: NaiveDatetime | None = None
    avg_option_volume: float | None = None
    in_sp500: bool = False
    in_nasdaq100: bool = False
    selected: bool = Field(default=False, index=True)
    updated_at: NaiveDatetime | None = None


class PipelineRun(SQLModel, table=True):
    __tablename__ = "pipeline_runs"

    id: int | None = Field(default=None, primary_key=True)
    pipeline: str = Field(index=True)  # "universe" | "options"
    status: str = "queued"  # queued | running | succeeded | failed
    params: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    progress: float = 0.0  # 0..1
    message: str | None = None
    error: str | None = None
    started_at: NaiveDatetime = Field(default_factory=datetime.now)
    finished_at: NaiveDatetime | None = None


class OptionQuote(SQLModel, table=True):
    """One call contract captured by an options pipeline run."""

    __tablename__ = "option_quotes"
    __table_args__ = (Index("ix_option_quotes_run_underlying", "run_id", "underlying"),)

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="pipeline_runs.id")
    underlying: str
    contract_symbol: str
    expiration: date
    strike: float
    bid: float
    ask: float
    iv: float  # decimal, e.g. 0.25
    underlying_price: float


class Earnings(SQLModel, table=True):
    """Next known earnings date per symbol (refreshed by the options pipeline)."""

    __tablename__ = "earnings"

    symbol: str = Field(primary_key=True, max_length=16)
    next_date: date | None = None
    updated_at: NaiveDatetime = Field(default_factory=datetime.now)
