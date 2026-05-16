# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""
Screener.in–inspired presentation helpers (layout only; not affiliated with screener.in).

Adds a compact quote header, light CSS polish, and grouped chart sections for Streamlit.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

_SCSS = """
<style>
    /* Layout polish inspired by clean equity research UIs (original CSS). */
    div[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
    .sd-section-title { font-size: 0.95rem; font-weight: 600; color: #047857; margin: 0.35rem 0 0.5rem 0; }
    .sd-info-panel { font-size: 0.82rem; line-height: 1.45; color: #334155; }
</style>
"""


def inject_screener_like_css() -> None:
    st.markdown(_SCSS, unsafe_allow_html=True)


def render_app_info_panel(
    *,
    single_api_blurb: str,
    build_line: str,
    attribution_line: str,
) -> None:
    """Content for the right-aligned info box (call inside ``st.container(border=True)``)."""
    st.markdown('<div class="sd-info-panel">', unsafe_allow_html=True)
    st.markdown(single_api_blurb)
    st.markdown(f"**Build:** {build_line}")
    st.markdown(attribution_line)
    st.markdown("</div>", unsafe_allow_html=True)


def render_quote_hero(symbol: str, df: pd.DataFrame, ohlcv_source: str) -> None:
    """
    Quote strip: symbol, last close, day change, ~252-session high/low, as-of date.
    """
    sym = symbol.strip().upper()
    with st.container(border=True):
        st.markdown(f'<p class="sd-section-title">{sym}</p>', unsafe_allow_html=True)
        st.caption(f"As-of from loaded OHLCV · {ohlcv_source}")
        if df is None or df.empty or "Close" not in df.columns:
            st.caption("No OHLCV rows to summarize.")
            return
        close = pd.to_numeric(df["Close"], errors="coerce").dropna()
        if close.empty:
            st.caption("No valid closes.")
            return
        last = float(close.iloc[-1])
        delta = None
        if len(close) >= 2:
            prev = float(close.iloc[-2])
            if prev:
                pct = (last - prev) / prev * 100.0
                delta = f"{pct:+.2f}%"
        ts = df.index[-1]
        try:
            tsn = pd.Timestamp(ts)
            if tsn.tzinfo is not None:
                tsn = tsn.tz_convert("UTC").tz_localize(None)
            date_lbl = tsn.strftime("%d %b %Y")
        except (TypeError, ValueError, AttributeError):
            date_lbl = str(ts)

        tail = df.tail(min(252, len(df)))
        hi = float(pd.to_numeric(tail.get("High", close), errors="coerce").max())
        lo = float(pd.to_numeric(tail.get("Low", close), errors="coerce").min())

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Last close", f"{last:,.2f}", delta=delta)
        with m2:
            st.caption("Session date")
            st.markdown(f"**{date_lbl}**")
        with m3:
            st.metric("High (~1Y window)", f"{hi:,.2f}")
        with m4:
            st.metric("Low (~1Y window)", f"{lo:,.2f}")
