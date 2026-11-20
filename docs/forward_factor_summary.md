# Forward Factor Strategy: Summary of Reference Material

Sources:
- YouTube video `6ao3uXE5KhU`, "This Simple Options Strategy Crushes SPY (27% CAGR, 2.4 Sharpe)". Summarized from an auto-generated third-party transcript (youtube-transcript.ai), so transcription errors are possible (e.g. "kegger" = Kelly). I did not watch the video.
- `calculator.py`: a Tkinter forward vol / FF calculator.
- `Forward Factors Research.docx`: backtest charts and tables. The extractable text is only headings and captions; the numbers are in images.
- `forward_volatility_signal_v2.ipynb`: a prototype live screener using Alpaca and yfinance.

All performance figures are the presenter's claims and are unverified. The presenter also sells a screener on their own site.

---

## 1. The idea

Implied vol across expiries often misprices the vol that is later realized. If front-month IV is high relative to the forward vol implied by the back month, the term structure is in backwardation. The claim is that long calendar spreads (sell front, buy back) on those setups earn positive returns. A long calendar is long forward volatility.

Unfiltered calendars have a negative mean return. The edge comes only from conditioning on a high Forward Factor.

## 2. Formulas

With T = DTE/365, σ1 = front IV, σ2 = back IV (as decimals):

```
forward variance = (σ2²·T2 − σ1²·T1) / (T2 − T1)
σ_fwd            = sqrt(forward variance)
FF               = (σ1 − σ_fwd) / σ_fwd
```

- FF > 0 means backwardation (front IV above forward IV) and is the tradeable direction.
- Video worked example: 30d IV 45%, 60d IV 35% gives σ_fwd ≈ 20.6% and FF ≈ 117%. This checks out arithmetically.
- Edge cases (handled in `calculator.py`): negative forward variance means inconsistent inputs, so FF is invalid. σ_fwd = 0 means FF is undefined. Require DTE2 > DTE1.
- The video says to use earnings-stripped ("ex-earn") IV, or else avoid earnings between entry and the back expiry.

## 3. Trade structure and rules

| Item | Rule |
|---|---|
| Structures | ATM long call calendar; long double calendar (~35-delta call and put calendars) |
| DTE pairs | 30/60, 30/90, 60/90 (±5 day buffer on 30 and 60; the notebook uses a wider ±8 on 90) |
| Entry | FF at or above a threshold (see section 4) |
| Exit | Just before the front contract expires; close the whole spread |
| Universe | Liquid names: 20-day average option volume above 10,000 contracts/day |
| Earnings | Avoid earnings between entry and back expiry |
| Sizing | About 2-8% of equity per position, 4% default. Quarter Kelly or less is recommended |
| Portfolio | Diversify across tickers and fill highest-FF first |
| Costs | The backtest includes slippage, commissions and position caps |

Backtest: from 2007 (about 19 years), 300,000+ spread instances.

## 4. Thresholds (these differ between sources)

| Source | Threshold |
|---|---|
| Video playbook | FF ≥ 0.20 (20%) |
| Video, minimum for positive returns (examples) | ATM 30/90 > 0.03; double calendar 30/60 > 0.11 |
| Notebook "recommended" (about 20 trades/month) | 30/60: 23%; 30/90: 23%; 60/90: 41.5% |
| Notebook "minimum threshold" (break-even) | 30/60: 14.1%; 30/90: 13.23%; 60/90: 41.5% |

The notebook's Kelly fractions, which are the user's own sizing choices:

| Pair | Kelly | Fraction of Kelly used |
|---|---|---|
| 30/60 | 8% | Half |
| 30/90 | 5% | Quarter |
| 60/90 | 4.5% | Half |

The notebook targets roughly 44 trades/month in total (about 20 + 20 + 4).

**Open question:** the thresholds are a per-pair configuration, not a constant. The platform should make them editable settings.

## 5. Claimed results (video)

- Headline: 27% CAGR, 2.4 Sharpe. The quoted case is 60/90 ATM call calendar at quarter Kelly (~26.7% CAGR, 2.4 Sharpe).
- CAGR is about 21-28% across pairs. Sharpe rises as Kelly fraction falls.
- Filtered (~20 trades/month) mean return per trade is about 9-25%, depending on pair and structure.
- The presenter calls the 60/90 pair the best.
- The research doc (`Forward Factors Research.docx`) has, for each of the three pairs and both structures: return distribution, returns over time by quarter, return vs FF and FF deciles, all-trades vs filtered (~20/month) model, and Kelly curves with full/half/quarter Kelly equity curves.
- Doc stat: trades per quarter, all-trades model, call calendar: 30/60 mean 148.6, 30/90 mean 413.6, 60/90 mean 11.5. Filtered model: roughly 57-64 per quarter.

## 6. Example trade (video)

AES: sell the Oct 17 14.5 ATM call at IV 61.97%, buy the Oct 24 call at IV 52.11%. Forward vol ≈ 33.37%, FF ≈ 86%. Earnings (around Oct 30) fell outside the window.

Note: this example is a one-week gap and does not fit the DTE pairs above. Treat it as illustrative only.

## 7. What the existing notebook does (live screener prototype)

1. Universe: S&P 500 constituents (Wikipedia), top 250 by market cap (yfinance).
2. Liquidity: pull option bars per ticker (Alpaca, `indicative` feed), sum volume per day, take the 20-day average, and keep tickers above about 9,500-10,000.
3. Chains: for each ticker and each target DTE (30/60/90), pull calls within ±$5 of spot, then keep the strike closest to spot. DTE buckets: low = 15-35, mid = 45-75, high = 80-105.
4. Pairing: cross-join low-mid, mid-high, low-high.
5. Signal: compute FF per pair from the contract IVs.
6. Pricing: debit = back ask − front bid. Spread = sum of both legs' bid-ask spreads.
7. Filters: FF ≥ recommended threshold; total spread ≤ 10% of price (as written, the filter compares the 10% of the combined price against the spread); earnings at least 7 days from front expiry (yfinance).
8. Sizing: Kelly fraction × portfolio ($40k in the notebook) divided by debit × 100 per contract.

Known issues in the notebook to fix when productionizing:
- IV is taken straight from Alpaca's chain snapshot. It is not earnings-stripped, which the video says matters.
- The notebook only uses ATM call calendars. It has no double calendar.
- Liquidity filter and earnings are fetched with slow per-ticker loops. In the notebook the volume file is cached to CSV from a prior run.
- `parse_occ_symbol` computes DTE with `datetime.today()`, including time of day.
- yfinance is unofficial and can break or be rate-limited. It is used for market cap and earnings dates.
- The Wikipedia scrape is brittle.
- Many of the notebook's trade-size steps are mixed with exploratory cells and need cleanup.

## 8. Implications for the platform (real-time focus)

Core real-time pipeline: universe, then liquidity filter (cached daily), then chain snapshot (DTE and strike windows), then IV and quote extraction, then FF per pair, then threshold and filters, then ranked signals with suggested size.

Data needed in real time: underlying last price, option quotes (bid/ask), IV per contract, expirations and DTE, and earnings dates. IV can come from the vendor or be computed ourselves from mid prices. The earnings-adjusted IV question needs a decision.

Open questions to decide:
1. Which threshold source wins as the default (video 20% vs the notebook's per-pair values)?
2. Support ATM call calendars only for the MVP, or double calendars too?
3. Own IV calculation vs vendor IV, and how to handle earnings-stripped IV.
4. Earnings date source more reliable than yfinance.
5. Refresh frequency: on demand, every few minutes, or end-of-day snapshots.


# Strategy
### FF Threshold Logic
- low - mid : 23 % : Increases the FF to limit the number of entry signals
- low - high : 23 % : Increases the FF to limit the number of entry signals
- mid - high : 41.46% : This is the FF cross over thresh hold. its about 4 trades a month and does not require me to reduce the the FF to get the 20 trades


With this combination, I should average about 20 + 20 + 4 = 44 trades a month. Which is very managable.  The increase FF on the low -mid and the low - high means a higher win rate and average return per trade
Below is the mininim FF Threshold required to make a profit according to historical data
- low - mid : 23 % 
- low - high : 23 % 
- mid - high : 41.46% 


### Kelly Criterion Logic
- low - mid : 8 % Half
- low - high : 5 %  Quarter
- mid - high : 4.5 Half

- Tried to keep all sizing between 2-8% and maximize CAGR and Sharpe Ratio