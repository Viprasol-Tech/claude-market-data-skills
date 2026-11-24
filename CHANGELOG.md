# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-24

### Added
- `market-data` Claude Code plugin with 6 skills: `corporate-actions`,
  `data-quality`, `bar-building`, `market-calendars`, `timestamps`,
  `data-storage`.
- `adjust_prices.py`: CRSP-style back-adjustment for splits, bonuses and cash
  dividends, and a scanner for unadjusted splits.
- `bar_check.py`: OHLCV quality report (consistency, duplicates, gaps against
  sessions and holidays, frozen bars, robust return outliers).
- `make_bars.py`: start-labelled time bars, session alignment, volume and
  dollar bars from trades.
- Facts checked against Yahoo, yfinance, Massive, Alpaca, Databento, Tiingo,
  EODHD, NYSE, NSE, Parquet, Arrow, DuckDB and QuestDB documentation in
  November 2026.
