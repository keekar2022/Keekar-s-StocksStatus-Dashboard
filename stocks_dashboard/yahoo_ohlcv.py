# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""Fetch and slice Yahoo Finance daily OHLCV for technical analysis."""

from __future__ import annotations

import json
from typing import Literal

import pandas as pd
import requests

Horizon = Literal["1W", "1M", "6M", "1Y", "5Y"]

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


class YahooOHLCVError(Exception):
    pass


def _ohlcv_from_yahoo_chart_json(payload: dict, symbol: str) -> pd.DataFrame:
    chart = payload.get("chart") or {}
    err = chart.get("error")
    if err:
        desc = err.get("description", str(err))
        raise YahooOHLCVError(f"Yahoo chart API error for {symbol}: {desc}")
    results = chart.get("result") or []
    if not results:
        raise YahooOHLCVError(f"Empty Yahoo chart result for {symbol}.")
    r0 = results[0]
    ts = r0.get("timestamp") or []
    quotes = (r0.get("indicators") or {}).get("quote") or []
    if not ts or not quotes:
        raise YahooOHLCVError(f"No timestamps or quotes in Yahoo response for {symbol}.")
    q = quotes[0]
    meta = r0.get("meta") or {}
    tz_name = meta.get("exchangeTimezoneName") or "UTC"
    idx_utc = pd.to_datetime(ts, unit="s", utc=True)
    try:
        idx = idx_utc.tz_convert(tz_name)
    except Exception:
        idx = idx_utc
    df = pd.DataFrame(
        {
            "Open": q.get("open"),
            "High": q.get("high"),
            "Low": q.get("low"),
            "Close": q.get("close"),
            "Volume": q.get("volume"),
        },
        index=idx,
    )
    df = df[~df["Close"].isna()]
    df = df.dropna(how="all")
    return df


def _fetch_daily_history_requests(symbol: str, *, period: str) -> pd.DataFrame:
    """
    Yahoo v8 chart JSON via **pip requests** (not curl_cffi).

    Recent ``yfinance`` builds use ``curl_cffi`` for cookies; on some setups the
    bootstrap GET to ``fc.yahoo.com`` fails before ``history()`` can run. The chart
    endpoint usually works with a normal browser User-Agent and no crumb.
    """
    sym = symbol.strip().upper()
    bases = (
        "https://query1.finance.yahoo.com",
        "https://query2.finance.yahoo.com",
    )
    last_status: tuple[int, str] | None = None
    headers = {
        "User-Agent": _BROWSER_UA,
        "Accept": "application/json,text/plain,*/*",
    }
    resp = None
    for base in bases:
        url = f"{base}/v8/finance/chart/{sym}"
        try:
            resp = requests.get(
                url,
                params={"range": period, "interval": "1d"},
                headers=headers,
                timeout=45,
            )
        except requests.RequestException as exc:
            raise YahooOHLCVError(f"Network error fetching Yahoo chart for {sym}: {exc}") from exc

        if resp.status_code == 429:
            last_status = (429, resp.text[:200])
            continue
        if resp.status_code >= 400:
            last_status = (resp.status_code, resp.text[:200])
            continue
        break
    else:
        if last_status and last_status[0] == 429:
            raise YahooOHLCVError(
                f"Yahoo rate-limited chart requests for {sym} (HTTP 429 on all endpoints). "
                "Wait and retry, or try another network."
            )
        if last_status:
            raise YahooOHLCVError(
                f"Yahoo chart HTTP {last_status[0]} for {sym}: {last_status[1]!r}"
            )
        raise YahooOHLCVError(f"No response from Yahoo chart endpoints for {sym}.")

    assert resp is not None

    try:
        payload = resp.json()
    except json.JSONDecodeError as exc:
        raise YahooOHLCVError(
            f"Invalid JSON from Yahoo chart for {sym} (body starts: {resp.text[:120]!r})."
        ) from exc

    return _ohlcv_from_yahoo_chart_json(payload, sym)


def _fetch_daily_history_yfinance(symbol: str, *, period: str) -> pd.DataFrame:
    """Fallback: ``yfinance.Ticker.history`` (same columns as requests path)."""
    import yfinance as yf

    sym = symbol.strip().upper()
    t = yf.Ticker(sym)
    df = t.history(period=period, interval="1d", auto_adjust=False)
    if df is None or df.empty:
        raise YahooOHLCVError(f"No OHLCV history returned for {sym} (rate limit, delisted, or network).")
    return df


def fetch_daily_history(symbol: str, *, period: str = "5y") -> pd.DataFrame:
    """
    Daily OHLCV (Open/High/Low/Close/Volume), ``auto_adjust=False`` semantics.

    Primary path: Yahoo **v8/chart** JSON via **requests** (avoids yfinance/curl_cffi
    cookie bootstrap failures). On failure, falls back to ``yfinance.Ticker.history``.
    """
    sym = symbol.strip().upper()
    if not sym:
        raise YahooOHLCVError("Empty symbol")

    primary_err: Exception | None = None
    try:
        df = _fetch_daily_history_requests(sym, period=period)
    except Exception as exc:
        primary_err = exc
        try:
            df = _fetch_daily_history_yfinance(sym, period=period)
        except Exception:
            raise YahooOHLCVError(
                f"Could not load OHLCV for {sym}. Chart (requests) failed: {primary_err!s} "
                "If you see curl_cffi or fc.yahoo.com errors, prefer a stable network or VPN. "
                "yfinance fallback also failed."
            ) from primary_err

    need = {"Open", "High", "Low", "Close", "Volume"}
    missing = need - set(df.columns)
    if missing:
        raise YahooOHLCVError(f"Missing columns {missing} for {sym}")
    return df


def slice_trading_window(df: pd.DataFrame, horizon: Horizon) -> pd.DataFrame:
    """Last N **trading rows** for stable POC windows."""
    if df.empty:
        return df
    if horizon == "1W":
        return df.tail(5)
    if horizon == "1M":
        return df.tail(21)
    if horizon == "6M":
        return df.tail(126)
    if horizon == "1Y":
        return df.tail(252)
    if horizon == "5Y":
        return df
    raise YahooOHLCVError(f"Unknown horizon: {horizon!r}")
