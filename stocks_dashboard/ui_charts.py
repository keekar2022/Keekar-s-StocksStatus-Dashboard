# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""Plotly chart helpers for OHLCV candlesticks and indicator line charts."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def _ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index, errors="coerce")
    return out.sort_index()


def render_candlestick(df: pd.DataFrame, *, title: str | None = None) -> None:
    """OHLC candlestick chart (requires Open, High, Low, Close)."""
    if df is None or df.empty:
        st.caption("No OHLC data for candlestick chart.")
        return
    need = {"Open", "High", "Low", "Close"}
    if not need.issubset(df.columns):
        st.caption(f"Missing columns for candlestick: {need - set(df.columns)}")
        return
    ohlc = _ensure_datetime_index(df[list(need)])
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=ohlc.index,
                open=ohlc["Open"],
                high=ohlc["High"],
                low=ohlc["Low"],
                close=ohlc["Close"],
                name="OHLC",
            )
        ]
    )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Price",
        height=420,
        margin=dict(l=40, r=20, t=40 if title else 20, b=40),
        xaxis_rangeslider_visible=False,
        template="plotly_white",
    )
    fig.update_yaxes(tickprefix="$", tickformat=",.2f")
    st.plotly_chart(fig, use_container_width=True)


def render_candlestick_with_overlays(
    ohlcv: pd.DataFrame,
    overlay_cols: list[str],
    *,
    title: str | None = None,
) -> None:
    """Candlestick plus optional line overlays (EMAs, PSAR) on the same panel."""
    if ohlcv is None or ohlcv.empty:
        st.caption("No OHLC data.")
        return
    ohlc = _ensure_datetime_index(ohlcv)
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=ohlc.index,
                open=ohlc["Open"],
                high=ohlc["High"],
                low=ohlc["Low"],
                close=ohlc["Close"],
                name="OHLC",
            )
        ]
    )
    for col in overlay_cols:
        if col not in ohlc.columns:
            continue
        series = pd.to_numeric(ohlc[col], errors="coerce").dropna()
        if series.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.values,
                mode="lines",
                name=col,
                line=dict(width=1.2),
            )
        )
    fig.update_layout(
        title=title,
        height=440,
        margin=dict(l=40, r=20, t=40 if title else 20, b=40),
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_yaxes(tickprefix="$", tickformat=",.2f")
    st.plotly_chart(fig, use_container_width=True)


def render_indicator_lines(
    df: pd.DataFrame,
    columns: list[str],
    *,
    title: str | None = None,
    y_prefix: str = "",
) -> None:
    """Multi-series line chart for MACD, RSI, volume indicators, etc."""
    if df is None or df.empty:
        return
    sub = _ensure_datetime_index(df)
    cols = [c for c in columns if c in sub.columns]
    if not cols:
        return
    fig = go.Figure()
    for col in cols:
        series = pd.to_numeric(sub[col], errors="coerce").dropna()
        if series.empty:
            continue
        fig.add_trace(
            go.Scatter(x=series.index, y=series.values, mode="lines", name=col)
        )
    fig.update_layout(
        title=title,
        height=320,
        margin=dict(l=40, r=20, t=40 if title else 20, b=40),
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    if y_prefix:
        fig.update_yaxes(tickprefix=y_prefix)
    st.plotly_chart(fig, use_container_width=True)
