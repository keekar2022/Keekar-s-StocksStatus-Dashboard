# Concept & Innovation: Satyan Bansal — satyan.bansal@gmail.com
# Developer: Mukesh Kesharwani — mukesh.kesharwani@adobe.com

# Keekar's Stocks Status Dashboard

**Keekar's Stocks Status Dashboard** is a Streamlit web app for tracking up to **10** stock tickers in one place. Enter symbols such as `AAPL.US` or `RELIANCE.NSE`, and the app loads **fundamentals**, **technical indicators** (MACD, RSI, EMAs, and more), and **chart pattern** scans across multiple time horizons. Price history comes from **Yahoo Finance** and/or **EODHD**; US fundamentals can use free **SEC EDGAR** filings; indicators are computed locally (no paid “momentum API”). Data is cached on disk, your symbol list persists between visits, and each tab can be refreshed independently.

Repository: [keekar2022/Keekar-s-StocksStatus-Dashboard](https://github.com/keekar2022/Keekar-s-StocksStatus-Dashboard)

## Project scale

Approximate size of **first-party code** in this repository (May 2026):

| Area | Lines (approx.) | Notes |
| --- | ---: | --- |
| **Python application** | **~4,900** | `app.py`, `stocks_dashboard/` package, `scripts/` |
| — Streamlit UI & orchestration | ~710 | [`app.py`](app.py) |
| — Data clients & indicators | ~4,050 | [`stocks_dashboard/`](stocks_dashboard/) (OHLCV, EDGAR, EODHD, `ta`, charts, cache) |
| — Tooling | ~160 | [`scripts/`](scripts/) (version stamp, secrets sync) |
| **Documentation** | ~670 | [`docs/`](docs/) guides and architecture notes |
| **CI workflows** | ~110 | GitHub Actions (version embed, SBOM) |

*Excludes:* `node_modules`, `.venv`, lockfiles, secrets, disk cache, and auto-generated [`stocks_dashboard/_version.py`](stocks_dashboard/_version.py) from CI.

## Authors & attribution

| Role | Name | Contact |
| --- | --- | --- |
| **Concept & Innovation** | Satyan Bansal | [satyan.bansal@gmail.com](mailto:satyan.bansal@gmail.com) |
| **Developer (implementation)** | Mukesh Kesharwani | [mukesh.kesharwani@adobe.com](mailto:mukesh.kesharwani@adobe.com) |

The dashboard **concept** — a single view of key stock parameters across fundamentals, technicals, and patterns — was introduced by **Satyan Bansal**. **Mukesh Kesharwani** developed the code, integrations, and UI in this repository.

Full details: **[docs/CONTRIBUTORS.md](docs/CONTRIBUTORS.md)**

## Features

- **Yahoo-first OHLCV** with optional EODHD fallback (`OHLCV_PRIMARY=yahoo`); MACD/RSI computed locally via `ta`
- **Fundamentals:** EODHD when enabled, **SEC EDGAR** (free) for US tickers; annual **ROIC** from EDGAR on Technical tab
- **Auto-load** on open; disk cache with TTL (`OHLCV_CACHE_TTL_HOURS`)
- **Persistent symbol list** (default: `AAPL.US, ADBE.US, BHEL.NSE, MSFT.US, RELIANCE.NSE`)
- **Refresh data** per tab or **Refresh all** next to the symbol field
- **Chart or table** view for technicals and patterns
- **Version footer** with build id and link to the latest commit on `main`

## Quick start

```bash
cd Stocks-Dashboard
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # set EODHD_API_KEY (optional), SEC_USER_AGENT for US EDGAR
streamlit run app.py
```

See **[docs/EODHD_API_KEY_SETUP.md](docs/EODHD_API_KEY_SETUP.md)** for API key setup, **[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)** for routing, and **[docs/FREE_TECHNICAL_DATA.md](docs/FREE_TECHNICAL_DATA.md)** for free MACD/RSI and ROIC paths.

### Streamlit Community Cloud (share.streamlit.io)

`.env` is **not** deployed. Set secrets in the hosted app — full guide: **[docs/STREAMLIT_CLOUD.md](docs/STREAMLIT_CLOUD.md)**.

1. [share.streamlit.io](https://share.streamlit.io/) → your app → **⚙️ Settings** → **Secrets**
2. Paste from [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example) and replace values
3. **Save** (app reboots)

Minimum for US fundamentals and annual ROIC: `SEC_USER_AGENT` (format: `AppName you@example.com`). Optional: `EODHD_API_KEY` for global OHLCV fallback.

## Version embedding

On each push to **`main`**, GitHub Actions runs [`.github/workflows/version.yml`](.github/workflows/version.yml) to regenerate `stocks_dashboard/_version.py` from the commit SHA and timestamp.

Local dev:

```bash
python scripts/write_version.py
```

## Security & Compliance

### Software Bill of Materials (SBOM)

SBOM is generated on pushes to `main` via [`.github/workflows/sbom-generation.yml`](.github/workflows/sbom-generation.yml).

- **SBOM:** `docs/sbom.json` (CycloneDX 1.5)
- **CBOM:** `docs/cbom.json` (Python cryptography inventory)

Manual generation:

```bash
npm install -g @cyclonedx/cdxgen
mkdir -p docs
cdxgen -t python -r -o docs/sbom.json --spec-version 1.5 --json-pretty --evidence
```

## Documentation

| Doc | Purpose |
| --- | --- |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | Yahoo/EODHD OHLCV, EDGAR, PE/ROIC |
| [docs/FREE_TECHNICAL_DATA.md](docs/FREE_TECHNICAL_DATA.md) | Local indicators, minimizing EODHD |
| [docs/EODHD_INTEGRATION.md](docs/EODHD_INTEGRATION.md) | EODHD integration |
| [docs/EODHD_API_KEY_SETUP.md](docs/EODHD_API_KEY_SETUP.md) | API key setup |
| [docs/STREAMLIT_CLOUD.md](docs/STREAMLIT_CLOUD.md) | Deploy and secrets |

## Notes

- Never commit `.env` or `.streamlit/secrets.toml` (API keys). Use `.env.example` / `secrets.toml.example` as templates.
- Yahoo PE/ROIC is optional (`YAHOO_PE_ROIC_ENABLE=true`); US annual ROIC works from **SEC EDGAR** without Yahoo.
