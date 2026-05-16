---
innovator: Satyan Bansal
developer: Mukesh Kesharwani
---

# Keekar's Stocks Status Dashboard — portable plan & progress

Use this document in **any IDE** or share it as a **single reference** for what the POC does, how data flows, what to configure, and what was built so far. For deeper API detail, see [DATA_SOURCES.md](DATA_SOURCES.md).

## Purpose

- **Streamlit POC** for global tickers: fundamentals, technical indicators (`ta`), and heuristic pattern scans.
- **Single API by default**: **EODHD** for global OHLCV, **SEC EDGAR** as a free US-only fundamentals enhancer. Legacy multi-source chain is preserved behind `LEGACY_SOURCES=true` for offline / no-key runs.

## Quick start (any machine)

1. Clone or copy the repo folder.
2. Python 3.14+ recommended (project targets 3.14; adjust if your environment differs).

```bash
cd Stocks-Dashboard
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # set EODHD_API_KEY (+ optional SEC_USER_AGENT)
streamlit run app.py
```

3. Open the URL Streamlit prints (usually `http://localhost:8501`).
4. Enter symbols using `SYMBOL.EXCHANGE` (e.g. `AAPL.US`, `RELIANCE.NSE`, `VOD.LSE`). Bare symbols default to `.<EODHD_DEFAULT_EXCHANGE>` (usually `.US`). Max 10 per run.
5. Use the three tabs: **Fundamental**, **Technical Indicators**, **Patterns**. Data **auto-loads**; use **Refresh data** per tab.

**Attribution:** Concept by **Satyan Bansal**; implementation by **Mukesh Kesharwani** — see [CONTRIBUTORS.md](CONTRIBUTORS.md).

**Streamlit Cloud:** Secrets, not `.env` — [STREAMLIT_CLOUD.md](STREAMLIT_CLOUD.md).

## Inputs (environment)

**Local:** copy `.env.example` → `.env`. **Hosted:** [STREAMLIT_CLOUD.md](STREAMLIT_CLOUD.md). Summary:

| Input | Purpose |
| ----- | ------- |
| `EODHD_API_KEY` | **Required** for OHLCV; subscribe to "EOD Historical Data - All World" (~$18/mo) at [eodhd.com](https://eodhd.com). |
| `EODHD_DEFAULT_EXCHANGE` | Suffix for bare symbols (default `US`). |
| `EODHD_FUNDAMENTALS_ENABLED` | Set `false` to skip EODHD fundamentals (EDGAR-only). Attempted when API key is set. |
| `EODHD_OHLCV_FALLBACK` | Default `true` — Yahoo OHLCV if EODHD 404 (e.g. NSE on US-only key). |
| `SEC_USER_AGENT` | Identifies your app to **SEC EDGAR**; required for free US fundamentals fallback. |
| `LEGACY_SOURCES` | `true` to re-enable Yahoo / Alpha Vantage / Investing chain. Default `false`. |
| `ALPHA_VANTAGE_API_KEY` | Legacy-only; only honoured when `LEGACY_SOURCES=true`. |
| `ALPHA_VANTAGE_CALL_INTERVAL_SEC` | Legacy throttle between Alpha Vantage calls (default `12.5`). |
| `INVESTING_ENABLE` | Legacy-only; default `true` but only used when `LEGACY_SOURCES=true`. |
| `NASDAQ_DATA_LINK_API_KEY` | Optional Nasdaq Data Link key. |
| `NASDAQ_DATA_LINK_CODE` | Optional dataset code for supplementary preview on Fundamental tab. |
| `NASDAQ_DATA_LINK_ROWS` | Optional row cap for that preview (default `250`). |

See [EODHD_INTEGRATION.md](EODHD_INTEGRATION.md) for signup, symbol format, and endpoint details.

## Data architecture (single-API mode)

### OHLCV (technicals + patterns)

**EODHD** `GET /api/eod/{SYMBOL}.{EX}` is the only path. Implemented in `stocks_dashboard/eodhd_client.fetch_ohlcv` and surfaced via `stocks_dashboard/data_sources.fetch_ohlcv_preferred`.

### Fundamentals

1. **EODHD fundamentals** first when `EODHD_API_KEY` is set (includes **Free cash flow**); requires fundamentals on your EODHD plan.
2. **SEC EDGAR** fallback for US tickers if EODHD returns 403 or is skipped (`EODHD_FUNDAMENTALS_ENABLED=false`).

Fundamental tab displays currency rows in **M/B** notation. Per-symbol **Source attempt log** records each step.

### Legacy mode (`LEGACY_SOURCES=true`)

OHLCV: **Yahoo -> Alpha Vantage -> Investing.com**. Fundamentals: **EDGAR -> Yahoo -> Alpha Vantage OVERVIEW**.

### PE / ROIC on Technical tab

The **PE (TTM proxy)** and **ROIC** blocks still call **Yahoo** (`yfinance`) and only run for **US** listings (bare or `.US`). Non-US listings show indicators without PE/ROIC overlays.

## UI / presentation progress (screener.in–inspired)

**Goal:** Cleaner company-style layout (inspired by layouts like [screener.in company chart pages](https://www.screener.in/company/ABB/#chart)) — **not affiliated** with that site.

| Piece | Location / behavior |
| ----- | ------------------- |
| Theme | `.streamlit/config.toml` — calm green accent, readable defaults. |
| Global CSS | `stocks_dashboard/ui_screener.py` — `inject_screener_like_css()` (tabular metrics, section title color). |
| Quote strip | `render_quote_hero()` — bordered block: symbol, last close + day % change, session date, ~252-session high/low, OHLCV source caption. Used on **Technical** and **Patterns** after OHLCV load. |
| Fundamentals layout | Bordered container + green symbol title + “Financial snapshot” label (`app.py`). |
| Horizon tabs | **Technical:** 1M (~21), **6M (~126)**, 1Y (~252), 5Y (full loaded history). **Patterns:** 1W, 1M, **6M**, 1Y, 5Y. |
| Chart grouping | Technicals: **Plotly candlesticks** for price; line charts for MACD/RSI/volume. Patterns: candlesticks. |
| Compact numbers | `format_fundamentals_display()` — M/B on Fundamental tab. |
| Horizons in code | `Horizon` in `stocks_dashboard/yahoo_ohlcv.py` includes `6M` via `slice_trading_window`. |

## Key source files (map for collaborators)

| Area | Files |
| ---- | ----- |
| App shell & tabs | `app.py` |
| EODHD client (primary) | `stocks_dashboard/eodhd_client.py` |
| EODHD fundamentals table | `stocks_dashboard/eodhd_fundamentals.py` |
| Charts (candlestick) | `stocks_dashboard/ui_charts.py` |
| Number formatting | `stocks_dashboard/format_numbers.py` |
| EDGAR (US fundamentals enhancer) | `stocks_dashboard/edgar.py` |
| Routing | `stocks_dashboard/data_sources.py` |
| Yahoo OHLCV + horizons | `stocks_dashboard/yahoo_ohlcv.py` *(slice helper used by all sources; full fetch only in legacy)* |
| Alpha Vantage | `stocks_dashboard/alphavantage.py` *(legacy only)* |
| Investing fallback | `stocks_dashboard/investing_ohlcv.py` *(legacy only)* |
| Indicators | `stocks_dashboard/technical_indicators.py` |
| Patterns | `stocks_dashboard/chart_patterns.py` |
| Presentation helpers | `stocks_dashboard/ui_screener.py` |
| Docs | `docs/EODHD_INTEGRATION.md`, `docs/DATA_SOURCES.md`, `README.md` |

## Disclaimers (share with friends)

- **POC / educational** — not investment advice; pattern labels are heuristics.
- **Licensing & ToS** — confirm terms before production use (EODHD, SEC EDGAR, and any legacy sources you re-enable).
- **EODHD cost** — paid subscription required (~$18/mo for OHLCV; fundamentals add-on is separate).
- **Yahoo PE/ROIC** — only run for US listings; silently skipped elsewhere.
- **Legacy mode** — Investing.com remains unofficial; Alpha Vantage free tier remains rate-limited.

## Optional next steps (not committed as requirements)

- Replace the Yahoo-based PE/ROIC blocks with EODHD fundamentals (requires the add-on).
- Local SQLite cache (`requests_cache`) in front of EODHD to stay well under daily quota.
- Symbol picker / autocomplete via `GET /api/exchange-symbol-list/{EX}`.
- Pros/cons or peer columns (would need curated data or LLM — out of scope for current POC).
- Export SBOM / CI docs if you open-source on GitHub (see your org's compliance checklist).

---

*Last aligned with repo behavior: single-API EODHD mode, EDGAR US enhancer, legacy chain gated behind `LEGACY_SOURCES`, Screener-like UI, `6M` horizon.*
