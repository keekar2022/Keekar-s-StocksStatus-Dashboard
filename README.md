# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

# Keekar's Stocks Status Dashboard

Streamlit app for monitoring tickers (comma-separated, max **10**): **Fundamental**, **Technical Indicators**, and **Patterns** tabs.

Repository: [keekar2022/Keekar-s-StocksStatus-Dashboard](https://github.com/keekar2022/Keekar-s-StocksStatus-Dashboard)

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
