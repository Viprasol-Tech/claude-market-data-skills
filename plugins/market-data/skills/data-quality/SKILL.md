---
name: data-quality
description: Check market data before a backtest or a live system trusts it - OHLC consistency, non-positive prices, duplicate and out-of-order timestamps, missing bars against the session and holiday calendar, frozen or forward-filled bars, zero-volume runs, return outliers with a robust z-score, unadjusted splits, survivorship bias (delisted symbols, point-in-time index members), renamed tickers and vendor-to-vendor reconciliation. Includes a tested bar checker. Use when loading a new dataset or vendor, when a backtest result looks too good, or when live signals differ from the backtest.
allowed-tools: Bash(python ${CLAUDE_SKILL_DIR}/scripts/bar_check.py *)
---

# Market data quality

Bad data does not crash a backtest; it makes it look good. Run checks when
data arrives, store the report with the data, and fail the pipeline on
errors. Facts checked November 2026; sources in `reference.md`.

## Tool

```bash
python ${CLAUDE_SKILL_DIR}/scripts/bar_check.py nifty_1m.csv --interval 1m --session 09:15-15:30 --tz +05:30 --holidays nse_2026.txt
python ${CLAUDE_SKILL_DIR}/scripts/bar_check.py aapl_daily.csv --interval 1d --holidays nyse_2026.txt
```

Errors (exit code 1): unparseable rows, non-positive prices, OHLC
inconsistency, negative volume, duplicate or out-of-order timestamps.
Warnings: missing bars against the session and holidays, bars outside the
session, three or more identical non-flat bars in a row, many zero-volume
bars, and return outliers (robust z-score on log returns; check them against
corporate actions with `corporate-actions --scan`). `--tz` is a fixed offset
and is also used for timestamps without one: for markets with daylight
saving, split the file at the DST dates or omit `--session`. Sessions may
cross midnight (`--session 18:00-17:00` for CME-style futures; the evening
part counts towards the next day).

## Checklist

| Check | Why |
|---|---|
| `low <= open, close <= high`, prices > 0 | broken ticks and bad merges |
| unique, increasing timestamps | duplicates double-count volume; disorder breaks rolling windows |
| bars vs. the exchange calendar | missing days hide halts or vendor gaps; extra bars mean wrong time zone or holidays |
| frozen bars, long zero-volume runs | stale feed or silent forward-fill |
| return outliers | bad ticks, unadjusted splits, or real events to keep |
| split-like gaps | raw data used as adjusted (`corporate-actions`) |
| delisted symbols present | survivorship bias |
| index membership by date | today's constituents applied to the past |
| renamed tickers | FB to META: history under the old symbol |
| two vendors agree | close within a tolerance on a sample of days |

## Survivorship and point-in-time data

- A universe built from **today's** listings or index members drops every
  company that went bankrupt or was delisted, which inflates returns.
- Massive's tickers endpoint has an `active` flag and `delisted_utc`;
  EODHD keeps delisted histories (renamed symbols need its rename history);
  Alpaca's `asof` maps renamed symbols. Check coverage for your market.
- Point-in-time S&P 500 membership comes from research datasets (for
  example CRSP via WRDS); for NIFTY, rebuild membership from NSE's
  index-change press releases. Store membership as (symbol, from, to).

## Reconciliation between vendors

Pick a sample of symbols and days; compare closes, volumes and corporate
actions. Expect differences in volume (consolidated vs. primary exchange),
daily bars (electronic session vs. official close) and adjustment methods.
Document which vendor is the reference for each field.

## yfinance and scraped data

yfinance is popular for prototypes but is intended for personal use, can be
rate-limited (`YfRateLimitError`), and changes with Yahoo's site. Pin the
version, set `auto_adjust` explicitly, cache downloads, and do not build a
commercial product on it.
