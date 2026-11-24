---
name: corporate-actions
description: Adjust stock prices correctly for splits, bonus issues, reverse splits and cash dividends - CRSP/Yahoo multiplicative back-adjustment, split-only vs. total-return series, what each vendor returns by default (Yahoo Adj Close, yfinance auto_adjust, Massive/Polygon split-adjusted aggregates, Alpaca raw by default, Databento adjustment factors, Tiingo adj fields, EODHD adjusted_close), NSE bonus/split adjustment factors for F&O, and detecting unadjusted splits in a dataset. Includes a tested adjuster and split scanner. Use when a backtest shows impossible jumps, indicators break at a split, adjusted and raw data are mixed, or someone asks which price series to store.
allowed-tools: Bash(python ${CLAUDE_SKILL_DIR}/scripts/adjust_prices.py *)
---

# Corporate actions and price adjustment

A 2-for-1 split looks like a 50% crash in raw prices. A backtest that mixes raw
and adjusted series, or adjusts twice, trades phantom crashes. Facts checked
November 2026; sources in `reference.md`.

## Tool

```bash
python ${CLAUDE_SKILL_DIR}/scripts/adjust_prices.py raw.csv --scan                          # find split-like gaps
python ${CLAUDE_SKILL_DIR}/scripts/adjust_prices.py raw.csv --actions actions.csv --out adjusted.csv
```

`actions.csv`: `ex_date,type,value` with `split` (new shares per old: 2 for
2-for-1, 0.1 for 1-for-10), `bonus` (bonus shares per share: 1 for a 1:1
bonus = 2x) or `dividend` (cash per share). Output adds a `factor` column so
you can always get back to raw prices. On a shared ex-date, splits are
applied before the dividend (which is per post-split share), and duplicate
action rows are reported. `--scan` reports overnight gaps of 30% or more that
match a p-for-q ratio (p, q up to 50: 7-for-1, 20-for-1, 1-for-8 and so on).

## The method (CRSP / Yahoo style)

Rows **before** the ex-date are scaled; the latest prices never change.

| Event | Price factor for earlier rows | Volume factor |
|---|---|---|
| Split N-for-1 (ratio N) | `1 / N` | `x N` |
| Bonus B:1 (B bonus shares per share) | `1 / (1 + B)` | `x (1 + B)` |
| Cash dividend D | `1 - D / previous close` (the close before the ex-date) | unchanged |

Factors compound backwards. The multiplicative dividend form cannot produce
negative prices (subtracting dividends can).

## What vendors give you (November 2026)

| Source | Default | Notes |
|---|---|---|
| Yahoo "Adj Close" | splits and dividends, CRSP method | OHLC columns are split-adjusted only |
| yfinance `download()` | `auto_adjust=True`: OHLC already adjusted for splits and dividends | set `auto_adjust` explicitly; old code that also used Adj Close adjusts twice. "Personal use" per the package |
| Massive (formerly Polygon) aggregates | **split-adjusted** by default, `adjusted=false` for raw | trades, quotes and flat files are never adjusted; nothing is dividend-adjusted (dividends are separate records) |
| Alpaca bars | **raw** by default; `adjustment=split,dividend,spin-off,all` | `asof` maps renamed symbols |
| Databento | prices unadjusted; separate Adjustment Factors dataset (one daily factor per security, statuses, event ids) | never apply two adjustments with the same ex-date and event id |
| Tiingo EOD | raw OHLCV plus `adjOpen`...`adjClose`, `adjVolume`, `divCash`, `splitFactor` | CRSP method |
| EODHD | `close` as traded; `adjusted_close` for splits and dividends | adjusted history changes when a new dividend arrives |
| IEX Cloud | shut down in August 2024 | migrate old code |

Rule: **store raw prices plus the corporate actions**, and build adjusted
series on demand. A stored adjusted series silently changes every time a new
dividend is paid.

## Which series for what

- **Backtest signals and returns**: total-return adjusted (splits and
  dividends), or raw prices plus dividend cash flows.
- **Order prices, stops, tick sizes, limit checks**: raw prices only; you
  cannot place an order at an adjusted price.
- **Volume filters**: split-adjusted volume.
- **Options**: raw underlying prices and the exchange's adjusted contract
  terms (strike and lot changes); not adjusted price series.

## India (NSE)

- Bonus A:B gives an F&O adjustment factor of (A + B) / B; a split A:B gives
  A / B. New strike = old strike / factor; new lot = old lot x factor. NSE
  publishes the adjusted terms by circular before the ex-date.
- Rights issues and extraordinary dividends have their own formulas; take the
  factor from the NSE circular rather than computing it.

## Checks before trusting a dataset

1. Run `--scan` on raw data: every split-like gap must match a corporate
   action; on adjusted data there should be none.
2. Compare one known split (date and ratio) against the vendor's actions
   endpoint.
3. Check that adjusted and raw series agree on the latest date.
4. Record the vendor, endpoint, adjustment flags and download date with the
   data.
