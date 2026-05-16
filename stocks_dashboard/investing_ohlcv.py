# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""
Unofficial Investing.com daily OHLCV (POC).

Investing.com does not publish a supported public bulk API for this use case. This module:

- Resolves instruments via ``https://api.investing.com/api/search/v2/search`` (JSON).
- Pulls history via ``POST https://www.investing.com/instruments/HistoricalDataAjax`` (HTML table).

Some networks receive a Cloudflare interstitial instead of data; callers should fall back to Yahoo.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pandas as pd
import requests

_SEARCH_URL = "https://api.investing.com/api/search/v2/search"
_HIST_URL = "https://www.investing.com/instruments/HistoricalDataAjax"
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

_pair_lock = threading.Lock()
_pair_mem: dict[str, tuple[int, str]] = {}  # symbol -> (pair_id, quote_path)


class InvestingOHLCVError(Exception):
    pass


def _cache_path() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    d = base / "stocks-dashboard"
    d.mkdir(parents=True, exist_ok=True)
    return d / "investing_pair_ids.json"


def _load_disk_pairs() -> dict[str, Any]:
    p = _cache_path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_disk_pair(sym: str, pair_id: int, quote_path: str) -> None:
    data = _load_disk_pairs()
    data[sym.upper()] = {"pair_id": pair_id, "quote_path": quote_path}
    try:
        _cache_path().write_text(json.dumps(data, indent=0), encoding="utf-8")
    except OSError:
        pass


def _cf_interstitial(html: str) -> bool:
    return "Just a moment" in html or "challenges.cloudflare.com" in html or "cf-browser-verification" in html


def _pick_us_equity_quote(quotes: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
    sym_u = symbol.strip().upper()
    us_ex = {"NASDAQ", "NYSE", "NYSE ARCA", "AMEX", "NYSE MKT"}
    best: dict[str, Any] | None = None
    for q in quotes:
        if (q.get("symbol") or "").upper() != sym_u:
            continue
        ex = (q.get("exchange") or "").upper()
        fl = (q.get("flag") or "").upper()
        typ = (q.get("type") or "").lower()
        if ex in us_ex or fl == "USA" or "nasdaq" in typ or "nyse" in typ:
            if best is None:
                best = q
            elif fl == "USA" and (best.get("flag") or "").upper() != "USA":
                best = q
    if best is None and quotes:
        for q in quotes:
            if (q.get("symbol") or "").upper() == sym_u:
                return q
    return best


def resolve_instrument(symbol: str) -> tuple[int, str]:
    """
    Return ``(pair_id, quote_url_path)`` e.g. ``(6408, "/equities/apple-computer-inc")``.
    """
    sym = symbol.strip().upper()
    if not sym:
        raise InvestingOHLCVError("Empty symbol")

    with _pair_lock:
        if sym in _pair_mem:
            return _pair_mem[sym]

    disk = _load_disk_pairs()
    if sym in disk and isinstance(disk[sym], dict):
        pid = int(disk[sym]["pair_id"])
        path = str(disk[sym].get("quote_path") or "")
        if pid and path:
            with _pair_lock:
                _pair_mem[sym] = (pid, path)
            return pid, path

    params = {"q": sym, "size": "25", "offset": "0"}
    headers = {
        "User-Agent": _BROWSER_UA,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.investing.com",
        "Referer": "https://www.investing.com/",
    }
    try:
        r = requests.get(_SEARCH_URL, params=params, headers=headers, timeout=25)
    except requests.RequestException as exc:
        raise InvestingOHLCVError(f"Investing search network error: {exc}") from exc
    if r.status_code >= 400:
        raise InvestingOHLCVError(f"Investing search HTTP {r.status_code}")

    try:
        payload = r.json()
    except json.JSONDecodeError as exc:
        raise InvestingOHLCVError("Investing search returned non-JSON.") from exc

    quotes = payload.get("quotes") or []
    picked = _pick_us_equity_quote(quotes, sym)
    if picked is None:
        raise InvestingOHLCVError(f"No Investing.com quote match for {sym!r} in search results.")

    pair_id = int(picked["id"])
    url_path = str(picked.get("url") or "")
    if not url_path.startswith("/"):
        url_path = "/" + url_path

    with _pair_lock:
        _pair_mem[sym] = (pair_id, url_path)
    _save_disk_pair(sym, pair_id, url_path)
    return pair_id, url_path


def _referer_historical(quote_path: str) -> str:
    base = "https://www.investing.com"
    q = quote_path.rstrip("/")
    if q.endswith("-historical-data"):
        return base + q
    return f"{base}{q}-historical-data"


def _parse_investing_history_html(html: str) -> pd.DataFrame:
    if _cf_interstitial(html):
        raise InvestingOHLCVError(
            "Investing.com returned a Cloudflare challenge instead of price history. "
            "Try again later, another network, or rely on Yahoo (primary source)."
        )
    if "<table" not in html.lower():
        snippet = re.sub(r"\s+", " ", html)[:240]
        raise InvestingOHLCVError(f"Unexpected Investing history response (no table): {snippet!r}")

    try:
        tables = pd.read_html(StringIO(html))
    except Exception as exc:
        raise InvestingOHLCVError(f"Could not parse Investing history HTML: {exc}") from exc
    if not tables:
        raise InvestingOHLCVError("Investing history HTML contained no parseable tables.")

    raw = tables[0].copy()
    raw.columns = [str(c).strip() for c in raw.columns]
    for c in raw.columns:
        cl = c.lower()
        if "date" in cl:
            colmap[c] = "Date"
        elif cl == "open" or cl.startswith("open"):
            colmap[c] = "Open"
        elif "high" in cl:
            colmap[c] = "High"
        elif "low" in cl and "slow" not in cl:
            colmap[c] = "Low"
        elif "close" in cl:
            colmap[c] = "Close"
        elif "vol" in cl:
            colmap[c] = "Volume"
    df = raw.rename(columns=colmap)
    need = {"Date", "Open", "High", "Low", "Close", "Volume"}
    if not need.issubset(set(df.columns)):
        raise InvestingOHLCVError(f"Investing table missing columns after map: {df.columns.tolist()}")

    out = df[list(need)].copy()
    for c in ("Open", "High", "Low", "Close", "Volume"):
        out[c] = pd.to_numeric(
            out[c].astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        )
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce", utc=True)
    out = out.dropna(subset=["Date", "Close"])
    out = out.set_index("Date").sort_index()
    out.index.name = None
    return out


def fetch_daily_history(symbol: str, *, years: int = 5) -> pd.DataFrame:
    """
    Daily OHLCV from Investing.com (unofficial). Index is UTC-aware datetimes ascending.
    """
    if (os.environ.get("INVESTING_ENABLE") or "true").strip().lower() in ("0", "false", "no", "off"):
        raise InvestingOHLCVError("Investing.com OHLCV disabled via INVESTING_ENABLE.")

    pair_id, quote_path = resolve_instrument(symbol)
    end = datetime.now(UTC).date()
    start = end - timedelta(days=int(365.25 * years) + 10)

    st_s = start.strftime("%m/%d/%Y")
    en_s = end.strftime("%m/%d/%Y")
    referer = _referer_historical(quote_path)

    body = urlencode(
        {
            "curr_id": str(pair_id),
            "header": "Date,Open,High,Low,Close,Volume",
            "st_date": st_s,
            "end_date": en_s,
            "interval_sec": "Daily",
            "sort_col": "date",
            "sort_ord": "DESC",
            "action": "HISTORICAL_DATA",
        }
    )
    headers = {
        "User-Agent": _BROWSER_UA,
        "Accept": "text/html, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.investing.com",
        "Referer": referer,
    }
    sess = requests.Session()
    sess.headers.update({"User-Agent": _BROWSER_UA})
    try:
        sess.get("https://www.investing.com/", timeout=20)
        time.sleep(0.15)
        r = sess.post(_HIST_URL, data=body, headers=headers, timeout=45)
    except requests.RequestException as exc:
        raise InvestingOHLCVError(f"Investing history request failed: {exc}") from exc

    if r.status_code >= 400:
        raise InvestingOHLCVError(f"Investing history HTTP {r.status_code}")

    df = _parse_investing_history_html(r.text)
    if df.empty:
        raise InvestingOHLCVError("Investing.com returned an empty OHLCV table.")
    return df
