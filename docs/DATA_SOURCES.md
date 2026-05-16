---
concept: Mukesh Kesharwani
contact: mukesh.kesharwani@adobe.com
---

# Data sources (single-API mode)

The dashboard uses **EODHD** for OHLCV and **EODHD fundamentals first** (when your API key and plan allow), with **SEC EDGAR** as a US fallback. Legacy Yahoo / Alpha Vantage / Investing.com is off unless `LEGACY_SOURCES=true`.

See [EODHD_INTEGRATION.md](EODHD_INTEGRATION.md) and [EODHD_API_KEY_SETUP.md](EODHD_API_KEY_SETUP.md).

## OHLCV (Technical Indicators & Patterns)

**EODHD** `GET /api/eod/{SYMBOL}.{EX}` via `stocks_dashboard/eodhd_client.py`.

Charts: **Plotly candlesticks** for price/patterns; line charts for MACD, RSI, OBV, etc.

## Fundamentals (Fundamental tab)

Default order:

1. **EODHD fundamentals** when `EODHD_API_KEY` is set and `EODHD_FUNDAMENTALS_ENABLED` is not `false`.
   - Parses `Financials` yearly statements including **Free cash flow** (`freeCashFlow`).
   - If HTTP **402/403** (plan lacks fundamentals): logs a clear message and falls back.
2. **SEC EDGAR** for US tickers when EODHD is skipped or fails.

Display: large currency amounts shown as **M** / **B** (see `stocks_dashboard/format_numbers.py`).

Set `EODHD_FUNDAMENTALS_ENABLED=false` to force **EDGAR-only** (skip EODHD attempt).

## Symbol format

| Input | Resolved |
| ----- | -------- |
| `AAPL` | `AAPL.US` |
| `RELIANCE.NSE` | `RELIANCE.NSE` |

## PE / ROIC (Technical tab)

Optional: EODHD `Highlights` when fundamentals API works, or Yahoo when `YAHOO_PE_ROIC_ENABLE=true` (US only).

## Environment variables (summary)

| Variable | Role |
| -------- | ---- |
| `EODHD_API_KEY` | **Required** for OHLCV; also triggers fundamentals **attempt**. |
| `EODHD_DEFAULT_EXCHANGE` | Suffix for bare symbols (default `US`). |
| `EODHD_FUNDAMENTALS_ENABLED` | `false` = skip EODHD fundamentals (EDGAR-only). Unset = attempt when key set. |
| `YAHOO_PE_ROIC_ENABLE` | `true` = use Yahoo for PE/ROIC on Technical tab (default off). |
| `SEC_USER_AGENT` | EDGAR fallback for US fundamentals. |
| `LEGACY_SOURCES` | Re-enable old multi-source chain. |
