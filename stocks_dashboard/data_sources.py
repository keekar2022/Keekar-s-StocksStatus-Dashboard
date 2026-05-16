# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""
OHLCV router: Yahoo-first (default), EODHD-first, or legacy multi-source chain.

Indicators (MACD, RSI, etc.) are computed locally from OHLCV via ``ta`` — not
fetched from EODHD. SEC EDGAR remains a free US-only fundamentals enhancer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import pandas as pd

from stocks_dashboard.edgar import EdgarError, fetch_company_facts, resolve_cik
from stocks_dashboard.eodhd_client import (
    EODHDError,
    EODHDFundamentalsDisabled,
    EODHDFundamentalsPlanError,
    fetch_fundamentals_payload,
    fetch_ohlcv as eodhd_fetch_ohlcv,
    normalize_symbol as eodhd_normalize_symbol,
    should_attempt_eodhd_fundamentals,
    yahoo_symbol_from_eodhd,
)
from stocks_dashboard.eodhd_fundamentals import fundamentals_table_from_eodhd
from stocks_dashboard.fundamentals import fundamentals_from_companyfacts
from stocks_dashboard.yahoo_ohlcv import YahooOHLCVError


def _legacy_enabled() -> bool:
    raw = (os.environ.get("LEGACY_SOURCES") or "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _ohlcv_primary_mode() -> str:
    """``yahoo`` (default) or ``eodhd`` — ignored when ``LEGACY_SOURCES=true``."""
    raw = (os.environ.get("OHLCV_PRIMARY") or "yahoo").strip().lower()
    return raw if raw in ("yahoo", "eodhd") else "yahoo"


def _ohlcv_cross_fallback_enabled() -> bool:
    """When the primary OHLCV provider fails, try the other (Yahoo ↔ EODHD)."""
    raw = (os.environ.get("EODHD_OHLCV_FALLBACK") or "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _has_eodhd_key() -> bool:
    return bool((os.environ.get("EODHD_API_KEY") or "").strip())


def _align_ohlcv_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Match EODHD column names for shared technical-indicator code."""
    out = df.copy()
    if "Adjusted_close" not in out.columns and "Close" in out.columns:
        out["Adjusted_close"] = out["Close"]
    cols = ("Open", "High", "Low", "Close", "Adjusted_close", "Volume")
    missing = [c for c in cols if c not in out.columns]
    if missing:
        raise YahooOHLCVError(f"OHLCV frame missing columns {missing}")
    return out[list(cols)]


@dataclass(frozen=True)
class ResolvedOHLCV:
    """Daily OHLCV with provenance for UI captions."""

    df: pd.DataFrame
    primary_source: str
    tried: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FundamentalAutoResult:
    df: pd.DataFrame | None
    primary_source: str
    log: tuple[tuple[str, str], ...]


def _ohlcv_eodhd_only(symbol: str) -> ResolvedOHLCV:
    sym = eodhd_normalize_symbol(symbol)
    tried: list[str] = []
    try:
        df = eodhd_fetch_ohlcv(symbol)
        return ResolvedOHLCV(df, f"EODHD ({sym})", ("eodhd",))
    except EODHDError as exc:
        tried.append(f"eodhd ({sym}): {exc}")

    if not _ohlcv_cross_fallback_enabled():
        raise YahooOHLCVError(
            f"EODHD OHLCV failed for {symbol}: {tried[0]}"
        ) from None

    from stocks_dashboard.yahoo_ohlcv import fetch_daily_history as yahoo_fetch_daily

    ysym = yahoo_symbol_from_eodhd(symbol)
    try:
        ydf = _align_ohlcv_columns(yahoo_fetch_daily(ysym))
    except YahooOHLCVError as exc:
        tried.append(f"yahoo ({ysym}): {exc}")
        raise YahooOHLCVError(
            f"OHLCV unavailable for {symbol.strip().upper()}. "
            + " | ".join(tried)
            + " Tip: NSE/BSE tickers need an EODHD All-World subscription; "
            "free API keys are often US-only."
        ) from exc

    return ResolvedOHLCV(
        ydf,
        f"Yahoo Finance fallback ({ysym}) — EODHD had no data for {sym}",
        tuple(tried) + ("yahoo",),
    )


def _ohlcv_yahoo_first(symbol: str) -> ResolvedOHLCV:
    """Yahoo chart API first; EODHD when Yahoo fails and a key is configured."""
    from stocks_dashboard.yahoo_ohlcv import fetch_daily_history as yahoo_fetch_daily

    sym = eodhd_normalize_symbol(symbol)
    ysym = yahoo_symbol_from_eodhd(symbol)
    tried: list[str] = []
    try:
        ydf = _align_ohlcv_columns(yahoo_fetch_daily(ysym))
        return ResolvedOHLCV(ydf, f"Yahoo Finance ({ysym})", ("yahoo",))
    except YahooOHLCVError as exc:
        tried.append(f"yahoo ({ysym}): {exc}")

    if not _ohlcv_cross_fallback_enabled() or not _has_eodhd_key():
        hint = (
            " Set EODHD_API_KEY for EODHD fallback, or check the Yahoo symbol mapping."
            if not _has_eodhd_key()
            else ""
        )
        raise YahooOHLCVError(
            f"OHLCV unavailable for {symbol.strip().upper()}. " + " | ".join(tried) + hint
        ) from None

    try:
        df = eodhd_fetch_ohlcv(symbol)
        return ResolvedOHLCV(
            df,
            f"EODHD fallback ({sym}) — Yahoo had no data for {ysym}",
            tuple(tried) + ("eodhd",),
        )
    except EODHDError as exc:
        tried.append(f"eodhd ({sym}): {exc}")
        raise YahooOHLCVError(
            f"OHLCV unavailable for {symbol.strip().upper()}. " + " | ".join(tried)
        ) from exc


def _ohlcv_legacy_chain(symbol: str) -> ResolvedOHLCV:
    """Original multi-source chain. Imported lazily to avoid hard deps when unused."""
    from stocks_dashboard.alphavantage import AlphaVantageError, fetch_time_series_daily
    from stocks_dashboard.investing_ohlcv import InvestingOHLCVError, fetch_daily_history as investing_fetch_daily
    from stocks_dashboard.yahoo_ohlcv import fetch_daily_history as yahoo_fetch_daily

    tried: list[str] = []
    try:
        df = yahoo_fetch_daily(symbol)
        return ResolvedOHLCV(df, "Yahoo Finance (chart JSON / yfinance)", ("yahoo",))
    except YahooOHLCVError as exc:
        tried.append(f"yahoo: {exc}")

    if (os.environ.get("ALPHA_VANTAGE_API_KEY") or "").strip():
        try:
            df = fetch_time_series_daily(symbol)
            return ResolvedOHLCV(
                df,
                "Alpha Vantage (TIME_SERIES_DAILY)",
                tuple(tried) + ("alphavantage",),
            )
        except AlphaVantageError as exc:
            tried.append(f"alphavantage: {exc}")
    else:
        tried.append("alphavantage: skipped (no ALPHA_VANTAGE_API_KEY)")

    if (os.environ.get("INVESTING_ENABLE") or "true").strip().lower() not in ("0", "false", "no", "off"):
        try:
            df = investing_fetch_daily(symbol)
            return ResolvedOHLCV(
                df,
                "Investing.com (unofficial HistoricalDataAjax)",
                tuple(tried) + ("investing",),
            )
        except InvestingOHLCVError as exc:
            tried.append(f"investing: {exc}")
    else:
        tried.append("investing: skipped (INVESTING_ENABLE=false)")

    raise YahooOHLCVError(
        f"All legacy OHLCV sources failed for {symbol.strip().upper()}: " + " | ".join(tried)
    )


def fetch_ohlcv_preferred(symbol: str) -> ResolvedOHLCV:
    """
    OHLCV routing (``LEGACY_SOURCES`` overrides everything):

    - ``OHLCV_PRIMARY=yahoo`` (default): Yahoo → EODHD (if key + fallback enabled)
    - ``OHLCV_PRIMARY=eodhd``: EODHD → Yahoo (if ``EODHD_OHLCV_FALLBACK`` enabled)
    - ``LEGACY_SOURCES=true``: Yahoo → Alpha Vantage → Investing
    """
    if _legacy_enabled():
        return _ohlcv_legacy_chain(symbol)
    if _ohlcv_primary_mode() == "yahoo":
        return _ohlcv_yahoo_first(symbol)
    return _ohlcv_eodhd_only(symbol)


def _looks_like_us_ticker(symbol: str) -> bool:
    """EDGAR only covers US listings. Treat bare or ``.US`` suffixes as US."""
    sym = (symbol or "").strip().upper()
    if not sym:
        return False
    if "." not in sym:
        return True
    return sym.endswith(".US")


def _bare_symbol(symbol: str) -> str:
    sym = (symbol or "").strip().upper()
    return sym.split(".", 1)[0] if "." in sym else sym


def _try_edgar_fundamentals(
    sym: str, *, cmap: dict[str, int] | None, log: list[tuple[str, str]]
) -> pd.DataFrame | None:
    ua = (os.environ.get("SEC_USER_AGENT") or "").strip()
    if not ua:
        log.append(("SEC EDGAR", "skipped (no SEC_USER_AGENT)"))
        return None
    if cmap is None:
        log.append(("SEC EDGAR", "skipped (no CIK map)"))
        return None
    if not _looks_like_us_ticker(sym):
        log.append(("SEC EDGAR", "skipped (non-US listing — EDGAR is US-only)"))
        return None
    bare = _bare_symbol(sym)
    try:
        cik = resolve_cik(bare, cmap)
        facts = fetch_company_facts(cik)
        df = fundamentals_from_companyfacts(facts)
        if df is not None and not df.empty:
            log.append(("SEC EDGAR", "ok (fallback)"))
            return df
        log.append(("SEC EDGAR", "empty table from company facts"))
    except EdgarError as exc:
        log.append(("SEC EDGAR", str(exc)))
    return None


def load_fundamentals_auto(symbol: str, *, cmap: dict[str, int] | None) -> FundamentalAutoResult:
    """
    Fundamentals: **EODHD first** (when ``EODHD_API_KEY`` is set), then **SEC EDGAR** (US fallback).

    Set ``EODHD_FUNDAMENTALS_ENABLED=false`` to skip the EODHD attempt and use EDGAR only.
    When ``LEGACY_SOURCES=true``, uses the original Yahoo / Alpha Vantage chain.
    """
    sym = (symbol or "").strip().upper()
    log: list[tuple[str, str]] = []

    if _legacy_enabled():
        return _fundamentals_legacy(sym, cmap=cmap)

    if should_attempt_eodhd_fundamentals():
        try:
            payload = fetch_fundamentals_payload(sym)
            df = fundamentals_table_from_eodhd(payload)
            if df is not None and not df.empty:
                log.append(("EODHD fundamentals", "ok"))
                return FundamentalAutoResult(
                    df,
                    f"EODHD fundamentals ({eodhd_normalize_symbol(sym)})",
                    tuple(log),
                )
            log.append(("EODHD fundamentals", "empty table after parse"))
        except EODHDFundamentalsDisabled as exc:
            log.append(("EODHD fundamentals", str(exc)))
        except EODHDFundamentalsPlanError as exc:
            log.append(("EODHD fundamentals", str(exc)))
        except EODHDError as exc:
            log.append(("EODHD fundamentals", str(exc)))
    else:
        if not (os.environ.get("EODHD_API_KEY") or "").strip():
            log.append(("EODHD fundamentals", "skipped (no EODHD_API_KEY)"))
        else:
            log.append(("EODHD fundamentals", "skipped (EODHD_FUNDAMENTALS_ENABLED=false)"))

    df_edgar = _try_edgar_fundamentals(sym, cmap=cmap, log=log)
    if df_edgar is not None:
        return FundamentalAutoResult(df_edgar, "SEC EDGAR (company facts)", tuple(log))

    return FundamentalAutoResult(None, "none", tuple(log))


def _fundamentals_legacy(symbol: str, *, cmap: dict[str, int] | None) -> FundamentalAutoResult:
    """Original EDGAR -> Yahoo -> Alpha Vantage OVERVIEW chain (only when LEGACY_SOURCES=true)."""
    from stocks_dashboard.alphavantage import AlphaVantageError, fetch_company_overview
    from stocks_dashboard.yahoo_fundamentals import (
        YahooFinanceError,
        fundamentals_table as yahoo_fundamentals_table,
    )

    log: list[tuple[str, str]] = []
    sym = symbol.strip().upper()
    ua = (os.environ.get("SEC_USER_AGENT") or "").strip()
    if ua and cmap is not None:
        try:
            cik = resolve_cik(_bare_symbol(sym), cmap)
            facts = fetch_company_facts(cik)
            df = fundamentals_from_companyfacts(facts)
            if df is not None and not df.empty:
                log.append(("SEC EDGAR", "ok"))
                return FundamentalAutoResult(df, "SEC EDGAR (company facts)", tuple(log))
            log.append(("SEC EDGAR", "empty table from company facts"))
        except EdgarError as exc:
            log.append(("SEC EDGAR", str(exc)))
    else:
        log.append(("SEC EDGAR", "skipped (no SEC_USER_AGENT or no CIK map)"))

    try:
        df, warns = yahoo_fundamentals_table(_bare_symbol(sym))
        for w in warns:
            log.append(("Yahoo Finance", w))
        log.append(("Yahoo Finance", "ok"))
        return FundamentalAutoResult(df, "Yahoo Finance (yfinance)", tuple(log))
    except YahooFinanceError as exc:
        log.append(("Yahoo Finance", str(exc)))

    if (os.environ.get("ALPHA_VANTAGE_API_KEY") or "").strip():
        try:
            odf = fetch_company_overview(_bare_symbol(sym))
            log.append(("Alpha Vantage", "ok (OVERVIEW)"))
            return FundamentalAutoResult(odf, "Alpha Vantage (OVERVIEW)", tuple(log))
        except AlphaVantageError as exc:
            log.append(("Alpha Vantage", str(exc)))
    else:
        log.append(("Alpha Vantage", "skipped (no ALPHA_VANTAGE_API_KEY)"))

    return FundamentalAutoResult(None, "none", tuple(log))
