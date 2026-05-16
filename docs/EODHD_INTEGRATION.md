---
concept: Mukesh Kesharwani
contact: mukesh.kesharwani@adobe.com
---

# EODHD integration (single-API mode)

This dashboard is wired to **EODHD (eodhd.com)** as the **single data provider** for OHLCV, with **SEC EDGAR** kept as a free, US-only fundamentals enhancer. The older Yahoo / Alpha Vantage / Investing.com chain is still in the codebase but only runs when `LEGACY_SOURCES=true`.

## 1. Sign up and get an API key

1. Create an account at [https://eodhd.com](https://eodhd.com).
2. Subscribe to **"EOD Historical Data - All World"** (~$17.99/mo at time of writing) for global equities + ETFs across 70+ exchanges. A free trial token is also available for evaluation.
3. Copy your API token from the dashboard.

**Fundamentals** (including **Free cash flow**) are attempted automatically when `EODHD_API_KEY` is set. Your plan must include the [Fundamentals Data Feed](https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds) (~$53.99/mo add-on); otherwise the app logs HTTP 403 and falls back to free **SEC EDGAR** for US tickers.

## 2. Configure environment

Copy `.env.example` to `.env` and set:

```bash
EODHD_API_KEY=your_token_here
EODHD_DEFAULT_EXCHANGE=US
# Optional: EODHD_FUNDAMENTALS_ENABLED=false   # skip EODHD fundamentals, EDGAR-only
SEC_USER_AGENT=Your-App you@example.com        # US EDGAR fallback
```

Restart `streamlit run app.py` after changing `.env`.

## 3. Symbol format

EODHD addresses securities as `SYMBOL.EXCHANGE`:

| Example | Meaning |
| ------- | ------- |
| `AAPL.US` | Apple Inc. (US listing) |
| `RELIANCE.NSE` | Reliance Industries (NSE, India) |
| `ABB.NSE` | ABB India (NSE) |
| `VOD.LSE` | Vodafone (London Stock Exchange) |
| `SAP.XETRA` | SAP (Deutsche Boerse XETRA) |
| `7203.TSE` | Toyota Motor (Tokyo) |

In the dashboard text input, a **bare symbol** (e.g. `AAPL`) is interpreted as `AAPL.<EODHD_DEFAULT_EXCHANGE>`.

A full list of supported exchanges is published at [https://eodhd.com/financial-apis/list-supported-exchanges](https://eodhd.com/financial-apis/list-supported-exchanges).

## 4. Endpoints used by this app

| Endpoint | Purpose | Where |
| -------- | ------- | ----- |
| `GET /api/eod/{SYMBOL}.{EX}` | Daily OHLCV (open/high/low/close/adjusted_close/volume) | `stocks_dashboard/eodhd_client.fetch_ohlcv` |
| `GET /api/fundamentals/{SYMBOL}.{EX}` | Yearly financials + **freeCashFlow** (wide table) | `stocks_dashboard/eodhd_fundamentals.fundamentals_table_from_eodhd` |

The client requests `fmt=json` and (for OHLCV) `order=a` so rows arrive ascending by date.

## 5. Rate limits and errors

EODHD's standard plans allow approximately **100,000 calls/day** and **1,000 requests/min**, which is far more than this POC needs. The client raises:

- `EODHDError` on network / HTTP / parse failure.
- `EODHDFundamentalsDisabled` when fundamentals are requested without enabling the add-on.

HTTP `401/403` -> auth issue (token or plan coverage). HTTP `404` -> bad `SYMBOL.EXCHANGE`. HTTP `429` -> rate limited; slow down or upgrade.

## 6. PE / ROIC caveat

The Technical Indicators tab still calls **Yahoo Finance** (`yfinance`) for the **PE (TTM proxy)** and **ROIC** blocks. These only run for **US** listings (`.US` or bare symbols) and are silently skipped for other exchanges. Replacing those with EODHD requires the Fundamentals add-on and a small client extension.

## 7. Legacy chain

Set `LEGACY_SOURCES=true` in `.env` to restore the previous **Yahoo -> Alpha Vantage -> Investing.com** OHLCV chain and the **EDGAR -> Yahoo -> Alpha Vantage OVERVIEW** fundamentals chain. This is useful for offline experiments or when EODHD credentials are not available.

## 8. Trade-offs

- **Cost**: requires a paid EODHD subscription (~$18/mo for OHLCV). Free tier is rate-limited.
- **Adjusted close**: EODHD's `adjusted_close` may differ slightly from Yahoo; expect minor numeric drift versus prior runs.
- **Fundamentals coverage**: without the add-on, only US fundamentals are available (via EDGAR).
- **ToS**: confirm redistribution rules before sharing dashboard output publicly.

## 9. References

- EODHD pricing: [https://eodhd.com/pricing-special-10](https://eodhd.com/pricing-special-10)
- EODHD historical EOD docs: [https://eodhd.com/financial-apis/api-for-historical-data-and-volumes](https://eodhd.com/financial-apis/api-for-historical-data-and-volumes)
- EODHD fundamentals docs: [https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds](https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds)
- SEC EDGAR access guide: [https://www.sec.gov/os/accessing-edgar-data](https://www.sec.gov/os/accessing-edgar-data)
