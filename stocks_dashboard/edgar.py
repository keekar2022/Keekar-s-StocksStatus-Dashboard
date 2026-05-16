# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""SEC EDGAR Data API client (company tickers + company facts)."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

import requests

_DOTENV_BOOTSTRAPPED = False


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_dotenv_loaded() -> None:
    """Load ``.env`` from repo root (cwd may differ under Streamlit) and bootstrap if missing."""
    global _DOTENV_BOOTSTRAPPED
    if _DOTENV_BOOTSTRAPPED:
        return
    _DOTENV_BOOTSTRAPPED = True
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    root = _project_root()
    env_path = root / ".env"
    example = root / ".env.example"
    load_dotenv(env_path)
    if (os.environ.get("SEC_USER_AGENT") or "").strip():
        return
    if not env_path.exists() and example.exists():
        shutil.copy(example, env_path)
        load_dotenv(env_path, override=True)


def _read_sec_user_agent() -> str:
    _ensure_dotenv_loaded()
    ua = (os.environ.get("SEC_USER_AGENT") or "").strip()
    if ua:
        return ua
    try:
        import streamlit as st

        sec = getattr(st, "secrets", None)
        if sec is not None and "SEC_USER_AGENT" in sec:
            return str(sec["SEC_USER_AGENT"]).strip()
    except Exception:
        pass
    return ""

SEC_TICKERS_JSON = "https://www.sec.gov/files/company_tickers.json"
COMPANY_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


class EdgarError(Exception):
    pass


def _headers() -> dict[str, str]:
    ua = _read_sec_user_agent()
    if not ua or ("@" not in ua and "http" not in ua.lower()):
        env_path = _project_root() / ".env"
        raise EdgarError(
            "Set SEC_USER_AGENT to a string that identifies you (include an email or https URL), "
            "per https://www.sec.gov/os/accessing-edgar-data — "
            f"add it to {env_path} or Streamlit secrets, then restart the app. "
            "If .env is missing, copy .env.example to .env (the example includes a valid format)."
        )
    return {"User-Agent": ua, "Accept-Encoding": "gzip, deflate", "Host": "www.sec.gov"}


def _data_headers() -> dict[str, str]:
    ua = _read_sec_user_agent()
    if not ua:
        env_path = _project_root() / ".env"
        raise EdgarError(
            f"Set SEC_USER_AGENT in {env_path} or Streamlit secrets (same value as for www.sec.gov)."
        )
    return {"User-Agent": ua, "Accept-Encoding": "gzip, deflate", "Host": "data.sec.gov"}


_http_session: requests.Session | None = None
_last_request: float = 0.0


def _throttle(min_interval_s: float = 0.12) -> None:
    global _last_request
    now = time.monotonic()
    wait = min_interval_s - (now - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def get_http_session() -> requests.Session:
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
    return _http_session


def fetch_ticker_cik_map() -> dict[str, int]:
    """Map upper-case ticker -> integer CIK (as in company_tickers.json)."""
    _throttle()
    r = get_http_session().get(SEC_TICKERS_JSON, headers=_headers(), timeout=60)
    if not r.ok:
        raise EdgarError(f"Ticker map HTTP {r.status_code}")
    data = r.json()
    out: dict[str, int] = {}
    if isinstance(data, dict):
        for v in data.values():
            if not isinstance(v, dict):
                continue
            t = str(v.get("ticker", "")).strip().upper()
            raw = v.get("cik_str", v.get("cik"))
            if not t or raw is None:
                continue
            try:
                out[t] = int(raw)
            except (TypeError, ValueError):
                continue
    if not out:
        raise EdgarError("Could not parse SEC company_tickers.json")
    return out


def cik_to_url_cik(cik: int) -> str:
    return f"{cik:010d}"


def fetch_company_facts(cik: int) -> dict[str, Any]:
    url = COMPANY_FACTS.format(cik=cik_to_url_cik(cik))
    _throttle()
    r = get_http_session().get(url, headers=_data_headers(), timeout=90)
    if r.status_code == 404:
        raise EdgarError(f"No company facts for CIK {cik}")
    if not r.ok:
        raise EdgarError(f"Company facts HTTP {r.status_code}")
    return r.json()


def resolve_cik(ticker: str, cache: dict[str, int] | None = None) -> int:
    t = ticker.strip().upper()
    m = cache or fetch_ticker_cik_map()
    if t not in m:
        raise EdgarError(f"Ticker {t!r} not found in SEC ticker list (US listings).")
    return m[t]
