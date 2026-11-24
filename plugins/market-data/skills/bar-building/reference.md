# Sources (checked November 2026)

- Massive custom bars (window start, no empty bars): https://massive.com/docs/rest/stocks/aggregates/custom-bars.md
- Databento OHLCV (`ts_event` = start, no record without trades): https://databento.com/docs/schemas-and-data-formats/ohlcv.md
- Binance klines (open time, UTC): https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints
- TradingView Pine time concepts: https://www.tradingview.com/pine-script-docs/concepts/time/
- pandas `resample` (`closed`, `label` defaults): https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.resample.html
- QuestDB `SAMPLE BY`: https://questdb.com/docs/reference/sql/sample-by/
- Volume and dollar bars: López de Prado, *Advances in Financial Machine Learning* (2018), ch. 2.

Not confirmed: Alpaca's bar labelling (start vs. end).
