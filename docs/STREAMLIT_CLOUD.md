---
innovator: Satyan Bansal
developer: Mukesh Kesharwani
---

# Deploy on Streamlit Community Cloud

Guide for hosting **Keekar's Stocks Status Dashboard** on [Streamlit Community Cloud](https://share.streamlit.io/) (e.g. `*.streamlit.app`).

Repository: [keekar2022/Keekar-s-StocksStatus-Dashboard](https://github.com/keekar2022/Keekar-s-StocksStatus-Dashboard)

## 1. Connect the GitHub repo

1. Sign in at [share.streamlit.io](https://share.streamlit.io/) with GitHub.
2. **Create app** → pick `keekar2022/Keekar-s-StocksStatus-Dashboard`.
3. **Main file path:** `app.py`
4. Deploy. The first build may show warnings until secrets are set (step 2).

## 2. Set secrets (API keys)

`.env` on your laptop is **not** deployed (gitignored). All keys go in **App settings → Secrets** as TOML.

1. Open your app on Streamlit Cloud → **⚙️ Settings** → **Secrets**.
2. Paste from [`.streamlit/secrets.toml.example`](../.streamlit/secrets.toml.example) and replace placeholders:

```toml
EODHD_API_KEY = "your_eodhd_token_here"
EODHD_DEFAULT_EXCHANGE = "US"
SEC_USER_AGENT = "Keekar-Stocks-Dashboard you@example.com"
```

3. **Save** — the app reboots automatically.

### Required vs optional

| Secret | Required? | Purpose |
| ------ | ----------- | ------- |
| `EODHD_API_KEY` | **Yes** for OHLCV | EODHD daily prices |
| `SEC_USER_AGENT` | Recommended for US | Free SEC EDGAR fundamentals when EODHD fundamentals are unavailable |
| `EODHD_FUNDAMENTALS_ENABLED` | Optional | Set `false` to skip EODHD fundamentals API |
| `EODHD_OHLCV_FALLBACK` | Optional | Default `true` — Yahoo fallback if EODHD 404 (e.g. NSE on US-only key) |
| `YAHOO_PE_ROIC_ENABLE` | Optional | Default `false` |

### `SEC_USER_AGENT` format

SEC [fair access](https://www.sec.gov/os/accessing-edgar-data) requires:

```text
ApplicationName you@example.com
```

Example: `Keekar-Stocks-Dashboard mukesh.kesharwani@gmail.com`

If this is missing, the sidebar shows an **info** message (not an error). US symbols still load OHLCV from EODHD; EDGAR fallback for fundamentals is skipped.

## 3. Update secrets later

1. **Settings → Secrets** → edit values → **Save**.
2. No Git push needed for secret-only changes.
3. To rotate `EODHD_API_KEY`, generate a new token at [eodhd.com/cp/dashboard](https://eodhd.com/cp/dashboard), paste in Secrets, save.

## 4. How the app loads configuration

| Environment | Source |
| ----------- | ------ |
| Local | `.env` via `python-dotenv`, and optionally `.streamlit/secrets.toml` |
| Streamlit Cloud | **Secrets** → copied into `os.environ` by `stocks_dashboard/secrets_loader.py` |

### Keep local `.env` and `secrets.toml` in sync

After editing `.env`:

```bash
python scripts/sync_secrets_from_env.py
```

This writes `.streamlit/secrets.toml` (gitignored) so `st.secrets` works locally without errors.

## 5. Common hosted-app messages

| Message | Meaning | Fix |
| ------- | ------- | --- |
| Set `EODHD_API_KEY`… | No EODHD token in Secrets | Add `EODHD_API_KEY` in Secrets and save |
| Set `SEC_USER_AGENT`… | Optional EDGAR not configured | Add `SEC_USER_AGENT` in Secrets (see above) |
| NSE/BSE / 404 for `BHEL.NSE` | Free/US-only EODHD plan | Upgrade to [EOD All-World](https://eodhd.com/pricing) or remove non-US symbols |
| OHLCV unavailable for … | EODHD + Yahoo both failed | Check keys, plan, and network |

## 6. Redeploy after code changes

Push to `main` on GitHub. Streamlit Cloud rebuilds from the default branch. Version footer updates via [`.github/workflows/version.yml`](../.github/workflows/version.yml).

## Related docs

- [EODHD_API_KEY_SETUP.md](EODHD_API_KEY_SETUP.md) — subscribe and test EODHD locally
- [DATA_SOURCES.md](DATA_SOURCES.md) — data routing
- [CONTRIBUTORS.md](CONTRIBUTORS.md) — attribution
