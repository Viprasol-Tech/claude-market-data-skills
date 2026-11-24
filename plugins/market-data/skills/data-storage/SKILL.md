---
name: data-storage
description: Store market data for research and trading systems - raw immutable layer plus derived layers, Parquet with Hive partitioning by date and symbol, DuckDB queries over Parquet, tick stores (QuestDB, TimescaleDB/Tiger Data hypertables), schema and metadata (vendor, adjustment flags, units, time zone), point-in-time correctness, deduplication and late corrections, NSE bhavcopy (UDiFF) ingestion, and sizing. Use when designing where bars, ticks, option chains and corporate actions live, choosing a database for market data, or when queries over years of data are slow.
---

# Market data storage

Store data so a backtest from next year can reproduce a result from today.
That means raw data kept as delivered, derived data rebuilt from it, and
metadata that says exactly what each column is. Facts checked November
2026; sources in `reference.md`.

## Layers

| Layer | Contents | Rule |
|---|---|---|
| raw | files exactly as downloaded (CSV, JSON, vendor binary) with download time | never modified; re-download only adds new versions |
| clean | parsed, typed, UTC timestamps, deduplicated, quality-checked | rebuilt from raw by code in version control |
| derived | adjusted series, resampled bars, features | rebuilt from clean; never edited by hand |

## Parquet + DuckDB (good default for research)

```sql
-- write bars partitioned by date parts
COPY (SELECT *, year(ts) AS year, month(ts) AS month FROM bars)
TO 'bars' (FORMAT parquet, PARTITION_BY (year, month));
-- read with partition pruning
SELECT symbol, avg(close) FROM read_parquet('bars/*/*/*.parquet', hive_partitioning = true)
WHERE year = 2026 AND month = 11 GROUP BY symbol;
```

- `PARTITION_BY` takes columns, not expressions: add `year`/`month` columns
  first. Filters on partition keys skip files.
- Partition by time (and by symbol only when there are few symbols); aim for
  files of tens to hundreds of MB, not thousands of tiny files.
- Timestamps as UTC (`isAdjustedToUTC=true`), prices as `DECIMAL` or `DOUBLE`
  consistently, volume as integer or decimal; see `timestamps`.

## Tick and live data

- **QuestDB**: designated timestamp column, `SAMPLE BY` for bars (aligned to
  calendar, `FILL` options for gaps).
- **TimescaleDB** (now Tiger Data): hypertables partition by time into chunks
  automatically; good when the rest of the system is PostgreSQL.
- Keep the raw feed (or the vendor's files) too: database ingestion code has
  bugs.

## Metadata to store with every dataset

Vendor and endpoint, request parameters (adjustment flags, feed such as
`sip`/`iex`), download time, timestamp unit and zone, bar label convention,
symbol mapping version, corporate-action source, and the quality report.

## Point-in-time and corrections

- Vendors correct data (late trades, bad ticks, adjusted histories). Keep
  versions (`valid_from` / download date) so a backtest can be rerun with
  the data it originally saw.
- Deduplicate on (symbol, timestamp, sequence/trade id), not on price.
- Universe, index membership and corporate actions are time series too.

## NSE bhavcopy (UDiFF)

NSE moved its end-of-day bhavcopies to the SEBI-driven UDiFF standard format
in 2024 (column names such as `TckrSymb`, `OpnPric`, `ClsPric` in the new
files), and URLs and paths have changed several times since, including in
2026. Write the downloader so the URL pattern and column mapping are
configuration, validate the header on every file, and keep both the old and
new parsers for history before the switch.

## Sizing rule of thumb

One year of 1-minute bars for 500 symbols is about 47 million rows; in
Parquet with compression that is hundreds of MB, fine on a laptop with
DuckDB. Tick data for the same universe is orders of magnitude larger:
plan partitioning and retention first.
