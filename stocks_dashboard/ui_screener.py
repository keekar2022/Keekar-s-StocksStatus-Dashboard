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
    .sd-info-panel-compact {
        font-size: 0.82rem;
        line-height: 1.35;
        color: #334155;
        width: 100%;
        margin: 0;
        padding: 0;
    }
    .sd-info-panel-compact [data-testid="stMarkdownContainer"] {
        margin-bottom: 0;
        padding-bottom: 0;
    }
    .sd-info-panel-compact [data-testid="stMarkdownContainer"] p {
        margin: 0.12rem 0 !important;
        line-height: 1.35 !important;
    }
    .sd-info-panel-compact [data-testid="stMarkdownContainer"] p:first-child {
        margin-top: 0 !important;
    }
    .sd-info-panel-compact [data-testid="stMarkdownContainer"] p:last-child {
        margin-bottom: 0 !important;
    }
    /* Tighter padding on the bordered info box */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.sd-info-panel-compact) {
        padding-top: 0.45rem;
        padding-bottom: 0.45rem;
    }
    .sd-info-panel-compact [data-testid="stExpander"] summary {
        font-size: 0.82rem;
        color: #047857;
        font-weight: 600;
    }
    /* Hide sidebar — controls live in the main info panel */
    section[data-testid="stSidebar"],
    [data-testid="collapsedControl"] {
        display: none !important;
    }
    [data-testid="stAppViewContainer"] > section.main {
        width: 100% !important;
        max-width: 100% !important;
    }
    .sd-page-footer {
        text-align: center;
        margin: 0.25rem 0 0.5rem 0;
    }
    .sd-page-footer [data-testid="stMarkdownContainer"] p {
        font-size: 0.8rem;
        line-height: 1.35;
        color: #64748b;
        margin: 0;
    }
    .sd-page-footer a {
        color: #059669;
    }

    /* Main section tabs — distinct backgrounds so tabs read as clickable */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        border-bottom: 2px solid #e2e8f0;
        padding-bottom: 0.35rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        border: 1px solid #cbd5e1;
        padding: 0.6rem 1.1rem;
        font-weight: 600;
        cursor: pointer;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
    }
    .stTabs [data-baseweb="tab"]:hover {
        filter: brightness(0.97);
        border-color: #94a3b8;
    }
    /* Fundamental — green */
    .stTabs [data-baseweb="tab"]:nth-child(1) {
        background-color: #ecfdf5;
        color: #047857;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"]:nth-child(1) {
        background-color: #059669;
        color: #ffffff;
        border-color: #047857;
    }
    /* Technical — blue */
    .stTabs [data-baseweb="tab"]:nth-child(2) {
        background-color: #eff6ff;
        color: #1d4ed8;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"]:nth-child(2) {
        background-color: #2563eb;
        color: #ffffff;
        border-color: #1d4ed8;
    }
    /* Patterns — amber */
    .stTabs [data-baseweb="tab"]:nth-child(3) {
        background-color: #fffbeb;
        color: #b45309;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"]:nth-child(3) {
        background-color: #d97706;
        color: #ffffff;
        border-color: #b45309;
    }
    /* Horizon sub-tabs (4th+ tab) — neutral slate, still clickable */
    .stTabs [data-baseweb="tab"]:nth-child(n+4) {
        background-color: #f1f5f9;
        color: #334155;
        font-weight: 500;
        padding: 0.45rem 0.85rem;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"]:nth-child(n+4) {
        background-color: #475569;
        color: #ffffff;
        border-color: #334155;
    }
    .stTabs [data-baseweb="tab-panel"] {
        background-color: #fafafa;
        border: 1px solid #e2e8f0;
        border-radius: 0 0 10px 10px;
        padding: 0.75rem 0.25rem 0.25rem 0.25rem;
    }
</style>
"""


def inject_screener_like_css() -> None:
    st.markdown(_SCSS, unsafe_allow_html=True)


def render_app_info_panel(
    *,
    attribution_line: str,
    expander_label: str,
    expander_content: str,
    eodhd_warning: str | None = None,
    sec_info: str | None = None,
) -> None:
    """Full-width info panel (call inside ``st.container(border=True)``)."""
    st.markdown('<div class="sd-info-panel-compact">', unsafe_allow_html=True)
    st.markdown(attribution_line)
    with st.expander(expander_label, expanded=False):
        st.markdown(expander_content)
        if eodhd_warning:
            st.warning(eodhd_warning)
        if sec_info:
            st.info(sec_info)
    st.markdown("</div>", unsafe_allow_html=True)


def render_page_footer(*, build_line: str) -> None:
    """Page footer: build version and link to latest commit on GitHub."""
    st.markdown("---")
    st.markdown('<div class="sd-page-footer">', unsafe_allow_html=True)
    st.markdown(f"**Build:** {build_line}")
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
