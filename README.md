# Options Platform

Forward Factor call-calendar screener. FastAPI + SQLite backend, React + TypeScript frontend.
Background and strategy notes: [docs/forward_factor_summary.md](docs/forward_factor_summary.md).

## Setup

API keys go in the repo-root `.env` (see `.env.example`): `ALPACA_KEY`, `ALPACA_SECRET`, `FINNHUB_KEY`.

```bash
# backend (uv)
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000   # API docs at http://localhost:8000/docs

# frontend (separate terminal)
cd frontend
npm install
npm run dev                                         # http://localhost:5173 (proxies /api to :8000)
```

Tests: `cd backend && uv run pytest`

## Using it

1. Open **Data Pipelines**. Run **1. Stock universe** (the first run takes several minutes: Finnhub
   market caps are throttled to about 1 call/second; later runs reuse cached values).
2. Run **2. Option data** to pull call quotes, Alpaca IV and earnings dates for the selected tickers.
3. Open **Forward Factor Screener**. Thresholds and DTE rules are UI filters applied at query time, so
   changing them never re-runs a pipeline.

## Layout

```
backend/app/
  api/         FastAPI routes (pipelines, signals)
  clients/     Alpaca and Finnhub wrappers
  pipelines/   universe.py, options.py, runner.py (run tracking)
  services/    ff.py (math), pairing.py (calendar pairs), signals.py, occ.py
  models.py    SQLModel tables
frontend/src/  pages/Screener.tsx, pages/Pipelines.tsx, api.ts
```

## Notes

- Free Alpaca plan = `indicative` option feed, so quotes and IV are approximate. Set
  `ALPACA_OPTION_FEED=opra` once on a paid plan.
- Tables are created with `create_all` on startup. Add Alembic migrations before the schema needs to change
  with data you want to keep.
