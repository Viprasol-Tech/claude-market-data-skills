---
name: market-calendars
description: Handle exchange trading calendars correctly - holidays, early closes, special sessions (NSE Muhurat trading), lunch breaks and auctions, using exchange_calendars and pandas_market_calendars (which exchanges each supports: XNYS, XBOM, NSE via pandas_market_calendars), US half-days (day after Thanksgiving, Christmas Eve), NSE holiday circulars, sessions in exchange-local time, and generating expected bar timestamps for gap checks and schedulers. Use when scheduling a trading bot, checking data for missing days, computing trading days between dates, or annualising returns.
---

# Market calendars

A calendar answers three questions: is the market open on this date, at
what local times, and is it a normal, early-close or special session. Facts
checked November 2026; sources in `reference.md`.

## Libraries

| Library | Notes |
|---|---|
| `exchange_calendars` (4.13.x, community-maintained fork of Quantopian's `trading_calendars`) | ISO codes like `XNYS`, `XLON`, `XBOM` (BSE); **no `XNSE`**; only regular sessions count as open (auctions, lunch breaks are closed) |
| `pandas_market_calendars` | native `NSE` and `BSE` calendars plus the `exchange_calendars` ones by ISO code; early closes supported |

```python
import pandas_market_calendars as mcal
nse = mcal.get_calendar("NSE")
sched = nse.schedule(start_date="2026-11-01", end_date="2026-11-30")   # market_open / market_close in UTC
bars = mcal.date_range(sched, frequency="1min")                          # expected 1-minute timestamps
```

Pin the version and update it every year: holiday lists for the next year
arrive in a library release only after the exchange publishes them.

## US (NYSE) points that break code

- 2026 early closes at 13:00 ET (13:15 for eligible options): Friday 27
  November (day after Thanksgiving) and Thursday 24 December. Independence
  Day 2026 is observed on Friday 3 July (closed).
- 2027: early close on 26 November; 24 December is the observed Christmas
  holiday.
- Daylight saving moves the session in UTC twice a year; store sessions in
  exchange-local time and convert per date.

## India (NSE)

- Regular equity and F&O session 09:15-15:30 IST (IST is UTC+5:30 all year,
  no daylight saving); pre-open 09:00-09:15.
- Holidays are announced per segment by NSE circular in December for the
  next year, and NSE adds ad-hoc closures (for example 15 January 2026 for
  municipal elections). Keep the list as data and refresh it from the
  circulars; do not trust a hard-coded list.
- **Muhurat trading**: a short special session on Diwali (2026: Sunday
  8 November), announced by circular weeks before. Treat it as a special
  session: a bot scheduled "weekdays only" misses it, and a daily bar
  builder may merge it into the next day.
- F&O expiries move to the previous trading day on a holiday (see
  `nse_symbols.py` in claude-tradingview-automation-skills).

## Using a calendar in code

- **Schedulers**: compute the next session open from the calendar, not from
  "every weekday at 09:15".
- **Gap checks**: compare stored bars with `date_range` of the schedule
  (`data-quality`).
- **Annualising**: count actual sessions per year (NSE and NYSE are about
  248-252) instead of assuming 252; crypto trades 365 days.
- **Trading days between dates**: from the schedule, not `numpy.busday_count`
  with a guessed holiday list.
- **Time zones**: keep schedules in UTC with the exchange zone recorded; see
  `timestamps`.
