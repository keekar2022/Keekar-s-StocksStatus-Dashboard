# Innovator & concept: Satyan Bansal — satyan.bansal@gmail.com
# Developer: Mukesh Kesharwani — mukesh.kesharwani@adobe.com

# Keekar's Stocks Status Dashboard

Streamlit app for monitoring tickers (comma-separated, max **10**): **Fundamental**, **Technical Indicators**, and **Patterns** tabs.

Repository: [keekar2022/Keekar-s-StocksStatus-Dashboard](https://github.com/keekar2022/Keekar-s-StocksStatus-Dashboard)

## Authors & attribution

| Role | Name | Contact |
| --- | --- | --- |
| **Innovator & concept** | Satyan Bansal | [satyan.bansal@gmail.com](mailto:satyan.bansal@gmail.com) |
| **Developer (implementation)** | Mukesh Kesharwani | [mukesh.kesharwani@adobe.com](mailto:mukesh.kesharwani@adobe.com) |

The dashboard **concept** — a single view of key stock parameters across fundamentals, technicals, and patterns — was introduced by **Satyan Bansal**. **Mukesh Kesharwani** developed the code, integrations, and UI in this repository.

Full details: **[docs/CONTRIBUTORS.md](docs/CONTRIBUTORS.md)**

## Features

- **EODHD-first** global OHLCV and fundamentals (with SEC EDGAR fallback for US tickers)
- **Auto-load** on open; disk cache survives browser refresh
- **Persistent symbol list** (default: `AAPL.US, ADBE.US, BHEL.NSE, MSFT.US, RELIANCE.NSE`)
- **Refresh data** per tab or **Refresh all** in the sidebar
- **Version footer** shows build id and link to the latest commit on `main` (from CI-generated `stocks_dashboard/_version.py`)

## Quick start

```bash
cd Stocks-Dashboard
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # set EODHD_API_KEY, optional SEC_USER_AGENT
streamlit run app.py
```

See **[docs/EODHD_API_KEY_SETUP.md](docs/EODHD_API_KEY_SETUP.md)** for API key setup and **[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)** for data routing.

### Streamlit Community Cloud (share.streamlit.io)

`.env` is **not** deployed. Set secrets in the hosted app — full guide: **[docs/STREAMLIT_CLOUD.md](docs/STREAMLIT_CLOUD.md)**.

1. [share.streamlit.io](https://share.streamlit.io/) → your app → **⚙️ Settings** → **Secrets**
2. Paste from [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example) and replace values
3. **Save** (app reboots)

Minimum secrets: `EODHD_API_KEY`, `SEC_USER_AGENT` (format: `AppName you@example.com`).

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
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | EODHD, EDGAR, legacy chain |
| [docs/EODHD_INTEGRATION.md](docs/EODHD_INTEGRATION.md) | Single-API integration |
| [docs/EODHD_API_KEY_SETUP.md](docs/EODHD_API_KEY_SETUP.md) | Subscribe and configure API key |

## Notes

- Never commit `.env` (API keys). `.env.example` is the template.
- Yahoo paths are optional (`YAHOO_PE_ROIC_ENABLE=true`); disabled by default on restrictive networks.
