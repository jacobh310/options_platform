# Database Schema

SQLite for the local MVP, at `data/options.db` (repo root, git-ignored). Tables are defined as SQLModel
classes in [backend/app/models.py](../backend/app/models.py) and created on API startup with `create_all`.
There are no migrations yet; add Alembic before changing the schema with data you want to keep.

The database URL is set by `DATABASE_URL` (default: the SQLite file above), so moving to Postgres later is
a configuration change.

## Tables

### `tickers`

Every S&P 500 and Nasdaq-100 stock the universe pipeline has seen.

| Column | Type | Notes |
|---|---|---|
| `symbol` | VARCHAR(16) | Primary key |
| `name` | VARCHAR | |
| `market_cap` | FLOAT | USD, from Finnhub |
| `market_cap_updated_at` | DATETIME | Lets runs reuse recent values |
| `avg_option_volume` | FLOAT | Average daily contracts from the volume step |
| `in_sp500` | BOOLEAN | |
| `in_nasdaq100` | BOOLEAN | |
| `selected` | BOOLEAN | Indexed. True means the ticker is in the current universe |
| `updated_at` | DATETIME | |

### `pipeline_runs`

One row per pipeline run.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | Primary key |
| `pipeline` | VARCHAR | `universe` or `options`. Indexed |
| `status` | VARCHAR | `queued`, `running`, `succeeded` or `failed` |
| `params` | JSON | Settings the run was started with |
| `progress` | FLOAT | 0 to 1 |
| `message` | VARCHAR | Latest progress message, or final summary |
| `error` | VARCHAR | Set when `status` is `failed` |
| `started_at` | DATETIME | |
| `finished_at` | DATETIME | Null while active |

Only one run can be `queued` or `running` at a time. On API startup, any run left active is marked `failed`
("Interrupted by server restart").

### `option_quotes`

One call contract per row, tied to the options run that fetched it.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | Primary key |
| `run_id` | INTEGER | Foreign key to `pipeline_runs.id` |
| `underlying` | VARCHAR | Ticker symbol |
| `contract_symbol` | VARCHAR | OCC symbol, e.g. `AAPL261204C00360000` |
| `expiration` | DATE | |
| `strike` | FLOAT | |
| `bid` | FLOAT | |
| `ask` | FLOAT | |
| `iv` | FLOAT | Vendor (Alpaca) implied vol as a decimal, so 0.25 means 25% |
| `underlying_price` | FLOAT | Spot at fetch time |

Index: `ix_option_quotes_run_underlying` on `(run_id, underlying)`.

### `earnings`

Next known earnings date per ticker, refreshed by the options pipeline.

| Column | Type | Notes |
|---|---|---|
| `symbol` | VARCHAR(16) | Primary key |
| `next_date` | DATE | Null if none found in the window |
| `updated_at` | DATETIME | |

## Relationships

```
pipeline_runs 1 ──< option_quotes        (enforced foreign key: option_quotes.run_id)
tickers.symbol  ~  option_quotes.underlying   (by convention, not enforced)
tickers.symbol  ~  earnings.symbol            (by convention, not enforced)
```

## Data flow

1. **Universe pipeline** writes `tickers` (constituents, market cap, average option volume, `selected`).
2. **Options pipeline** reads the `selected` tickers, writes `option_quotes` under its own `run_id`, and
   upserts `earnings`.
3. **Signals** are not stored. The API computes forward factor calendar pairs on request from the latest
   successful options run's `option_quotes`, joined with `earnings`. Screener thresholds and DTE filters
   therefore apply instantly without re-running a pipeline.

Each options run adds a new set of quotes, so history accumulates in `option_quotes`, which is the table
that will grow. Pruning old runs is not implemented yet.

## Conventions

- Datetimes are naive local time (`NaiveDatetime`). The signals service uses the options run's
  `started_at` date as the "as of" date when computing DTE.
- IV is stored as a decimal. The API and UI convert to percent for display (`ff_pct`, `forward_vol_pct`).
- Prices are in USD. `market_cap` is in dollars, not millions.
