# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""
Technical indicators via the ``ta`` pip package (Python 3.14–compatible alternative to pandas-ta).

Optional Yahoo-based **PE (TTM EPS proxy)** and **ROIC** helpers are opt-in via
``YAHOO_PE_ROIC_ENABLE=true`` (default **false**) because ``yfinance`` often cannot
reach ``fc.yahoo.com`` on corporate networks.
"""

from __future__ import annotations

import os

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD, PSARIndicator, SMAIndicator
from ta.volume import AccDistIndexIndicator, OnBalanceVolumeIndicator

# Moving-average envelope: ±2.5% around 20-day SMA (per plan)
ENVELOPE_PCT = 0.025


def yahoo_pe_roic_enabled() -> bool:
    """Whether to call Yahoo ``yfinance`` for PE / ROIC (off by default in EODHD mode)."""
    raw = (os.environ.get("YAHOO_PE_ROIC_ENABLE") or "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


def compute_indicators(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """
    Append EMA(20,50,200), MACD(12,26,9), RSI(14), OBV, ADL (``ta`` AccDistIndex), PSAR,
    and SMA(20) envelope bands to a copy of the input frame.

    Expects columns: Open, High, Low, Close, Volume (yfinance default).
    """
    df = ohlcv.copy()
    c = df["Close"]
    h, l, v = df["High"], df["Low"], df["Volume"]

    df["EMA_20"] = EMAIndicator(close=c, window=20).ema_indicator()
    df["EMA_50"] = EMAIndicator(close=c, window=50).ema_indicator()
    df["EMA_200"] = EMAIndicator(close=c, window=200).ema_indicator()

    macd = MACD(close=c, window_slow=26, window_fast=12, window_sign=9)
    df["MACD"] = macd.macd()
    df["MACD_signal"] = macd.macd_signal()
    df["MACD_hist"] = macd.macd_diff()

    df["RSI_14"] = RSIIndicator(close=c, window=14).rsi()
    df["OBV"] = OnBalanceVolumeIndicator(close=c, volume=v).on_balance_volume()
    df["ADL"] = AccDistIndexIndicator(high=h, low=l, close=c, volume=v).acc_dist_index()

    ps = PSARIndicator(high=h, low=l, close=c)
    df["PSAR"] = ps.psar()

    sma20 = SMAIndicator(close=c, window=20).sma_indicator()
    df["ENV_SMA20"] = sma20
    df["ENV_upper"] = sma20 * (1 + ENVELOPE_PCT)
    df["ENV_lower"] = sma20 * (1 - ENVELOPE_PCT)
    return df


def _quarterly_income(symbol: str) -> pd.DataFrame:
    if not yahoo_pe_roic_enabled():
        return pd.DataFrame()
    import yfinance as yf

    try:
        t = yf.Ticker(symbol.strip().upper())
    except Exception:
        return pd.DataFrame()
    getter = getattr(t, "get_income_stmt", None)
    if callable(getter):
        try:
            q = getter(freq="quarterly")
            if isinstance(q, pd.DataFrame) and not q.empty:
                return q
        except Exception:
            pass
    q = getattr(t, "quarterly_income_stmt", None)
    if isinstance(q, pd.DataFrame) and not q.empty:
        return q
    return pd.DataFrame()


def pe_ttm_proxy_series(symbol: str, daily_index: pd.Index) -> pd.Series:
    """
    Daily **PE proxy** = Close / trailing-twelve-month diluted EPS, where TTM EPS is a rolling
    4-quarter sum of reported quarterly diluted EPS, forward-filled to trading days.
    """
    q = _quarterly_income(symbol)
    if q.empty:
        return pd.Series(index=daily_index, dtype=float)

    eps_row = None
    for name in ("Diluted EPS", "Basic EPS"):
        if name in q.index:
            eps_row = name
            break
    if eps_row is None:
        return pd.Series(index=daily_index, dtype=float)

    s = q.loc[eps_row].sort_index()
    s = pd.to_numeric(s, errors="coerce")
    ttm = s.rolling(4, min_periods=4).sum()
    ttm = ttm.dropna()
    if ttm.empty:
        return pd.Series(index=daily_index, dtype=float)
    daily = ttm.reindex(pd.DatetimeIndex(daily_index)).ffill()
    daily.name = "TTM_EPS"
    return daily


def attach_pe_proxy(ohlcv_with_indicators: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if not yahoo_pe_roic_enabled():
        return ohlcv_with_indicators.copy()
    out = ohlcv_with_indicators.copy()
    ttm = pe_ttm_proxy_series(symbol, out.index)
    out["TTM_EPS"] = ttm.reindex(out.index).ffill()
    close = pd.to_numeric(out["Close"], errors="coerce")
    out["PE_TTM_proxy"] = close / out["TTM_EPS"]
    out.loc[out["TTM_EPS"].isna() | (out["TTM_EPS"].abs() < 1e-9), "PE_TTM_proxy"] = pd.NA
    return out


def _annual_income_balance(symbol: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not yahoo_pe_roic_enabled():
        return pd.DataFrame(), pd.DataFrame()
    import yfinance as yf

    try:
        t = yf.Ticker(symbol.strip().upper())
    except Exception:
        return pd.DataFrame(), pd.DataFrame()
    inc = pd.DataFrame()
    bs = pd.DataFrame()
    for getter_name, freq, attr_fallback in (
        ("get_income_stmt", "yearly", "income_stmt"),
        ("get_balance_sheet", "yearly", "balance_sheet"),
    ):
        fn = getattr(t, getter_name, None)
        if callable(fn):
            try:
                df = fn(freq=freq)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    if "income" in getter_name:
                        inc = df
                    else:
                        bs = df
                    continue
            except Exception:
                pass
        fb = getattr(t, attr_fallback, None)
        if isinstance(fb, pd.DataFrame) and not fb.empty:
            if "income" in getter_name and inc.empty:
                inc = fb
            if "balance" in getter_name and bs.empty:
                bs = fb
    return inc, bs


def roic_latest_from_info(symbol: str) -> float | None:
    if not yahoo_pe_roic_enabled():
        return None
    import yfinance as yf

    try:
        info = getattr(yf.Ticker(symbol.strip().upper()), "info", {}) or {}
    except Exception:
        return None
    for key in ("returnOnInvestedCapital", "returnOnCapital", "roic"):
        v = info.get(key)
        if v is not None and isinstance(v, (int, float)) and pd.notna(v):
            return float(v)
    return None


def roic_annual_table(symbol: str) -> pd.DataFrame:
    """
    Simplified **annual ROIC** ≈ NOPAT / Invested Capital, where:
    - NOPAT ≈ Operating Income × (1 − effective tax rate), tax rate from Income Tax / Pretax Income.
    - Invested Capital ≈ Total Debt + Stockholders Equity − Cash (rough proxy).

    Missing rows/columns yield NaN for that year.
    """
    inc, bs = _annual_income_balance(symbol)
    if inc.empty or bs.empty:
        return pd.DataFrame()

    cols = sorted(set(inc.columns) & set(bs.columns), key=lambda x: pd.to_datetime(x))
    if not cols:
        cols = sorted(inc.columns, key=lambda x: pd.to_datetime(x))

    def pick(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
        for n in names:
            if n in df.index:
                return n
        return None

    oi = pick(inc, ("Operating Income", "Operating Income Loss"))
    tax = pick(inc, ("Income Tax Expense", "Tax Provision"))
    pretax = pick(inc, ("Pretax Income", "Income Before Tax"))
    td = pick(bs, ("Total Debt",))
    eq = pick(bs, ("Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"))
    cash = pick(bs, ("Cash And Cash Equivalents", "Cash And Cash Equivalents And Short Term Investments"))

    rows: list[dict[str, float | str | None]] = []
    for c in cols:
        if c not in inc.columns or c not in bs.columns:
            continue
        try:
            op = float(inc.loc[oi, c]) if oi else None
            tx = float(inc.loc[tax, c]) if tax else None
            pre = float(inc.loc[pretax, c]) if pretax else None
            debt = float(bs.loc[td, c]) if td else None
            equity = float(bs.loc[eq, c]) if eq else None
            csh = float(bs.loc[cash, c]) if cash else 0.0
        except (KeyError, TypeError, ValueError):
            continue
        if op is None or debt is None or equity is None:
            continue
        tr = (tx / pre) if (tx is not None and pre and abs(pre) > 1e-9) else 0.21
        tr = max(0.0, min(tr, 0.5))
        nopat = op * (1 - tr)
        ic = debt + equity - csh
        if abs(ic) < 1e-6:
            continue
        rows.append({"period": str(pd.to_datetime(c).date()), "ROIC_approx": nopat / ic})
    return pd.DataFrame(rows)
