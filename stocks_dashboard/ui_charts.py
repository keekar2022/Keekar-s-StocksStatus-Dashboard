# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""Plotly chart helpers for OHLCV candlesticks and indicator line charts."""

from __future__ import annotations

import re
from typing import Literal

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DisplayMode = Literal["chart", "table", "both"]


def _sanitize_chart_key(key: str) -> str:
    """Streamlit element keys: unique, stable, alphanumeric-ish."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", key)[:200]


def _unique_plotly_key(chart_key: str) -> str:
    """Ensure uniqueness across reruns and many charts on one page."""
    if "plotly_chart_seq" not in st.session_state:
        st.session_state.plotly_chart_seq = 0
    st.session_state.plotly_chart_seq += 1
    seq = st.session_state.plotly_chart_seq
    return _sanitize_chart_key(f"{chart_key}_{seq}")


def _unique_table_key(chart_key: str) -> str:
    if "data_table_seq" not in st.session_state:
        st.session_state.data_table_seq = 0
    st.session_state.data_table_seq += 1
    seq = st.session_state.data_table_seq
    return _sanitize_chart_key(f"{chart_key}_tbl_{seq}")


def chart_display_mode_selector(scope: str) -> DisplayMode:
    """Chart / table / both — applies to OHLCV and indicator visuals on a tab."""
    label_map: dict[str, DisplayMode] = {
        "Chart": "chart",
        "Table": "table",
        "Both": "both",
    }
    choice = st.radio(
        "View charts as",
        options=["Chart", "Table", "Both"],
        horizontal=True,
        key=f"chart_display_{scope}",
        help="Table shows the same underlying series as the charts (date-indexed rows).",
    )
    return label_map[choice]


def _ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index, errors="coerce")
    return out.sort_index()


def _prepare_table_df(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    sub = _ensure_datetime_index(df)
    if columns:
        cols = [c for c in columns if c in sub.columns]
        sub = sub[cols] if cols else sub
    out = sub.reset_index()
    date_col = out.columns[0]
    if date_col != "Date":
        out = out.rename(columns={date_col: "Date"})
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for col in out.select_dtypes(include="number").columns:
        out[col] = out[col].round(4)
    return out


def render_data_table(
    df: pd.DataFrame,
    columns: list[str] | None,
    *,
    title: str | None = None,
    table_key: str,
) -> None:
    if df is None or df.empty:
        st.caption("No data for table.")
        return
    table_df = _prepare_table_df(df, columns)
    if table_df.empty:
        st.caption("No columns available for table.")
        return
    if title:
        st.caption(title)
    st.dataframe(table_df, use_container_width=True, key=_unique_table_key(table_key))


def render_candlestick(
    df: pd.DataFrame,
    *,
    title: str | None = None,
    chart_key: str,
    display: DisplayMode = "chart",
) -> None:
    """OHLC candlestick chart (requires Open, High, Low, Close)."""
    need = {"Open", "High", "Low", "Close"}
    if df is None or df.empty:
        st.caption("No OHLC data for candlestick chart.")
        return
    if not need.issubset(df.columns):
        st.caption(f"Missing columns for candlestick: {need - set(df.columns)}")
        return
    table_cols = list(need)
    if "Volume" in df.columns:
        table_cols.append("Volume")

    if display in ("table", "both"):
        render_data_table(df, table_cols, title=title, table_key=chart_key)
    if display == "table":
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
    st.plotly_chart(fig, use_container_width=True, key=_unique_plotly_key(chart_key))


def render_candlestick_with_overlays(
    ohlcv: pd.DataFrame,
    overlay_cols: list[str],
    *,
    title: str | None = None,
    chart_key: str,
    display: DisplayMode = "chart",
) -> None:
    """Candlestick plus optional line overlays (EMAs, PSAR) on the same panel."""
    if ohlcv is None or ohlcv.empty:
        st.caption("No OHLC data.")
        return
    need = {"Open", "High", "Low", "Close"}
    if not need.issubset(ohlcv.columns):
        st.caption(f"Missing OHLC columns: {need - set(ohlcv.columns)}")
        return

    table_cols = list(need)
    if "Volume" in ohlcv.columns:
        table_cols.append("Volume")
    table_cols.extend(c for c in overlay_cols if c in ohlcv.columns)

    if display in ("table", "both"):
        render_data_table(ohlcv, table_cols, title=title, table_key=chart_key)
    if display == "table":
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
    st.plotly_chart(fig, use_container_width=True, key=_unique_plotly_key(chart_key))


def render_indicator_lines(
    df: pd.DataFrame,
    columns: list[str],
    *,
    title: str | None = None,
    y_prefix: str = "",
    chart_key: str,
    display: DisplayMode = "chart",
) -> None:
    """Multi-series line chart for MACD, RSI, volume indicators, etc."""
    if df is None or df.empty:
        return
    sub = _ensure_datetime_index(df)
    cols = [c for c in columns if c in sub.columns]
    if not cols:
        return

    if display in ("table", "both"):
        render_data_table(sub, cols, title=title, table_key=chart_key)
    if display == "table":
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
    st.plotly_chart(fig, use_container_width=True, key=_unique_plotly_key(chart_key))
