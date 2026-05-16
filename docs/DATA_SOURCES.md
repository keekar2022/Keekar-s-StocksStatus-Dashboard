---
concept: Mukesh Kesharwani
contact: mukesh.kesharwani@adobe.com
---

# Data sources

OHLCV defaults to **Yahoo first** (`OHLCV_PRIMARY=yahoo`), with **EODHD** as fallback when a key is set. **MACD, RSI, and other technicals** are computed locally via the `ta` library — not fetched from EODHD. See [FREE_TECHNICAL_DATA.md](FREE_TECHNICAL_DATA.md).

Fundamentals: **EODHD attempt** (optional paid add-on) then **SEC EDGAR** (US). Legacy Yahoo / Alpha Vantage / Investing.com is off unless `LEGACY_SOURCES=true`.

See [EODHD_INTEGRATION.md](EODHD_INTEGRATION.md) and [EODHD_API_KEY_SETUP.md](EODHD_API_KEY_SETUP.md).

## OHLCV (Technical Indicators & Patterns)

Routing in `stocks_dashboard/data_sources.py`:

| `OHLCV_PRIMARY` | Order |
| --------------- | ----- |
| `yahoo` (default) | Yahoo chart API → EODHD (if `EODHD_API_KEY` and `EODHD_OHLCV_FALLBACK=true`) |
| `eodhd` | EODHD → Yahoo fallback |

Charts: **Plotly** candlesticks and line charts. Tables available via **View charts as** on Technical and Patterns tabs.

Disk cache: `OHLCV_CACHE_TTL_HOURS` (default 24) — fresh cache skips live fetch until **Refresh data**.

## Fundamentals (Fundamental tab)

Default order:

1. **EODHD fundamentals** when `EODHD_API_KEY` is set and `EODHD_FUNDAMENTALS_ENABLED` is not `false`.
2. **SEC EDGAR** for US tickers when EODHD is skipped or fails.

Set `EODHD_FUNDAMENTALS_ENABLED=false` to force **EDGAR-only** (skip EODHD attempt).

## Symbol format

| Input | Resolved |
| ----- | -------- |
| `AAPL` | `AAPL.US` |
| `RELIANCE.NSE` | `RELIANCE.NSE` (Yahoo: `RELIANCE.NS`) |

## PE / ROIC (Technical tab, US listings)

| Metric | Sources (in order) |
| ------ | ------------------- |
| **Latest ROIC / ROE** | EODHD Highlights, else Yahoo `info` if `YAHOO_PE_ROIC_ENABLE=true` |
| **Annual ROIC table** | **SEC EDGAR** company facts (free, `SEC_USER_AGENT`) → Yahoo statements → EODHD yearly `Financials` |

Annual ROIC appears on **1 year** and **5 years** horizon tabs under **ROIC — annual approximation**. Non-US symbols do not show this block (EDGAR is US-only).

Implementation: [`stocks_dashboard/roic.py`](../stocks_dashboard/roic.py), [`stocks_dashboard/valuation.py`](../stocks_dashboard/valuation.py).

## Environment variables (summary)

| Variable | Role |
| -------- | ---- |
| `OHLCV_PRIMARY` | `yahoo` (default) or `eodhd` — OHLCV provider order |
| `EODHD_OHLCV_FALLBACK` | `true` = cross-fallback between Yahoo and EODHD |
| `OHLCV_CACHE_TTL_HOURS` | Cache max age before auto-refresh (default `24`; `0` = no age expiry) |
| `EODHD_API_KEY` | Optional with Yahoo-first; required for EODHD-first and EODHD fallback |
| `EODHD_DEFAULT_EXCHANGE` | Suffix for bare symbols (default `US`) |
| `EODHD_FUNDAMENTALS_ENABLED` | `false` = skip EODHD fundamentals (EDGAR-only) |
| `YAHOO_PE_ROIC_ENABLE` | `true` = Yahoo PE/ROIC on Technical tab (default off) |
| `SEC_USER_AGENT` | **Required** for free US EDGAR fundamentals and annual ROIC (public 10-K data) |
| `LEGACY_SOURCES` | Re-enable old multi-source chain |
