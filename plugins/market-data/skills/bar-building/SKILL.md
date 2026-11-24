---
name: bar-building
description: Build and align OHLCV bars correctly - start-labelled, left-closed time bars [start, end), session-aligned intraday bars (NSE 09:15, US 09:30), no-trade intervals (missing bar vs. forward-filled flat bar), extended hours, volume and dollar bars, and how vendors label bars (Massive/Polygon and Databento start time, Binance kline open time, TradingView bar open time, pandas resample closed/label defaults, QuestDB SAMPLE BY). Includes a tested trades-to-bars builder. Use when resampling ticks or 1-minute data, merging bars from two vendors, or when indicators differ from TradingView by one bar.
allowed-tools: Bash(python ${CLAUDE_SKILL_DIR}/scripts/make_bars.py *)
---

# Building bars

Most "my indicator is off by one bar" bugs are labelling bugs: one source
labels a bar by its start, another by its end, or a resample closes intervals
on the right. Facts checked November 2026; sources in `reference.md`.

## Tool

```bash
python ${CLAUDE_SKILL_DIR}/scripts/make_bars.py trades.csv --time 60                     # 1-minute bars, UTC-aligned
python ${CLAUDE_SKILL_DIR}/scripts/make_bars.py trades.csv --time 3600 --offset-min 45   # hourly bars from NSE's 09:15 IST open
python ${CLAUDE_SKILL_DIR}/scripts/make_bars.py trades.csv --volume 10000                # volume bars
python ${CLAUDE_SKILL_DIR}/scripts/make_bars.py trades.csv --dollar 5000000              # dollar (notional) bars
```

Rules it follows: bars cover `[start, start + interval)`; a trade exactly on a
boundary opens the next bar; bars are labelled by start time in UTC; no
trades means no bar unless `--fill` (flat bar, zero volume, `trades = 0`);
volume and dollar bars close on the trade that crosses the threshold and the
last incomplete bar has an empty `end`. `--fill` never bridges gaps longer
than `--max-fill` bars (nights, weekends, halts). Integer timestamps may be
seconds, ms, us or ns (guessed from magnitude); ISO timestamps need an offset.
Filter trades to the session first: the tool sets `end` = start + interval
even for the session's last, short bar.

## How sources label bars

| Source | Timestamp means | Empty intervals |
|---|---|---|
| Massive (formerly Polygon) aggregates | `t` = start of the window (Unix ms) | no bar; pre-market and after-hours included |
| Databento OHLCV | `ts_event` = inclusive start of the bar | no record; `ohlcv-1d` is cut on UTC dates (electronic session), not the exchange's trading day |
| Binance klines | open time (close time is element 6) | UTC; startTime/endTime always UTC |
| TradingView Pine | `time` = bar open (UNIX ms); `time_close` = close | calendar functions use the exchange time zone |
| pandas `resample` | `closed`/`label` default `'left'`, except month/quarter/year/week-end rules, which default to `'right'` | missing intervals become NaN rows |
| QuestDB `SAMPLE BY` | aligned to calendar (UTC, or a TIME ZONE) | skipped unless `FILL(PREV/NULL/LINEAR/x)` |

Before merging two sources, shift both to start-labelled UTC.

## Rules worth writing down

- **Label by start, store in UTC**, convert for display. A 09:15 bar on NSE
  is `03:45Z`.
- **Align intraday bars to the session**, not to UTC midnight, when the
  session does not start on an interval boundary (hourly NSE bars: 09:15,
  10:15, ...; the last bar is short, 15:15-15:30, so drop trades after the
  close before building it).
- **Empty intervals**: either no bar (honest) or a flat bar flagged as filled
  with zero volume. Never forward-fill silently: it hides halts and stale
  feeds, and fills a backtest at prices nobody traded.
- **Extended hours**: decide per strategy and filter by session; vendors mix
  them in by default for US stocks.
- **Resampling bars to bars**: open = first open, high = max, low = min,
  close = last close, volume = sum; only from complete lower bars, and only
  when the lower bars are aligned to the target boundaries.
- **Volume / dollar bars** (de Prado) sample by activity, which gives more
  even information per bar than clock time; thresholds need recalibrating as
  volume trends.
- **Daily bars**: the vendor's daily bar may be the electronic session only
  or the official close; settlement prices for futures differ from the last
  trade.
