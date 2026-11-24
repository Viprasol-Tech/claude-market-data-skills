# Sources (checked November 2026)

- Yahoo adjusted close (CRSP method, split and dividend multipliers): https://help.yahoo.com/kb/SLN28256.html
- yfinance `download()` defaults (`auto_adjust=True`): https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html and https://pypi.org/project/yfinance/
- Massive (formerly Polygon) adjustment policy: https://massive.com/knowledge-base/article/is-polygons-stock-data-adjusted-for-splits-or-dividends
- Alpaca stock bars (`adjustment`, `asof`): https://docs.alpaca.markets/reference/stockbars
- Databento adjustment factors: https://databento.com/docs/schemas/adjustment-factors and https://databento.com/docs/examples/adjustment-factors/applying-adjustment-factors
- Tiingo end-of-day: https://www.tiingo.com/documentation/end-of-day
- EODHD historical data: https://eodhd.com/financial-apis/api-for-historical-data-and-volumes
- IEX Cloud closure (secondary): https://databento.com/blog/migrating-from-iex-cloud
- NSE F&O corporate action adjustments: https://www.nseindia.com/products-services/equity-derivatives-corporate-actions-adjustments (example circular: https://archives.nseindia.com/content/circulars/FAOP53548.pdf)

Not confirmed on a primary page: CRSP's cumulative factor documentation (the
guide was unreachable), the yfinance release that changed `auto_adjust`,
how Databento's factor compounds across events, and NSE's rights and
extraordinary-dividend formulas.
