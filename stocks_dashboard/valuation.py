# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""
Optional valuation metrics (PE / ROIC) for the Technical tab.

Annual ROIC (US): **SEC EDGAR** company facts first (free), then optional **Yahoo**,
then **EODHD** yearly financials. Latest ROIC scalar from EODHD Highlights or Yahoo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import pandas as pd

from stocks_dashboard.eodhd_client import (
    EODHDError,
    EODHDFundamentalsDisabled,
    EODHDFundamentalsPlanError,
    fetch_fundamentals_payload,
    should_attempt_eodhd_fundamentals,
    valuation_snapshot,
)
from stocks_dashboard.technical_indicators import (
    attach_pe_proxy,
    roic_annual_table,
    roic_latest_from_info,
    yahoo_pe_roic_enabled,
)


@dataclass(frozen=True)
class ValuationContext:
    """PE / ROIC data loaded once per symbol for all horizon tabs."""

    roic_latest: float | None
    roic_annual: pd.DataFrame
    eodhd_trailing_pe: float | None
    source_note: str | None
    yahoo_warning: str | None
    roic_annual_source: str | None = None
    roic_annual_attempts: tuple[str, ...] = field(default_factory=tuple)


def _yahoo_warning(exc: BaseException) -> str:
    return (
        "Yahoo (`yfinance`) valuation data is unavailable on this network "
        f"({type(exc).__name__}: {exc}). "
        "US annual ROIC can still load from **SEC EDGAR** when `SEC_USER_AGENT` is set."
    )


def _load_edgar_roic_annual(bare_symbol: str, cik_map: dict[str, int] | None) -> tuple[pd.DataFrame, str]:
    from stocks_dashboard.roic import roic_annual_from_edgar

    ua = (os.environ.get("SEC_USER_AGENT") or "").strip()
    if not ua:
        return pd.DataFrame(), "SEC EDGAR: skipped (no SEC_USER_AGENT)"
    if cik_map is None:
        return pd.DataFrame(), "SEC EDGAR: skipped (no CIK map)"
    from stocks_dashboard.edgar import EdgarError, fetch_company_facts, resolve_cik

    bare = bare_symbol.strip().upper()
    try:
        cik = resolve_cik(bare, cik_map)
        facts = fetch_company_facts(cik)
        df = roic_annual_from_edgar(facts)
        if df is not None and not df.empty:
            return df, "SEC EDGAR: ok"
        return pd.DataFrame(), "SEC EDGAR: no annual ROIC rows parsed from company facts"
    except EdgarError as exc:
        return pd.DataFrame(), f"SEC EDGAR: {exc}"


def _load_eodhd_roic_annual(symbol_with_exchange: str) -> tuple[pd.DataFrame, str]:
    from stocks_dashboard.eodhd_fundamentals import roic_annual_from_eodhd

    if not should_attempt_eodhd_fundamentals():
        return pd.DataFrame(), "EODHD yearly: skipped (no key or EODHD_FUNDAMENTALS_ENABLED=false)"
    try:
        payload = fetch_fundamentals_payload(symbol_with_exchange)
        df = roic_annual_from_eodhd(payload)
        if df is not None and not df.empty:
            return df, "EODHD yearly financials: ok"
        return pd.DataFrame(), "EODHD yearly: no ROIC rows parsed from Financials"
    except (EODHDFundamentalsDisabled, EODHDFundamentalsPlanError, EODHDError) as exc:
        return pd.DataFrame(), f"EODHD yearly: {exc}"


def load_valuation_context(
    symbol_with_exchange: str,
    bare_symbol: str,
    *,
    cik_map: dict[str, int] | None = None,
) -> ValuationContext:
    """
    Load ROIC / PE helpers for one symbol.

    Never raises — failures become empty metrics plus optional warnings/attempt logs.
    """
    sym = symbol_with_exchange.strip().upper()
    bare = bare_symbol.strip().upper()

    eodhd = valuation_snapshot(sym)
    roic_latest: float | None = eodhd.get("roic") or eodhd.get("roe_ttm")
    trailing_pe = eodhd.get("trailing_pe")
    source_note: str | None = None
    if eodhd:
        source_note = "Valuation ratios from **EODHD fundamentals** (Highlights / Valuation)."

    roic_annual = pd.DataFrame()
    roic_annual_source: str | None = None
    attempts: list[str] = []
    yahoo_warning: str | None = None

    df_edgar, msg_edgar = _load_edgar_roic_annual(bare, cik_map)
    attempts.append(msg_edgar)
    if not df_edgar.empty:
        roic_annual = df_edgar
        roic_annual_source = "SEC EDGAR (company facts)"

    if roic_annual.empty and yahoo_pe_roic_enabled():
        try:
            if roic_latest is None:
                roic_latest = roic_latest_from_info(bare)
            df_yahoo = roic_annual_table(bare)
            if not df_yahoo.empty:
                roic_annual = df_yahoo
                roic_annual_source = "Yahoo (`yfinance` statements)"
                attempts.append("Yahoo: ok")
            else:
                attempts.append("Yahoo: empty annual ROIC table")
        except Exception as exc:
            yahoo_warning = _yahoo_warning(exc)
            attempts.append(f"Yahoo: {type(exc).__name__}")

    if roic_annual.empty:
        df_eodhd, msg_eodhd = _load_eodhd_roic_annual(sym)
        attempts.append(msg_eodhd)
        if not df_eodhd.empty:
            roic_annual = df_eodhd
            roic_annual_source = "EODHD yearly financials"

    if roic_annual_source:
        note = f"Annual ROIC from **{roic_annual_source}**."
        source_note = f"{source_note} {note}" if source_note else note
    elif not eodhd and not yahoo_pe_roic_enabled():
        source_note = (
            "PE / ROIC: set `SEC_USER_AGENT` for free US annual ROIC (EDGAR), "
            "`EODHD_FUNDAMENTALS_ENABLED=true`, or `YAHOO_PE_ROIC_ENABLE=true`."
        )

    return ValuationContext(
        roic_latest=roic_latest,
        roic_annual=roic_annual,
        eodhd_trailing_pe=trailing_pe,
        source_note=source_note,
        yahoo_warning=yahoo_warning,
        roic_annual_source=roic_annual_source,
        roic_annual_attempts=tuple(attempts),
    )


def attach_pe_to_frame(
    ohlcv_with_indicators: pd.DataFrame,
    symbol_with_exchange: str,
    bare_symbol: str,
    ctx: ValuationContext,
) -> pd.DataFrame:
    """
    Add ``PE_TTM_proxy`` when possible: Yahoo TTM series (opt-in) or flat EODHD trailing PE.
    """
    out = ohlcv_with_indicators
    if yahoo_pe_roic_enabled():
        try:
            return attach_pe_proxy(out, bare_symbol)
        except Exception:
            pass
    if ctx.eodhd_trailing_pe is not None:
        out = out.copy()
        out["PE_TTM_proxy"] = float(ctx.eodhd_trailing_pe)
        return out
    return out
