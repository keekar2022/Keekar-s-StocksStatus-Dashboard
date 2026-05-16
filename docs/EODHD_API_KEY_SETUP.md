---
concept: Mukesh Kesharwani
contact: mukesh.kesharwani@adobe.com
---

# EODHD API key — step-by-step (subscribe, retrieve, install, test)

This is the practical walkthrough: how to subscribe to EODHD, where to find your API key, how to put it into this project's `.env`, and how to verify it works end-to-end.

For architectural context and endpoint detail, see [EODHD_INTEGRATION.md](EODHD_INTEGRATION.md). For where this key fits in the routing, see [DATA_SOURCES.md](DATA_SOURCES.md).

## TL;DR

1. Sign up at [https://eodhd.com/register](https://eodhd.com/register).
2. Subscribe to **"EOD Historical Data - All World"** (~$17.99/mo) at [https://eodhd.com/pricing](https://eodhd.com/pricing) — or use the free trial / demo token first.
3. Copy your API token from the dashboard at [https://eodhd.com/cp/dashboard](https://eodhd.com/cp/dashboard).
4. Paste it into the project's `.env` as `EODHD_API_KEY=...` (local) or **Streamlit Cloud Secrets** (hosted).
5. Run `streamlit run app.py` and load `AAPL.US`.

**Hosted on Streamlit Cloud?** See [STREAMLIT_CLOUD.md](STREAMLIT_CLOUD.md) — use **App settings → Secrets**, not `.env`.

## 1. Choose how you'll evaluate vs. use long-term

| Option | URL | Notes |
| ------ | --- | ----- |
| **Free demo token** | [https://eodhd.com/financial-apis/api-demo-key](https://eodhd.com/financial-apis/api-demo-key) | Public token `demo`. Limited to a small handful of US tickers (e.g. `AAPL.US`, `MCD.US`). Great for verifying the wiring without paying. |
| **Free trial (account)** | [https://eodhd.com/register](https://eodhd.com/register) | Register an account; trial credits land in your dashboard. |
| **Paid - EOD All-World** | [https://eodhd.com/pricing](https://eodhd.com/pricing) (currently linked from [https://eodhd.com/pricing-special-10](https://eodhd.com/pricing-special-10)) | ~$17.99/mo. Covers OHLCV across 70+ exchanges, 20+ years of history, ~100k calls/day. This is the plan this project is designed around. |
| **Paid - Fundamentals add-on** | Same pricing page | ~$53.99/mo. Required for **Free cash flow** and full financials on the Fundamental tab. The app **tries** fundamentals when `EODHD_API_KEY` is set; HTTP 403 means you need this add-on (then EDGAR fallback for US). |

Pricing and limits change; always confirm on the live pricing page before subscribing.

## 2. Subscribe (paid path)

1. Open [https://eodhd.com/pricing](https://eodhd.com/pricing) in your browser.
2. Pick **"EOD Historical Data - All World"** (monthly or annual). The annual plan is cheaper per month.
3. Click **Subscribe** / **Get plan** and complete checkout (Stripe / PayPal supported).
4. After checkout you'll land back in your account dashboard. The active plan badge should reflect the new subscription within a minute.

If you just want to test first, skip to step 3 with the demo token.

## 3. Retrieve your API token

1. Sign in at [https://eodhd.com/cp/dashboard](https://eodhd.com/cp/dashboard).
2. Look for the **API Token** / **API Key** card on the dashboard (also reachable via **Settings** -> **Secret Key** / **API Token**).
3. Click **Show / Copy** to reveal the token. It looks like a long alphanumeric string, often with a dot separator, for example:

```text
6a07fe39db3f54.04964801
```

4. Keep this token private. If it leaks, regenerate it from the same dashboard.

For the demo path, the token is literally the string `demo`.

## 4. Put the key into this project

The repo loads environment variables from a local `.env` file at the project root (`/Users/<you>/Documents/Stocks-Dashboard/.env`). This file is **not** checked into git.

### 4a. Create or open `.env`

If you don't yet have one, copy the template:

```bash
cd /Users/<you>/Documents/Stocks-Dashboard
cp .env.example .env
```

### 4b. Set the EODHD key

Open `.env` in your editor and set:

```bash
EODHD_API_KEY=PASTE_YOUR_TOKEN_HERE
EODHD_DEFAULT_EXCHANGE=US
# Optional: EODHD_FUNDAMENTALS_ENABLED=false   # skip EODHD fundamentals, EDGAR-only
```

If you only want to smoke-test with the demo token:

```bash
EODHD_API_KEY=demo
```

Optional (recommended for US fundamentals via free SEC EDGAR):

```bash
SEC_USER_AGENT=Your-App you@example.com
```

Leave the legacy block as-is unless you specifically want the old Yahoo / Alpha Vantage / Investing chain back:

```bash
LEGACY_SOURCES=false
```

Save the file.

### 4c. Make sure `.env` is not committed

This project's `.gitignore` should already exclude `.env`. Verify with:

```bash
git check-ignore -v .env
```

If the command prints a matching rule, you're safe. If not, add `.env` to `.gitignore` before any commit. **Never** commit a real API token; rotate immediately if you accidentally do.

## 5. Verify the key (no Streamlit required)

From the project root, with your virtualenv active:

```bash
cd /Users/<you>/Documents/Stocks-Dashboard
source .venv/bin/activate
python - <<'PY'
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.env'))

from stocks_dashboard.eodhd_client import fetch_ohlcv
df = fetch_ohlcv('AAPL.US')
print(df.tail(3))
print('rows:', len(df))
PY
```

Expected: a 3-row tail with `Open / High / Low / Close / Adjusted_close / Volume` and a total row count in the thousands. Common errors and what they mean:

| Error message | Likely cause | Fix |
| ------------- | ------------ | --- |
| `EODHD_API_KEY is not set` | `.env` not loaded or variable empty | Confirm `EODHD_API_KEY=...` and that you ran from the project root. |
| `EODHD authentication failed (HTTP 401/403)` | Wrong / revoked token, or plan doesn't cover endpoint | Re-copy the token from the dashboard; confirm subscription is active. |
| `EODHD 404 ... symbol/exchange not found` | Bad `SYMBOL.EXCHANGE` | Try `AAPL.US`; check the supported-exchanges page below. |
| `EODHD rate-limited (HTTP 429)` | Burst over the per-minute cap | Wait a minute and retry; upgrade plan if persistent. |

Supported exchanges and their suffixes are listed at [https://eodhd.com/financial-apis/list-supported-exchanges](https://eodhd.com/financial-apis/list-supported-exchanges).

## 6. Verify end-to-end in the Streamlit app

```bash
streamlit run app.py
```

In the browser:

1. Confirm the sidebar does **not** show the yellow "Set `EODHD_API_KEY`" warning.
2. In the symbol box, enter `AAPL.US, RELIANCE.NSE, VOD.LSE` (or just `AAPL.US` on the demo token).
3. Data should **auto-load**; or use **Refresh data** on a tab. Each symbol's quote strip should read:

```text
EODHD (AAPL.US)
```

with last close, day % change, and ~1Y high/low populated. For `AAPL.US` the PE / ROIC blocks will also appear (Yahoo-based, US only).

## 7. Rotating or replacing the key

If the token leaks or you change plan:

1. Sign in to [https://eodhd.com/cp/dashboard](https://eodhd.com/cp/dashboard).
2. Open the API Token card and choose **Regenerate** (or revoke + create a new one if the UI offers that).
3. Update `EODHD_API_KEY=...` in your local `.env` (or **Streamlit Cloud → Secrets** if hosted).
4. Restart the app (`streamlit run app.py` locally, or save Secrets on Cloud).

## 8. Sharing this project with friends safely

When sharing the codebase:

- Share `docs/EODHD_API_KEY_SETUP.md` and `docs/EODHD_INTEGRATION.md` so they can subscribe with their own account.
- Do **not** share your `.env`. Each developer must get their own EODHD token (free demo, trial, or paid plan).
- The `.env.example` file is safe to share — it has placeholders only.

## 9. Useful links

- Sign up: [https://eodhd.com/register](https://eodhd.com/register)
- Pricing: [https://eodhd.com/pricing](https://eodhd.com/pricing)
- Account / API token: [https://eodhd.com/cp/dashboard](https://eodhd.com/cp/dashboard)
- Demo token info: [https://eodhd.com/financial-apis/api-demo-key](https://eodhd.com/financial-apis/api-demo-key)
- Historical OHLCV docs: [https://eodhd.com/financial-apis/api-for-historical-data-and-volumes](https://eodhd.com/financial-apis/api-for-historical-data-and-volumes)
- Fundamentals docs: [https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds](https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds)
- Supported exchanges: [https://eodhd.com/financial-apis/list-supported-exchanges](https://eodhd.com/financial-apis/list-supported-exchanges)
- Status / support: [https://eodhd.com/financial-apis/contacts](https://eodhd.com/financial-apis/contacts)
