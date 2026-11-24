---
name: timestamps
description: Get market-data timestamps right - store instants as UTC int64 (ms/us/ns) with the exchange time zone recorded, exchange-local vs. UTC, daylight-saving gaps and repeats (US and EU on different dates, India none), naive vs. aware timestamps in pandas, Parquet isAdjustedToUTC and Arrow time zones, Spark truncation, epoch-unit mistakes (s vs. ms vs. ns), vendor conventions (Binance UTC ms, MT5 server time, TradingView UNIX ms), event time vs. receive time, and clock sync. Use when merging data across vendors or markets, when bars are shifted by an hour twice a year, or when designing a tick or bar store.
---

# Timestamps and time zones

Timestamps fail quietly: everything still runs, but a bar is an hour late
from March to October, or two vendors' data disagree by 5.5 hours. Facts
checked November 2026; sources in `reference.md`.

## Rules

1. **Store instants in UTC** as int64 with an explicit unit (ms, us or ns),
   or as a time-zone-aware timestamp type. Record the exchange time zone
   (`America/New_York`, `Asia/Kolkata`) as metadata, not in the value.
2. **Never store naive local times.** If a source gives local wall-clock time
   without an offset (MT5 server time, many CSV exports), attach the source's
   zone immediately on ingest, with the IANA name, not a fixed offset.
3. **Convert to local time only for display and for session logic** (for
   example "is this bar inside 09:30-16:00 New York").
4. **Keep event time and receive time** for live data: the exchange
   timestamp for analysis, your receive time for latency and ordering.
5. **Sync clocks** (NTP/chrony) on every machine that timestamps data.

## Daylight saving

- The US switches on the second Sunday of March and the first Sunday of
  November; the EU on the last Sundays of March and October. For three to
  four weeks a year in total the New York-London gap is 4 hours, not 5 (in
  2026: 8-29 March and 25 October-1 November).
- India (IST, UTC+5:30) and most crypto venues (UTC) have no daylight saving.
- Local times can be missing (spring forward) or repeated (fall back).
  Converting a naive local series with pandas needs `ambiguous=` and
  `nonexistent=` decisions; it is better not to have naive local series.

## Units and formats

| Source | Format |
|---|---|
| Binance REST/WebSocket | UTC epoch milliseconds (some newer streams microseconds: check the field) |
| TradingView Pine `time` | UNIX milliseconds, bar open |
| Massive (Polygon) aggregates | Unix ms, window start |
| Databento | `ts_event`, nanoseconds since epoch, UTC |
| MT5 | server time (broker zone, often UTC+2/+3), no offset |
| Kite/Indian brokers | IST strings in many endpoints |

Guess the unit from magnitude only as a last resort (2026 in seconds is about
1.8e9, in ms 1.8e12, in ns 1.8e18), and assert it in code.

## Storage formats

- **Parquet**: `TIMESTAMP` with `isAdjustedToUTC=true` stores instants (the
  original zone is lost, so keep it as a column or file metadata); `false`
  stores local wall-clock values that are not instants. Units MILLIS, MICROS
  or NANOS.
- **Arrow**: int64 plus a unit and an optional time zone (aware vs. naive).
  Round trips through Spark drop the time zone and truncate to microseconds.
- **pandas**: use `datetime64[ns, UTC]`; `tz_localize` for naive data with a
  known zone, `tz_convert` to change zones.

## Debugging checklist

- [ ] Every ingested timestamp has a zone or offset at the boundary.
- [ ] Unit asserted (ms vs. ns) per source.
- [ ] Sessions computed in exchange-local time per date (DST).
- [ ] Vendor bar labels normalised (start vs. end, `bar-building`).
- [ ] A sample bar compared by hand across sources at a DST transition.
