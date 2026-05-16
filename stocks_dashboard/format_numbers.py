# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""Compact M/B/T display for large dollar amounts in fundamentals tables."""

from __future__ import annotations

import re

import pandas as pd

# Rows that stay numeric (ratios, per-share) — not scaled to M/B.
_RATIO_ROW_PATTERNS = (
    re.compile(r"eps", re.I),
    re.compile(r"debt\s*/\s*equity", re.I),
    re.compile(r"ratio", re.I),
    re.compile(r"margin", re.I),
    re.compile(r"%", re.I),
)

_CURRENCY_ROW_HINTS = (
    "revenue",
    "income",
    "cash flow",
    "cashflow",
    "debt",
    "equity",
    "shares outstanding",
)


def format_compact(value: float | int | None) -> str:
    """Format large numbers as ``1.12B``, ``450.5M``, etc."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)
    if pd.isna(n):
        return ""
    sign = "-" if n < 0 else ""
    n = abs(n)
    if n >= 1e12:
        return f"{sign}{n / 1e12:.2f}T"
    if n >= 1e9:
        return f"{sign}{n / 1e9:.2f}B"
    if n >= 1e6:
        return f"{sign}{n / 1e6:.2f}M"
    if n >= 1e3:
        return f"{sign}{n / 1e3:.2f}K"
    if abs(n) < 1 and n != 0:
        return f"{sign}{n:.4f}"
    return f"{sign}{n:,.2f}"


def _is_ratio_row(label: str) -> bool:
    return any(p.search(label) for p in _RATIO_ROW_PATTERNS)


def _is_currency_row(label: str) -> bool:
    low = label.lower()
    if _is_ratio_row(label):
        return False
    if "shares outstanding" in low:
        return True
    return any(h in low for h in _CURRENCY_ROW_HINTS)


def format_fundamentals_display(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a display copy with currency rows in M/B/T and ratios/EPS left readable.
    """
    if df is None or df.empty:
        return df
    out = df.copy().astype(object)
    for idx in out.index:
        label = str(idx)
        if not _is_currency_row(label):
            continue
        for col in out.columns:
            raw = out.at[idx, col]
            if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                out.at[idx, col] = ""
                continue
            try:
                num = float(raw)
            except (TypeError, ValueError):
                continue
            if "shares outstanding" in label.lower():
                if num >= 1e9:
                    out.at[idx, col] = f"{num / 1e9:.2f}B sh"
                elif num >= 1e6:
                    out.at[idx, col] = f"{num / 1e6:.2f}M sh"
                else:
                    out.at[idx, col] = f"{num:,.0f}"
            else:
                out.at[idx, col] = format_compact(num)
    return out
