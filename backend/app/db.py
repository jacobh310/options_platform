from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine

from .config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    db_path = settings.database_url.removeprefix("sqlite:///")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        # WAL lets the API read while a pipeline is writing.
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=10000")
        cur.close()


SessionLocal = sessionmaker(engine, class_=Session, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(engine)
