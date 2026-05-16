# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""
EODHD (eodhd.com) single-provider client for OHLCV and (gated) fundamentals.

This module is the **only** data provider used by the dashboard after the
single-API refactor. It targets the public EODHD REST API:

- OHLCV (EOD):     ``GET https://eodhd.com/api/eod/{SYMBOL}.{EXCHANGE}``
- Fundamentals:    ``GET https://eodhd.com/api/fundamentals/{SYMBOL}.{EXCHANGE}``

Behaviour:

- Symbols may be passed bare (``AAPL``) or with an exchange suffix (``RELIANCE.NSE``,
  ``VOD.LSE``, ``ABB.NSE``). Bare symbols default to ``EODHD_DEFAULT_EXCHANGE`` (``US``).
- OHLCV is normalised to columns ``Open / High / Low / Close / Adjusted_close / Volume``
  with a ``DatetimeIndex`` sorted ascending.
- Fundamentals are only fetched when ``EODHD_FUNDAMENTALS_ENABLED=true`` (the
  add-on costs more than the All-World OHLCV plan). Otherwise a clear error is
  raised and callers fall back to free SEC EDGAR for US tickers.
"""

from __future__ import annotations

import json
import os
from typing import Any

import pandas as pd
import requests

_BASE_URL = "https://eodhd.com/api"
_TIMEOUT_SEC = 45
_OHLCV_COLUMNS = ("Open", "High", "Low", "Close", "Adjusted_close", "Volume")


class EODHDError(Exception):
    """Raised for any EODHD client failure (network, auth, parse, empty)."""


class EODHDNotFoundError(EODHDError):
    """Raised when the symbol/exchange is unknown or not on the current subscription."""


class EODHDFundamentalsDisabled(EODHDError):
    """Raised when fundamentals are skipped via ``EODHD_FUNDAMENTALS_ENABLED=false``."""


class EODHDFundamentalsPlanError(EODHDError):
    """Raised when the API key is valid but the subscription does not include fundamentals."""


def _api_token() -> str:
    token = (os.environ.get("EODHD_API_KEY") or "").strip()
    if not token:
        raise EODHDError(
            "EODHD_API_KEY is not set. Add it to .env or your environment to use the EODHD client."
        )
    return token


def _default_exchange() -> str:
    return (os.environ.get("EODHD_DEFAULT_EXCHANGE") or "US").strip().upper() or "US"


def _fundamentals_force_skip() -> bool:
    """When ``EODHD_FUNDAMENTALS_ENABLED=false``, skip EODHD fundamentals (EDGAR-only mode)."""
    raw = (os.environ.get("EODHD_FUNDAMENTALS_ENABLED") or "").strip().lower()
    return raw in ("0", "false", "no", "off")


def should_attempt_eodhd_fundamentals() -> bool:
    """Attempt EODHD fundamentals when an API key is set and not force-skipped."""
    if not (os.environ.get("EODHD_API_KEY") or "").strip():
        return False
    return not _fundamentals_force_skip()


def _fundamentals_enabled() -> bool:
    """Alias: fundamentals API allowed (inverse of force-skip). Used by valuation helpers."""
    return should_attempt_eodhd_fundamentals()


# User-facing exchange suffixes -> EODHD API codes (search / eod endpoints).
_EXCHANGE_ALIASES: dict[str, str] = {
    "NS": "NSE",
    "NSE": "NSE",
    "BO": "BSE",
    "BSE": "BSE",
    "BOM": "BSE",
}


def normalize_symbol(symbol: str) -> str:
    """
    Return ``SYMBOL.EXCHANGE`` upper-cased. Adds the default exchange when missing.

    Examples:
        >>> normalize_symbol("aapl")
        'AAPL.US'
        >>> normalize_symbol("Reliance.NSE")
        'RELIANCE.NSE'
    """
    sym = (symbol or "").strip().upper()
    if not sym:
        raise EODHDError("Empty symbol")
    if "." in sym:
        base, exch = sym.rsplit(".", 1)
        exch = _EXCHANGE_ALIASES.get(exch, exch)
        return f"{base}.{exch}"
    return f"{sym}.{_default_exchange()}"


def yahoo_symbol_from_eodhd(symbol: str) -> str:
    """
    Map ``SYMBOL.NSE`` style tickers to Yahoo Finance suffixes (e.g. ``SYMBOL.NS``).
    """
    sym = normalize_symbol(symbol)
    if "." not in sym:
        return sym
    base, exch = sym.rsplit(".", 1)
    yahoo_exch = {"NSE": "NS", "BSE": "BO"}.get(exch, exch)
    return f"{base}.{yahoo_exch}"


def _search_resolved_symbol(symbol: str) -> str | None:
    """Use EODHD search API to resolve ``Code`` + ``Exchange`` for ambiguous tickers."""
    bare = (symbol or "").strip().upper()
    query = bare.split(".", 1)[0] if bare else ""
    if not query:
        return None
    try:
        hits = _get_json(f"search/{query}", {"limit": 15})
    except EODHDError:
        return None
    if not isinstance(hits, list):
        return None
    want_exch = None
    if "." in bare:
        _, suffix = bare.rsplit(".", 1)
        want_exch = _EXCHANGE_ALIASES.get(suffix, suffix)
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        code = (hit.get("Code") or "").strip().upper()
        exch = (hit.get("Exchange") or "").strip().upper()
        if not code or not exch:
            continue
        if want_exch and exch != want_exch:
            continue
        if code == query or (not want_exch and hit.get("isPrimary")):
            return f"{code}.{exch}"
    return None


def _get_json(path: str, params: dict[str, Any]) -> Any:
    url = f"{_BASE_URL}/{path}"
    full_params = {"api_token": _api_token(), "fmt": "json", **params}
    try:
        resp = requests.get(url, params=full_params, timeout=_TIMEOUT_SEC)
    except requests.RequestException as exc:
        raise EODHDError(f"Network error calling EODHD {path}: {exc}") from exc

    if resp.status_code in (401, 402, 403) and path.startswith("fundamentals/"):
        raise EODHDFundamentalsPlanError(
            f"EODHD fundamentals not available on your plan (HTTP {resp.status_code}). "
            "Subscribe to the Fundamentals Data Feed: https://eodhd.com/pricing — "
            "docs: https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds"
        )
    if resp.status_code == 401 or resp.status_code == 403:
        raise EODHDError(
            f"EODHD authentication failed (HTTP {resp.status_code}). "
            "Check EODHD_API_KEY and that your plan covers this endpoint."
        )
    if resp.status_code == 404:
        raise EODHDNotFoundError(
            f"EODHD 404 for {path} params={params}: symbol/exchange not found. "
            "Confirm the ticker on eodhd.com; Indian and other markets require the "
            "All-World plan (free trial keys are often US-only)."
        )
    if resp.status_code == 429:
        raise EODHDError("EODHD rate-limited (HTTP 429). Slow down or upgrade your plan.")
    if resp.status_code >= 400:
        raise EODHDError(f"EODHD HTTP {resp.status_code} for {path}: {resp.text[:200]!r}")

    try:
        return resp.json()
    except json.JSONDecodeError as exc:
        raise EODHDError(
            f"Invalid JSON from EODHD {path} (body starts: {resp.text[:120]!r})."
        ) from exc


def fetch_ohlcv(symbol: str, *, period: str = "d") -> pd.DataFrame:
    """
    Daily OHLCV for one ``SYMBOL.EXCHANGE``.

    Returns a DataFrame indexed by date with columns
    ``Open / High / Low / Close / Adjusted_close / Volume``.
    """
    sym = normalize_symbol(symbol)
    try:
        payload = _get_json(f"eod/{sym}", {"period": period, "order": "a"})
    except EODHDNotFoundError:
        resolved = _search_resolved_symbol(symbol)
        if resolved and resolved != sym:
            sym = resolved
            payload = _get_json(f"eod/{sym}", {"period": period, "order": "a"})
        else:
            raise
    if not isinstance(payload, list) or not payload:
        raise EODHDError(f"Empty OHLCV response for {sym}.")

    df = pd.DataFrame(payload)
    if "date" not in df.columns:
        raise EODHDError(f"EODHD OHLCV response for {sym} missing 'date' column: {df.columns.tolist()!r}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date").sort_index()

    rename_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "adjusted_close": "Adjusted_close",
        "volume": "Volume",
    }
    df = df.rename(columns=rename_map)

    missing = [c for c in _OHLCV_COLUMNS if c not in df.columns]
    if missing:
        raise EODHDError(f"EODHD OHLCV for {sym} missing columns {missing}; got {df.columns.tolist()!r}")

    for col in _OHLCV_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Close"])
    if df.empty:
        raise EODHDError(f"EODHD OHLCV for {sym} parsed to empty frame after cleanup.")
    return df[list(_OHLCV_COLUMNS)]


def _flatten_fundamentals(payload: dict[str, Any], sym: str) -> pd.DataFrame:
    """
    Best-effort flattening of EODHD's nested ``General`` / ``Highlights`` /
    ``Valuation`` / ``SharesStats`` blocks into a two-column metric/value table.

    Statement grids (income, balance sheet, cash flow) are intentionally **not**
    flattened here; consumers wanting time-series statements should query the
    nested keys directly.
    """
    if not isinstance(payload, dict) or not payload:
        raise EODHDError(f"EODHD fundamentals payload for {sym} was empty or invalid.")

    rows: list[tuple[str, Any]] = []
    for section in ("General", "Highlights", "Valuation", "SharesStats", "Technicals"):
        block = payload.get(section)
        if not isinstance(block, dict):
            continue
        for key, value in block.items():
            if isinstance(value, (dict, list)):
                continue
            rows.append((f"{section}.{key}", value))

    if not rows:
        raise EODHDError(
            f"EODHD fundamentals for {sym} had no scalar metrics in expected sections."
        )
    df = pd.DataFrame(rows, columns=["metric", "value"])
    return df


def fetch_fundamentals_payload(symbol: str) -> dict[str, Any]:
    """Raw fundamentals JSON (requires API key; plan must include fundamentals)."""
    if _fundamentals_force_skip():
        raise EODHDFundamentalsDisabled(
            "EODHD fundamentals skipped (EODHD_FUNDAMENTALS_ENABLED=false). "
            "Remove or set true to attempt the fundamentals API."
        )
    sym = normalize_symbol(symbol)
    payload = _get_json(f"fundamentals/{sym}", {})
    if not isinstance(payload, dict) or not payload:
        raise EODHDError(f"EODHD fundamentals payload for {sym} was empty or invalid.")
    return payload


def valuation_snapshot(symbol: str) -> dict[str, float | None]:
    """
    Scalar valuation ratios from EODHD ``Highlights`` / ``Valuation`` blocks.

    Returns keys such as ``trailing_pe``, ``forward_pe``, ``roe_ttm`` (may be used
    as a ROIC proxy when ROIC is not published). Empty dict when fundamentals are
    disabled or the request fails.
    """
    try:
        payload = fetch_fundamentals_payload(symbol)
    except (EODHDError, EODHDFundamentalsDisabled):
        return {}

    highlights = payload.get("Highlights") if isinstance(payload.get("Highlights"), dict) else {}
    valuation = payload.get("Valuation") if isinstance(payload.get("Valuation"), dict) else {}

    def _num(block: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            raw = block.get(key)
            if raw is None:
                continue
            try:
                val = float(raw)
            except (TypeError, ValueError):
                continue
            if pd.notna(val):
                return val
        return None

    trailing_pe = _num(
        highlights,
        "PERatio",
        "TrailingPE",
        "PeRatio",
    ) or _num(valuation, "TrailingPE", "PERatio")
    forward_pe = _num(highlights, "ForwardPE", "ForwardPEGRatio") or _num(valuation, "ForwardPE")
    roe = _num(highlights, "ReturnOnEquityTTM", "ReturnOnEquity")
    roic = _num(
        highlights,
        "ReturnOnInvestedCapital",
        "ReturnOnInvestedCapitalTTM",
    ) or _num(valuation, "ReturnOnInvestedCapital")

    out: dict[str, float | None] = {
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
        "roe_ttm": roe,
        "roic": roic,
    }
    return {k: v for k, v in out.items() if v is not None}


def fetch_fundamentals(symbol: str) -> pd.DataFrame:
    """
    Two-column ``metric / value`` snapshot from EODHD fundamentals.

    Raises :class:`EODHDFundamentalsDisabled` when the add-on is not enabled via
    ``EODHD_FUNDAMENTALS_ENABLED=true``. This keeps the default cost at the
    All-World OHLCV plan (~$18/mo).
    """
    if _fundamentals_force_skip():
        raise EODHDFundamentalsDisabled(
            "EODHD fundamentals skipped (EODHD_FUNDAMENTALS_ENABLED=false)."
        )
    sym = normalize_symbol(symbol)
    payload = fetch_fundamentals_payload(symbol)
    return _flatten_fundamentals(payload, sym)
