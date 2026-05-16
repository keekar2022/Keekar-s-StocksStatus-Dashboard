# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""
Fundamentals-style tables from Yahoo Finance via the ``yfinance`` pip package.

``yfinance`` uses Yahoo's **public web-style endpoints** (not a contractual "official API").
A paid **Yahoo Finance / market data subscription** may use different products and SLAs;
validate against Yahoo's commercial docs before relying on this POC for production.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


class YahooFinanceError(Exception):
    pass


def _annual_income(t: Any) -> pd.DataFrame:
    getter = getattr(t, "get_income_stmt", None)
    if callable(getter):
        try:
            df = getter(freq="yearly")
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
        except Exception:
            pass
    inc = getattr(t, "income_stmt", None)
    if inc is not None and isinstance(inc, pd.DataFrame) and not inc.empty:
        return inc
    fin = getattr(t, "financials", None)
    if fin is not None and isinstance(fin, pd.DataFrame) and not fin.empty:
        return fin
    return pd.DataFrame()


def _annual_balance(t: Any) -> pd.DataFrame:
    getter = getattr(t, "get_balance_sheet", None)
    if callable(getter):
        try:
            df = getter(freq="yearly")
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
        except Exception:
            pass
    bs = getattr(t, "balance_sheet", None)
    if bs is not None and isinstance(bs, pd.DataFrame) and not bs.empty:
        return bs
    return pd.DataFrame()


def _annual_cashflow(t: Any) -> pd.DataFrame:
    getter = getattr(t, "get_cashflow", None)
    if callable(getter):
        try:
            df = getter(freq="yearly")
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
        except Exception:
            pass
    cf = getattr(t, "cashflow", None)
    if cf is not None and isinstance(cf, pd.DataFrame) and not cf.empty:
        return cf
    return pd.DataFrame()


def _pick_row(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    for name in candidates:
        if name in df.index:
            return name
    return None


def _last_n_period_columns(df: pd.DataFrame, n: int = 5) -> list:
    if df.empty:
        return []
    cols = sorted(df.columns, key=lambda c: pd.to_datetime(c))[-n:]
    return cols


def _volume_by_calendar_year(t: Any) -> pd.Series:
    hist = t.history(period="5y", interval="1d", auto_adjust=False)
    if hist is None or hist.empty or "Volume" not in hist.columns:
        return pd.Series(dtype=float)
    s = hist["Volume"].groupby(hist.index.year).mean()
    return s.sort_index()


def fundamentals_table(symbol: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Build a wide fundamentals table (up to 5 annual columns) plus warnings.

    Returns (df, warnings) where df index is metric labels and columns are period labels.
    """
    try:
        import yfinance as yf
    except ImportError as exc:
        raise YahooFinanceError("Install yfinance: pip install yfinance") from exc

    sym = symbol.strip().upper()
    if not sym:
        raise YahooFinanceError("Empty symbol")

    t = yf.Ticker(sym)
    inc = _annual_income(t)
    if inc.empty:
        raise YahooFinanceError(
            f"No annual income statement returned for {sym}. "
            "Yahoo may be rate-limiting or blocking this network; try again later, another network, "
            "or compare with a Yahoo Finance commercial data product (different from the free yfinance path)."
        )

    cols = _last_n_period_columns(inc, 5)
    if not cols:
        raise YahooFinanceError(f"No statement columns for {sym}")

    warnings: list[str] = []

    bs = _annual_balance(t)
    cf = _annual_cashflow(t)

    def row_from_df(df: pd.DataFrame, candidates: tuple[str, ...]) -> dict[Any, float | None]:
        out: dict[Any, float | None] = {}
        if df.empty:
            for c in cols:
                out[c] = None
            return out
        rname = _pick_row(df, candidates)
        if rname is None:
            for c in cols:
                out[c] = None
            return out
        for c in cols:
            if c not in df.columns:
                out[c] = None
                continue
            v = df.loc[rname, c]
            try:
                out[c] = float(v) if pd.notna(v) else None
            except (TypeError, ValueError):
                out[c] = None
        return out

    row_labels: list[str] = []
    row_values: list[list[float | None]] = []

    def add_row(label: str, series: dict[Any, float | None]) -> None:
        row_labels.append(label)
        row_values.append([series.get(c) for c in cols])

    rev_key = _pick_row(inc, ("Total Revenue", "Revenue", "Net Sales"))
    if rev_key:
        add_row(
            "Revenue",
            {c: float(inc.loc[rev_key, c]) if pd.notna(inc.loc[rev_key, c]) else None for c in cols},
        )
    else:
        warnings.append("Could not find a revenue line on the income statement.")
        add_row("Revenue", {c: None for c in cols})

    ni_key = _pick_row(inc, ("Net Income", "Net Income Common Stockholders"))
    if ni_key:
        add_row(
            "Net income",
            {c: float(inc.loc[ni_key, c]) if pd.notna(inc.loc[ni_key, c]) else None for c in cols},
        )
    else:
        add_row("Net income", {c: None for c in cols})

    eps_key = _pick_row(inc, ("Diluted EPS", "Basic EPS"))
    if eps_key:
        add_row(
            "EPS (diluted or basic)",
            {c: float(inc.loc[eps_key, c]) if pd.notna(inc.loc[eps_key, c]) else None for c in cols},
        )
    else:
        add_row("EPS (diluted or basic)", {c: None for c in cols})

    add_row(
        "Operating cash flow",
        row_from_df(cf, ("Operating Cash Flow", "Total Cash From Operating Activities")),
    )
    add_row("Free cash flow", row_from_df(cf, ("Free Cash Flow",)))

    add_row(
        "Shares outstanding (approx)",
        row_from_df(bs, ("Share Issued", "Ordinary Shares Number", "Common Stock Shares Outstanding")),
    )

    td_key = _pick_row(bs, ("Total Debt",))
    eq_key = _pick_row(bs, ("Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"))
    de: dict[Any, float | None] = {}
    for c in cols:
        if bs.empty or not td_key or not eq_key or c not in bs.columns:
            de[c] = None
            continue
        try:
            debt = float(bs.loc[td_key, c]) if pd.notna(bs.loc[td_key, c]) else None
            eq = float(bs.loc[eq_key, c]) if pd.notna(bs.loc[eq_key, c]) else None
            if debt is None or eq is None or eq == 0:
                de[c] = None
            else:
                de[c] = debt / eq
        except (KeyError, TypeError, ValueError):
            de[c] = None
    add_row("Debt / equity (approx)", de)

    vol_s = _volume_by_calendar_year(t)
    vol_row: dict[Any, float | None] = {}
    for c in cols:
        y = pd.to_datetime(c).year
        vol_row[c] = float(vol_s.loc[y]) if y in vol_s.index else None
    add_row("Avg daily volume (calendar year of period end)", vol_row)

    col_names = [str(pd.to_datetime(c).date()) for c in cols]
    df = pd.DataFrame(row_values, index=row_labels, columns=col_names)
    df.columns.name = "Statement period (Yahoo)"

    info = getattr(t, "info", None) or {}
    trailing_pe = info.get("trailingPE") or info.get("forwardPE")
    if trailing_pe is not None and pd.notna(trailing_pe):
        warnings.append(
            f"Latest snapshot trailing/fwd P/E from quote info: {float(trailing_pe):.2f} (not split by statement column)."
        )

    return df, warnings
