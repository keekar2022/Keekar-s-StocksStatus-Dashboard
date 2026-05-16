---
concept: Mukesh Kesharwani
contact: mukesh.kesharwani@adobe.com
---

# Free technical data (MACD, RSI, and OHLCV)

## How momentum data is produced

The dashboard **does not** buy MACD or RSI from EODHD. Flow:

1. **OHLCV** — daily Open, High, Low, Close, Volume from Yahoo and/or EODHD.
2. **Indicators** — computed locally in [`stocks_dashboard/technical_indicators.py`](../stocks_dashboard/technical_indicators.py) with the [`ta`](https://github.com/bukosabino/ta) library (EMA, MACD 12/26/9, RSI 14, OBV, ADL, PSAR).

That matches what most free chart sites do: they derive indicators from price history rather than selling pre-built momentum series.

## Minimizing EODHD usage

| Variable | Default | Role |
| -------- | ------- | ---- |
| `OHLCV_PRIMARY` | `yahoo` | Yahoo first; EODHD only when Yahoo fails (if key set) |
| `EODHD_OHLCV_FALLBACK` | `true` | Enable cross-fallback between Yahoo and EODHD |
| `OHLCV_CACHE_TTL_HOURS` | `24` | Reuse disk cache without live API calls until stale or **Refresh data** |
| `EODHD_FUNDAMENTALS_ENABLED` | (attempt if key) | Set `false` to avoid paid fundamentals add-on; use SEC EDGAR for US |

### Example profiles

| Goal | Settings |
| ---- | ---------- |
| US technicals, minimal EODHD | `OHLCV_PRIMARY=yahoo`, optional `EODHD_API_KEY` for fallback |
| Global watchlist | `OHLCV_PRIMARY=yahoo` + EODHD key for symbols Yahoo misses |
| EODHD-first (previous behavior) | `OHLCV_PRIMARY=eodhd` |
| No EODHD at all (US POC) | Omit `EODHD_API_KEY`, `OHLCV_PRIMARY=yahoo` |
| Free US fundamentals | `EODHD_FUNDAMENTALS_ENABLED=false`, `SEC_USER_AGENT` set |

## When EODHD is still needed

- Exchanges or tickers **Yahoo does not cover** reliably.
- You want a **single vendor** for corporate actions / symbol resolution (`OHLCV_PRIMARY=eodhd`).
- **Fundamentals** beyond free SEC EDGAR (optional paid EODHD fundamentals add-on).

NSE/BSE often work on Yahoo as `SYMBOL.NS` / `SYMBOL.BO` (mapped from `SYMBOL.NSE` in code). If both Yahoo and EODHD fail, check your EODHD plan or symbol suffix.

## Annual ROIC (US, free)

The **ROIC — annual approximation** expander (Technical tab, **1 year** / **5 years**) uses:

1. **SEC EDGAR** — NOPAT / invested capital from US-GAAP company facts (`SEC_USER_AGENT` required). Same public filings as the Fundamental tab.
2. **Yahoo** — optional if `YAHOO_PE_ROIC_ENABLE=true` and statements load.
3. **EODHD** — yearly `Financials` when your plan includes fundamentals.

You do **not** need Yahoo or a paid EODHD fundamentals add-on for US annual ROIC if EDGAR is configured.

## What we do not recommend

- Alpha Vantage **MACD/RSI API** endpoints — rate-limited, redundant with local `ta`, and values may differ slightly from dashboard settings.
- Scraping third-party sites that display indicators — fragile and often against terms of service.

See also [DATA_SOURCES.md](DATA_SOURCES.md) and [EODHD_INTEGRATION.md](EODHD_INTEGRATION.md).
