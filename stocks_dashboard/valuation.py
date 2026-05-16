# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""
Optional valuation metrics (PE / ROIC) for the Technical tab.

Default path is **EODHD fundamentals** when ``EODHD_FUNDAMENTALS_ENABLED=true``.
Legacy **Yahoo** (`yfinance`) is opt-in via ``YAHOO_PE_ROIC_ENABLE=true`` because
``yfinance`` often fails on corporate networks (``fc.yahoo.com`` / ``curl_cffi``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pandas as pd

from stocks_dashboard.eodhd_client import valuation_snapshot
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


def _yahoo_warning(exc: BaseException) -> str:
    return (
        "Yahoo (`yfinance`) valuation data is unavailable on this network "
        f"({type(exc).__name__}: {exc}). "
        "OHLCV from EODHD still works. Enable `EODHD_FUNDAMENTALS_ENABLED=true` "
        "or set `YAHOO_PE_ROIC_ENABLE=false` to hide this path."
    )


def load_valuation_context(symbol_with_exchange: str, bare_symbol: str) -> ValuationContext:
    """
    Load ROIC / PE helpers for one symbol.

    Never raises — failures become empty metrics plus an optional ``yahoo_warning``.
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
    yahoo_warning: str | None = None

    if yahoo_pe_roic_enabled():
        try:
            if roic_latest is None:
                roic_latest = roic_latest_from_info(bare)
            roic_annual = roic_annual_table(bare)
            if source_note:
                source_note += " Yahoo PE/ROIC also enabled."
            else:
                source_note = "Valuation from **Yahoo** (`yfinance`)."
        except Exception as exc:
            yahoo_warning = _yahoo_warning(exc)
    elif not eodhd:
        source_note = (
            "PE / ROIC skipped: set `EODHD_FUNDAMENTALS_ENABLED=true` "
            "or `YAHOO_PE_ROIC_ENABLE=true` (Yahoo may fail on some networks)."
        )

    return ValuationContext(
        roic_latest=roic_latest,
        roic_annual=roic_annual,
        eodhd_trailing_pe=trailing_pe,
        source_note=source_note,
        yahoo_warning=yahoo_warning,
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
