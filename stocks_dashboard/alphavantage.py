# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""
Alpha Vantage market data (official API key from https://www.alphavantage.co/support/#api-key).

Free-tier limits are strict (calls per minute / per day); this module throttles consecutive requests.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import pandas as pd
import requests

_AV_BASE = "https://www.alphavantage.co/query"

_lock = threading.Lock()
_last_request_mono: float = 0.0


class AlphaVantageError(Exception):
    pass


def _api_key() -> str:
    return (os.environ.get("ALPHA_VANTAGE_API_KEY") or "").strip()


def _throttle() -> None:
    """Space out calls to respect Alpha Vantage free-tier velocity limits."""
    interval = float((os.environ.get("ALPHA_VANTAGE_CALL_INTERVAL_SEC") or "12.5").strip() or "12.5")
    interval = max(0.5, min(60.0, interval))
    global _last_request_mono
    with _lock:
        now = time.monotonic()
        wait = interval - (now - _last_request_mono)
        if wait > 0:
            time.sleep(wait)
        _last_request_mono = time.monotonic()


def _get_json(params: dict[str, str]) -> dict[str, Any]:
    key = _api_key()
    if not key:
        raise AlphaVantageError("Missing ALPHA_VANTAGE_API_KEY in environment (.env or secrets).")
    _throttle()
    q = {**params, "apikey": key}
    try:
        r = requests.get(_AV_BASE, params=q, timeout=90)
    except requests.RequestException as exc:
        raise AlphaVantageError(f"Network error: {exc}") from exc
    if r.status_code >= 400:
        raise AlphaVantageError(f"HTTP {r.status_code} from Alpha Vantage.")
    try:
        data = r.json()
    except ValueError as exc:
        raise AlphaVantageError("Alpha Vantage returned non-JSON.") from exc
    if not isinstance(data, dict):
        raise AlphaVantageError("Unexpected Alpha Vantage response shape.")

    note = data.get("Note") or data.get("Information")
    if note:
        raise AlphaVantageError(f"Alpha Vantage rate or usage notice: {note}")
    err = data.get("Error Message")
    if err:
        raise AlphaVantageError(str(err))
    return data


def fetch_time_series_daily(symbol: str) -> pd.DataFrame:
    """
    Daily OHLCV via ``TIME_SERIES_DAILY`` (unadjusted close), ``outputsize=full``, then sorted ascending.

    Columns: ``Open``, ``High``, ``Low``, ``Close``, ``Volume`` — index timezone-aware UTC at midnight.
    """
    sym = symbol.strip().upper()
    if not sym:
        raise AlphaVantageError("Empty symbol.")

    data = _get_json(
        {
            "function": "TIME_SERIES_DAILY",
            "symbol": sym,
            "outputsize": "full",
            "datatype": "json",
        }
    )
    series = data.get("Time Series (Daily)")
    if not isinstance(series, dict) or not series:
        raise AlphaVantageError("No Time Series (Daily) in Alpha Vantage response (check symbol entitlement).")

    rows: list[dict[str, Any]] = []
    for date_str, bar in series.items():
        if not isinstance(bar, dict):
            continue
        try:
            rows.append(
                {
                    "Date": date_str,
                    "Open": bar.get("1. open"),
                    "High": bar.get("2. high"),
                    "Low": bar.get("3. low"),
                    "Close": bar.get("4. close"),
                    "Volume": bar.get("5. volume"),
                }
            )
        except (TypeError, ValueError):
            continue
    if not rows:
        raise AlphaVantageError("Could not parse any daily bars from Alpha Vantage.")

    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    for c in ("Open", "High", "Low", "Close", "Volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["Date", "Close"])
    df = df.set_index("Date").sort_index()
    return df


def fetch_company_overview(symbol: str) -> pd.DataFrame:
    """
    Flat company profile / key metrics as a two-column table (``metric``, ``value``).
    """
    sym = symbol.strip().upper()
    if not sym:
        raise AlphaVantageError("Empty symbol.")

    data = _get_json({"function": "OVERVIEW", "symbol": sym})
    if not data:
        raise AlphaVantageError("Empty OVERVIEW response from Alpha Vantage.")

    # Drop trivial meta if present
    skip = {"Information", "Note", "Error Message"}
    items = [(k, v) for k, v in data.items() if k not in skip and v is not None and str(v).strip() != ""]
    if not items:
        raise AlphaVantageError("OVERVIEW contained no usable fields.")

    return pd.DataFrame(items, columns=["metric", "value"])
