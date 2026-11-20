# Session Handoff: Forward Factor Screener MVP scaffold

Date: 2026-11-14. Everything below reflects the state of the repo at the end of this session.

## 1. What this session was for

[CLAUDE.md](../CLAUDE.md) set the goals: pick a stack and structure for a local MVP that can later deploy as a
web app, choose a data source, design the data pipelines, define MVP requirements, and start implementing. The
first feature is forward factor screening.

We read the reference material in `references/` (a forward vol calculator, a backtest report docx, and a
prototype notebook) and a transcript of the YouTube video, summarized the strategy, made the product
decisions below, then scaffolded and partly verified a working app.

## 2. Strategy summary (details in [docs/forward_factor_summary.md](../docs/forward_factor_summary.md))

- Forward vol between two expiries is computed in variance space, and
  `FF = (front IV - forward vol) / forward vol`. FF > 0 means the front month is rich (backwardation).
- The trade is a long calendar spread (sell front, buy back), entered when FF is high and closed just before
  the front expires.
- The video claims 27% CAGR and 2.4 Sharpe. Those are the presenter's own figures, unverified. I worked from
  an auto-generated transcript and did not watch the video.
- The video's entry threshold (FF >= 20%) differs from the notebook's per-pair values (23%, 23%, 41.5%). The
  threshold is therefore a UI setting, not a constant.

## 3. Decisions made (all confirmed by the user)

| Topic | Decision |
|---|---|
| Structure | Call calendar spreads only (no double calendars yet) |
| DTE rules | Front at least 14 DTE, back at least 14 days after the front, back at most 120 DTE. Any expiry pair that fits, not fixed 30/60/90. DTE gap shown in the UI |
| Threshold | One global FF threshold set in the UI, applied at query time |
| IV source | Vendor IV from Alpaca, free plan (`indicative` feed, so quotes and IV are approximate) |
| Other data | Finnhub for market cap and earnings dates. yfinance dropped |
| Earnings | Flag and show, with an optional UI filter. Not excluded by default |
| Universe | S&P 500 + Nasdaq-100, top N by market cap (default 250), then average option volume cutoff (default 10,000) |
| Pipelines | Two manual pipelines run from the UI: (1) universe selection, (2) option data. Single user |
| Spread filter | Default max 10% (combined bid/ask spread as % of mid debit), a UI setting |
| Stack | Python 3.11 + FastAPI, SQLModel on SQLite (Postgres later via `DATABASE_URL`), React + TypeScript + Vite, uv for Python packages |
| Scope | Real-time data first. Historical data later |

Position sizing: the notebook's per-pair Kelly fractions no longer apply to continuous DTE combos. I asked
whether to replace them with one position-size setting or leave sizing out, and the reply was a blanket "yes",
so this is **unresolved and not implemented**.

## 4. What was built

```
options_platform/
  backend/                      uv project (pyproject.toml, uv.lock)
    app/
      main.py                   FastAPI app, CORS, startup (create tables, fail interrupted runs)
      config.py, db.py          settings from root .env, SQLite engine with WAL
      models.py                 SQLModel tables (see docs/database_schema.md)
      api/pipelines.py          POST run endpoints, run history, universe list
      api/signals.py            GET /api/signals with filters
      clients/alpaca.py         prices, option chains (IV + quotes), option bars
      clients/finnhub.py        market cap, next earnings, throttled to ~1 call/sec
      pipelines/runner.py       run tracking, one active run at a time, progress reporter
      pipelines/universe.py     pipeline 1
      pipelines/options.py      pipeline 2
      services/ff.py            forward vol and FF math
      services/pairing.py       calendar pair generation
      services/signals.py       computes signals from the latest successful options run
      services/occ.py           OCC symbol parser
    tests/                      21 tests
  frontend/                     Vite + React + TypeScript
    src/pages/Screener.tsx      filters, sortable table, earnings badges, "Run options pipeline" button
    src/pages/Pipelines.tsx     both pipelines with parameters, progress, run history, universe table
    src/hooks.ts                shared run polling, refreshes data when a run finishes
  docs/                         forward_factor_summary.md, database_schema.md
  README.md                     setup and run instructions
```

How data flows: the universe pipeline writes `tickers` and sets `selected`. The options pipeline reads the
selected tickers and appends call quotes to `option_quotes` under its own run id, and upserts `earnings`.
Signals are not stored. They are computed on each API request from the latest successful options run, which
is why changing a threshold or DTE filter in the UI is instant.

## 5. Problems found and fixed along the way

- **Mismatched strikes in the notebook.** The notebook picked the ATM strike per expiry independently, so a
  calendar's two legs could sit at different strikes. Pairing now uses the strike common to both expiries
  that is closest to spot.
- **Alpaca `feed` argument.** `OptionBarsRequest` has no `feed` field, so the notebook's `feed="indicative"`
  on bars did nothing. It is omitted.
- **Naive datetimes.** The installed SQLModel stores datetimes as timezone-aware and rejected naive values.
  The model fields use pydantic `NaiveDatetime` (naive local time).
- **Nasdaq-100 constituents.** Wikipedia's Nasdaq-100 article no longer contains a constituents table, which
  crashed the universe pipeline. The Nasdaq-100 list now comes from Nasdaq's public endpoint
  `api.nasdaq.com/api/quote/list-type/nasdaq100` (101 members). The S&P 500 still comes from Wikipedia. Both
  fail with a readable error if their layout changes again. Nasdaq's endpoint is not a documented API.
- **Test data.** One API test used a 50% front IV against 30% back IV, which correctly produces negative
  forward variance and no pair. The test data was changed, not the code.

## 6. Verification status

Verified:
- 21 backend tests pass (FF math against the reference calculator and the video's worked example, OCC
  parsing, pairing rules, the signals API with earnings flags, the one-active-run rule, interrupted-run
  recovery).
- Frontend typechecks and builds. FastAPI starts and serves `/api/health`, `/api/signals` and `/docs`.
- Live one-ticker probes worked: Alpaca returned AAPL spot, calls, vendor IV and bid/ask. Finnhub returned
  market cap and next earnings.
- The constituents step returns 516 unique symbols (501 S&P 500, 101 Nasdaq-100, 86 in both).

**Not verified:**
- The universe pipeline past the constituents step (market caps, ranking, option volume, selection) has not
  run end to end. The user's last run failed at the constituents step before that fix.
- The options pipeline has not run end to end, so the screener has never shown real data.
- The UI has not been opened in a browser. I confirmed it compiles, not that it looks right.
- The database is empty apart from one failed run row (run 1).

## 7. Behaviors worth knowing

- **Universe pipeline.** All constituents are added to `tickers` regardless of volume. The volume threshold
  only sets `selected`. Market caps are reused if newer than 7 days. `updated_at` is set on every row on every
  run, so use `market_cap_updated_at` to judge freshness. `avg_option_volume` is not cleared for tickers that
  drop out of the top N.
- **Volume is a proxy.** It sums near-the-money contracts expiring within 45 days, not the whole chain, so
  the 10,000 cutoff means something different than in the notebook. Tune it.
- **First universe run is slow.** About 516 Finnhub profile calls at roughly 1 per second, around 9 minutes.
  Later runs reuse cached caps.
- **Options pipeline is append-only.** Each run adds rows under a new run id and nothing is deleted. The
  screener reads only the latest succeeded run, so a ticker skipped in the newest run disappears from the
  screener even if an older run had it. Failed runs leave partial rows that are ignored.
- **No pruning** of old option quotes yet, and no migrations: tables are created with `create_all`.
- **Strike window** (default +/-5% of spot) limits what is stored. Anything outside it is unavailable to the
  screener until the pipeline reruns with a wider window.
- **Dotted tickers** (e.g. BRK.B) are skipped because Alpaca lists their options under a different root.

## 8. How to run

```bash
cd backend  && uv sync && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev        # http://localhost:5173
cd backend  && uv run pytest
```
Keys live in the git-ignored root `.env`: `ALPACA_KEY`, `ALPACA_SECRET`, `FINNHUB_KEY`. The repo has no git
commits yet.

## 9. Recommended next steps

In order:


1. **Verify Calender spread option contract selectoin logic.** No contracts are left out 
3. **Sanity-check data quality on the free indicative feed.** Look for stale or zero quotes, odd IVs, wide
   spreads, and large chains that may need pagination or throttling. Decide whether the free feed is good
   enough or whether to move to the paid OPRA feed (`ALPACA_OPTION_FEED=opra`).
4. **Open the UI in a browser** and fix any layout or usability problems, then check the progress bar, errors
   and the run button behave as intended.
5. **Make a first git commit** once steps 1 to 4 work.
6. **Decide on position sizing** (single size setting vs none) and implement it if wanted.
7. **Add pipeline tests** with mocked Alpaca and Finnhub clients, since only pure logic and the API are
   tested today.
8. **Cleanups:** make `updated_at` change only for rows that were actually refreshed, clear volume for tickers
   outside the top N, and add pruning (keep the last N option runs).
9. **Add Alembic** before the schema needs to change with data worth keeping.
10. **Handle earnings-stripped IV.** The video says earnings-inflated front IV distorts FF. Currently earnings
    are only flagged.
11. **Later:** double calendars, historical data and backtests, scheduling the pipelines, Postgres and web
    deployment (auth, hosting), and live or streaming data.
