# Innovator & concept: Satyan Bansal — satyan.bansal@gmail.com
# Developer: Mukesh Kesharwani — mukesh.kesharwani@adobe.com
"""
Streamlit POC — Keekar's Stocks Status Dashboard.

Default data source is **EODHD** (eodhd.com) for global OHLCV. SEC EDGAR remains
as a free, US-only enhancer for fundamentals.

Run locally:
  python3 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  cp .env.example .env   # set EODHD_API_KEY (and optional SEC_USER_AGENT)
  streamlit run app.py
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from stocks_dashboard.chart_patterns import scan_patterns
from stocks_dashboard.data_cache import (
    CachedFundamental,
    CachedOHLCV,
    clear_cache,
    load_cache,
    save_cache,
    symbols_key,
)
from stocks_dashboard.data_sources import fetch_ohlcv_preferred, load_fundamentals_auto
from stocks_dashboard.yahoo_ohlcv import YahooOHLCVError
from stocks_dashboard.edgar import EdgarError, fetch_ticker_cik_map
from stocks_dashboard.format_numbers import format_fundamentals_display
from stocks_dashboard.fundamentals import direction_note
from stocks_dashboard.nasdaq_datalink_client import NasdaqDataLinkError, fetch_dataset_table
from stocks_dashboard.symbols import parse_symbols
from stocks_dashboard.technical_indicators import compute_indicators, yahoo_pe_roic_enabled
from stocks_dashboard.ui_charts import (
    render_candlestick,
    render_candlestick_with_overlays,
    render_indicator_lines,
)
from stocks_dashboard.ui_screener import (
    inject_screener_like_css,
    render_app_info_panel,
    render_quote_hero,
)
from stocks_dashboard.secrets_loader import apply_streamlit_secrets
from stocks_dashboard.user_prefs import load_symbols_text, save_symbols_text
from stocks_dashboard.valuation import attach_pe_to_frame, load_valuation_context
from stocks_dashboard.version_info import footer_markdown, get_version_info
from stocks_dashboard.yahoo_ohlcv import Horizon, YahooOHLCVError, slice_trading_window

load_dotenv(Path(__file__).resolve().parent / ".env")

APP_TITLE = "Keekar's Stocks Status Dashboard"

st.set_page_config(page_title=APP_TITLE, layout="wide")
apply_streamlit_secrets()
inject_screener_like_css()
_SINGLE_API_BLURB = (
    "Single-API mode: **EODHD** serves global OHLCV. SEC EDGAR is a free US-only "
    "fundamentals enhancer. Set `LEGACY_SOURCES=true` to re-enable the older Yahoo / "
    "Alpha Vantage / Investing chain."
)
_ATTRIBUTION_LINE = (
    "Innovator & concept: **Satyan Bansal** ([satyan.bansal@gmail.com](mailto:satyan.bansal@gmail.com)) · "
    "Developer: **Mukesh Kesharwani**"
)


def _render_header_row() -> None:
    info = get_version_info()
    build_line = footer_markdown(info)
    try:
        col_main, col_info = st.columns([2.4, 1], gap="medium", vertical_alignment="top")
    except TypeError:
        col_main, col_info = st.columns([2.4, 1], gap="medium")
    with col_main:
        st.title(APP_TITLE)
        st.caption(
            "Data loads automatically from cache or live sources. Use **Refresh data** "
            "on each tab to fetch again."
        )
    with col_info:
        with st.container(border=True):
            render_app_info_panel(
                single_api_blurb=_SINGLE_API_BLURB,
                build_line=build_line,
                attribution_line=_ATTRIBUTION_LINE,
            )


_render_header_row()


def _bare_symbol(sym: str) -> str:
    s = (sym or "").strip().upper()
    return s.split(".", 1)[0] if "." in s else s


def _is_us(sym: str) -> bool:
    s = (sym or "").strip().upper()
    return ("." not in s) or s.endswith(".US")


def _ui_key(sym: str, scope: str, element_id: str) -> str:
    """Unique Streamlit widget key (symbol + scope + id)."""
    safe_sym = sym.strip().upper().replace(".", "_")
    return f"{safe_sym}_{scope}_{element_id}"


def _chart_key(sym: str, horizon: str, chart_id: str) -> str:
    return _ui_key(sym, horizon, chart_id)


def _edgar_cik_map() -> dict[str, int] | None:
    if not (os.environ.get("SEC_USER_AGENT") or "").strip():
        return None
    try:
        return fetch_ticker_cik_map()
    except EdgarError as exc:
        st.warning(f"Could not load SEC ticker map: {exc}. EDGAR will be skipped.")
        return None


def _fetch_fundamentals(syms: list[str]) -> list[CachedFundamental]:
    cmap = _edgar_cik_map()
    rows: list[CachedFundamental] = []
    for sym in syms:
        time.sleep(0.25)
        res = load_fundamentals_auto(sym, cmap=cmap)
        rows.append(
            CachedFundamental(
                symbol=sym.strip().upper(),
                primary_source=res.primary_source,
                df=res.df,
                log=res.log,
            )
        )
    return rows


def _fetch_ohlcv_all(syms: list[str]) -> dict[str, CachedOHLCV]:
    out: dict[str, CachedOHLCV] = {}
    for sym in syms:
        time.sleep(0.35)
        key = sym.strip().upper()
        try:
            ohlcv_res = fetch_ohlcv_preferred(sym)
            out[key] = CachedOHLCV(
                symbol=key,
                df=ohlcv_res.df,
                primary_source=ohlcv_res.primary_source,
                tried=ohlcv_res.tried,
            )
        except YahooOHLCVError as exc:
            out[key] = CachedOHLCV(
                symbol=key,
                df=None,
                primary_source="unavailable",
                tried=("error",),
                error=str(exc),
            )
    return out


def _apply_cache_to_session(cache) -> None:
    st.session_state.fundamentals_cache = cache.fundamentals
    st.session_state.ohlcv_cache = cache.ohlcv
    st.session_state.fetched_at = cache.fetched_at
    st.session_state.data_symbols_key = cache.symbols_key


def _persist_session_to_disk(syms: list[str]) -> None:
    fund = st.session_state.get("fundamentals_cache") or []
    ohlcv = st.session_state.get("ohlcv_cache") or {}
    if fund or ohlcv:
        save_cache(syms, fund, ohlcv)
        st.session_state.fetched_at = datetime.now(timezone.utc).isoformat()


def _fetch_all(syms: list[str]) -> None:
    with st.spinner("Loading fundamentals and market data…"):
        st.session_state.fundamentals_cache = _fetch_fundamentals(syms)
        st.session_state.ohlcv_cache = _fetch_ohlcv_all(syms)
        st.session_state.data_symbols_key = symbols_key(syms)
        st.session_state.fetched_at = datetime.now(timezone.utc).isoformat()
        _persist_session_to_disk(syms)


def _ensure_data_loaded(syms: list[str]) -> None:
    key = symbols_key(syms)
    if st.session_state.get("data_symbols_key") != key:
        st.session_state.data_symbols_key = key
        disk = load_cache(syms)
        if disk:
            _apply_cache_to_session(disk)
        else:
            clear_cache()
            _fetch_all(syms)
        return

    if st.session_state.get("fundamentals_cache") is None and st.session_state.get("ohlcv_cache") is None:
        disk = load_cache(syms)
        if disk:
            _apply_cache_to_session(disk)
        else:
            _fetch_all(syms)


def _format_fetched_at() -> str:
    raw = st.session_state.get("fetched_at") or ""
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return raw


def _refresh_toolbar(button_key: str) -> bool:
    """Last-updated caption and Refresh button on one row."""
    fetched = _format_fetched_at()
    try:
        col_info, col_btn = st.columns([5, 1], vertical_alignment="center")
    except TypeError:
        col_info, col_btn = st.columns([5, 1])
    with col_info:
        if fetched:
            st.caption(f"Last updated: **{fetched}**")
    with col_btn:
        return st.button(
            "Refresh data",
            type="primary",
            key=button_key,
            use_container_width=True,
        )


def _render_fundamentals_tab(syms: list[str]) -> None:
    st.markdown(
        """
**Fundamentals.** With `EODHD_API_KEY` set, the app tries **EODHD** first (revenue, operating cash flow, **free cash flow**, debt, equity).
If your plan does not include fundamentals (HTTP 403), it falls back to **SEC EDGAR** for US tickers.
        """
    )
    refresh = _refresh_toolbar("refresh_fund")

    if refresh:
        with st.spinner("Refreshing fundamentals…"):
            st.session_state.fundamentals_cache = _fetch_fundamentals(syms)
            _persist_session_to_disk(syms)
        st.rerun()

    fund_rows: list[CachedFundamental] = st.session_state.get("fundamentals_cache") or []
    if not fund_rows:
        st.info("No fundamentals loaded yet.")
        return

    for row in fund_rows:
        st.divider()
        with st.container(border=True):
            st.markdown(
                f'<p class="sd-section-title">{row.symbol}</p>',
                unsafe_allow_html=True,
            )
            st.caption(f"**Primary source:** {row.primary_source}")
            if row.df is not None:
                st.markdown("**Financial snapshot**")
                st.caption("Currency rows in **M** / **B**; ratios and EPS unchanged.")
                st.dataframe(
                    format_fundamentals_display(row.df),
                    use_container_width=True,
                    key=_ui_key(row.symbol, "fund", "table"),
                )
                note = "" if row.primary_source.startswith("Alpha Vantage") else direction_note(row.df)
                if note:
                    st.text("Approx. change first→last column (where numeric):")
                    st.code(note)
            else:
                st.error(
                    "No fundamentals returned. For US tickers ensure `SEC_USER_AGENT` is set; "
                    "for non-US tickers enable EODHD fundamentals on your plan."
                )
            with st.expander(
                "Source attempt log",
                key=_ui_key(row.symbol, "fund", "log"),
            ):
                for src, msg in row.log:
                    st.text(f"{src}: {msg}")

    ndl_code = (os.environ.get("NASDAQ_DATA_LINK_CODE") or "").strip()
    if ndl_code:
        with st.expander("Supplementary Nasdaq Data Link preview"):
            try:
                ndl_rows = int((os.environ.get("NASDAQ_DATA_LINK_ROWS") or "250").strip() or "250")
                ndl_rows = max(20, min(2000, ndl_rows))
                ndf = fetch_dataset_table(ndl_code, rows=ndl_rows)
                st.dataframe(ndf, use_container_width=True)
            except NasdaqDataLinkError as exc:
                st.warning(str(exc))


def _render_technical_for_symbol(sym: str, full_hist: pd.DataFrame, primary_source: str) -> None:
    render_quote_hero(sym, full_hist, primary_source)
    is_us = _is_us(sym)
    bare_sym = _bare_symbol(sym)
    val_ctx = load_valuation_context(sym, bare_sym) if is_us else None
    if not is_us:
        st.caption("Non-US listing — **PE / ROIC** use EODHD fundamentals when that add-on is enabled.")
    elif val_ctx is not None:
        if val_ctx.source_note:
            st.caption(val_ctx.source_note)
        if val_ctx.yahoo_warning:
            st.warning(val_ctx.yahoo_warning)

    def _render_horizon(horizon: Horizon) -> None:
        try:
            win = slice_trading_window(full_hist, horizon)
        except YahooOHLCVError as exc:
            st.error(str(exc))
            return
        if horizon in ("1M", "6M") and len(win) < 200:
            st.warning(
                "This window is shorter than 200 trading sessions; **EMA(200)** will be mostly undefined."
            )
        out = compute_indicators(win)
        if is_us:
            out = attach_pe_to_frame(out, sym, bare_sym, val_ctx)

        if (
            is_us
            and val_ctx is not None
            and horizon in ("1M", "6M", "1Y")
            and val_ctx.roic_latest is not None
        ):
            st.metric(
                "ROIC / ROE latest (EODHD or Yahoo, if available)",
                f"{val_ctx.roic_latest * 100:.2f}%",
                help="Fundamental ratio from EODHD fundamentals or Yahoo metadata.",
                key=_chart_key(sym, horizon, "roic_metric"),
            )

        with st.expander(
            "Price & trend (candlestick + EMAs, PSAR)",
            expanded=True,
            key=_chart_key(sym, horizon, "exp_price"),
        ):
            render_candlestick_with_overlays(
                win,
                ["EMA_20", "EMA_50", "EMA_200"],
                title="OHLC with EMAs",
                chart_key=_chart_key(sym, horizon, "ohlc_ema"),
            )
            render_indicator_lines(
                win,
                ["Close", "PSAR"],
                title="Close vs PSAR",
                chart_key=_chart_key(sym, horizon, "psar"),
            )

        with st.expander(
            "Momentum (MACD, RSI)",
            expanded=False,
            key=_chart_key(sym, horizon, "exp_momentum"),
        ):
            render_indicator_lines(
                out,
                ["MACD", "MACD_signal", "MACD_hist"],
                title="MACD",
                chart_key=_chart_key(sym, horizon, "macd"),
            )
            render_indicator_lines(
                out,
                ["RSI_14"],
                title="RSI (14)",
                chart_key=_chart_key(sym, horizon, "rsi"),
            )

        with st.expander(
            "Volume (OBV, ADL)",
            expanded=False,
            key=_chart_key(sym, horizon, "exp_volume"),
        ):
            render_indicator_lines(
                out, ["OBV"], title="OBV", chart_key=_chart_key(sym, horizon, "obv")
            )
            render_indicator_lines(
                out, ["ADL"], title="ADL", chart_key=_chart_key(sym, horizon, "adl")
            )

        if is_us and val_ctx is not None:
            with st.expander(
                "Valuation proxy (PE)",
                expanded=False,
                key=_chart_key(sym, horizon, "exp_pe"),
            ):
                if "PE_TTM_proxy" not in out.columns:
                    st.caption(
                        "No PE data. Enable `EODHD_FUNDAMENTALS_ENABLED=true` or `YAHOO_PE_ROIC_ENABLE=true`."
                    )
                else:
                    pe = out[["PE_TTM_proxy"]].dropna(how="all")
                    if not pe.empty:
                        render_indicator_lines(
                            pe,
                            ["PE_TTM_proxy"],
                            title="PE (TTM proxy)",
                            chart_key=_chart_key(sym, horizon, "pe"),
                        )
                        if val_ctx.eodhd_trailing_pe is not None and not yahoo_pe_roic_enabled():
                            st.caption(
                                f"Flat line: EODHD trailing P/E ≈ {val_ctx.eodhd_trailing_pe:.2f} "
                                "(enable Yahoo for a daily TTM EPS series)."
                            )
                    else:
                        st.caption(
                            "No PE data. Enable `EODHD_FUNDAMENTALS_ENABLED=true` or `YAHOO_PE_ROIC_ENABLE=true`."
                        )

        if is_us and val_ctx is not None and horizon == "5Y":
            with st.expander(
                "ROIC — annual approximation (Yahoo statements)",
                expanded=False,
                key=_chart_key(sym, horizon, "exp_roic"),
            ):
                if not val_ctx.roic_annual.empty:
                    st.dataframe(
                        val_ctx.roic_annual,
                        use_container_width=True,
                        key=_chart_key(sym, horizon, "roic_table"),
                    )
                    render_indicator_lines(
                        val_ctx.roic_annual.set_index("period"),
                        ["ROIC_approx"],
                        title="ROIC (annual approx)",
                        chart_key=_chart_key(sym, horizon, "roic_annual"),
                    )
                else:
                    st.caption(
                        "No annual ROIC table (requires `YAHOO_PE_ROIC_ENABLE=true` and reachable Yahoo)."
                    )

    t1m, t6m, t1y, t5y = st.tabs(
        ["1 month (~21)", "6 months (~126)", "1 year (~252)", "5 years"],
    )
    with t1m:
        _render_horizon("1M")
    with t6m:
        _render_horizon("6M")
    with t1y:
        _render_horizon("1Y")
    with t5y:
        _render_horizon("5Y")


def _render_technical_tab(syms: list[str]) -> None:
    st.markdown(
        """
**Technical indicators** use **EODHD** OHLCV. Per horizon: **EMA**, **MACD**, **RSI**, **OBV**, **ADL**, **PSAR**, and optional **PE / ROIC**.
        """
    )
    refresh = _refresh_toolbar("refresh_tech")

    if refresh:
        with st.spinner("Refreshing OHLCV…"):
            st.session_state.ohlcv_cache = _fetch_ohlcv_all(syms)
            _persist_session_to_disk(syms)
        st.rerun()

    ohlcv_map: dict[str, CachedOHLCV] = st.session_state.get("ohlcv_cache") or {}
    if not ohlcv_map:
        st.info("No OHLCV data loaded yet.")
        return

    loaded = [s.strip().upper() for s in syms if ohlcv_map.get(s.strip().upper())]
    st.caption(f"Showing **{len(loaded)}** of **{len(syms)}** symbol(s) — scroll for all tickers.")

    for sym in syms:
        key = sym.strip().upper()
        cached = ohlcv_map.get(key)
        if cached is None:
            st.warning(f"No cached OHLCV for {key}.")
            continue
        st.divider()
        if cached.error:
            st.error(f"**{key}** — {cached.error}")
            continue
        if cached.df is None or cached.df.empty:
            st.warning(f"**{key}** — no OHLCV data.")
            continue
        _render_technical_for_symbol(key, cached.df, cached.primary_source)


def _render_patterns_tab(syms: list[str]) -> None:
    st.markdown(
        """
**Pattern scan** uses cached **EODHD** OHLCV. Patterns are heuristic POC signals, not investment advice.
        """
    )
    refresh = _refresh_toolbar("refresh_pat")

    if refresh:
        with st.spinner("Refreshing OHLCV for patterns…"):
            st.session_state.ohlcv_cache = _fetch_ohlcv_all(syms)
            _persist_session_to_disk(syms)
        st.rerun()

    ohlcv_map: dict[str, CachedOHLCV] = st.session_state.get("ohlcv_cache") or {}
    if not ohlcv_map:
        st.info("No OHLCV data loaded yet.")
        return

    def _pattern_horizon(full_hist: pd.DataFrame, horizon: Horizon, sym_key: str) -> None:
        try:
            win = slice_trading_window(full_hist, horizon)
        except YahooOHLCVError as exc:
            st.error(str(exc))
            return
        if horizon == "1W":
            st.caption("~**One trading week** (5 sessions).")
        rows = scan_patterns(win)
        st.dataframe(
            pd.DataFrame([r.__dict__ for r in rows]),
            use_container_width=True,
            key=_chart_key(sym_key, horizon, "pat_table"),
        )
        render_candlestick(
            win,
            title="OHLC",
            chart_key=_chart_key(sym_key, horizon, "pat_ohlc"),
        )

    for sym in syms:
        key = sym.strip().upper()
        cached = ohlcv_map.get(key)
        if cached is None:
            continue
        st.divider()
        if cached.error:
            st.error(f"**{key}** — {cached.error}")
            continue
        if cached.df is None or cached.df.empty:
            st.warning(f"**{key}** — no OHLCV data.")
            continue
        full_hist = cached.df
        render_quote_hero(key, full_hist, cached.primary_source)

        tw, tm, ts_tab, ty, tf = st.tabs(
            ["1 week (~5)", "1 month (~21)", "6 months (~126)", "1 year (~252)", "5 years"],
        )
        with tw:
            _pattern_horizon(full_hist, "1W", key)
        with tm:
            _pattern_horizon(full_hist, "1M", key)
        with ts_tab:
            _pattern_horizon(full_hist, "6M", key)
        with ty:
            _pattern_horizon(full_hist, "1Y", key)
        with tf:
            _pattern_horizon(full_hist, "5Y", key)


with st.sidebar:
    st.subheader("Data sources")
    st.markdown(
        """
- **EODHD** for OHLCV (`SYMBOL.EXCHANGE`, e.g. `AAPL.US`, `RELIANCE.NSE`).
- **Fundamentals:** EODHD first, then **SEC EDGAR** (US).
- **PE / ROIC:** EODHD or optional Yahoo (`YAHOO_PE_ROIC_ENABLE=true`).
- **Legacy chain:** `LEGACY_SOURCES=true`.
        """
    )
    if not (os.environ.get("EODHD_API_KEY") or "").strip():
        st.warning(
            "Set `EODHD_API_KEY` to load OHLCV. **Local:** `.env` · "
            "**Streamlit Cloud:** App settings → **Secrets** (see `.streamlit/secrets.toml.example`)."
        )
    else:
        st.caption(
            "NSE/BSE symbols (e.g. `BHEL.NSE`) need an **EODHD All-World** plan. "
            "Free/trial keys are often **US-only**; those tickers show an error while US symbols still load."
        )
    if not (os.environ.get("SEC_USER_AGENT") or "").strip():
        st.info(
            "Optional: set `SEC_USER_AGENT` for free **US EDGAR** fundamentals (when EODHD fundamentals "
            "are unavailable). Format: `AppName you@example.com` per "
            "[SEC fair access](https://www.sec.gov/os/accessing-edgar-data). "
            "**Local:** `.env` · **Streamlit Cloud:** App settings → **Secrets**."
        )

    if st.button("Refresh all", type="secondary", key="refresh_all"):
        st.session_state._refresh_all = True

if "symbols_text" not in st.session_state:
    st.session_state.symbols_text = load_symbols_text()


def _persist_symbols() -> None:
    save_symbols_text(st.session_state.symbols_text)


symbols_text = st.text_input(
    "Symbols (comma-separated, max 10) — use `SYMBOL.EXCHANGE`; bare symbols default to `.US`",
    key="symbols_text",
    on_change=_persist_symbols,
)
syms, err = parse_symbols(symbols_text)
if err:
    st.error(err)

if syms and st.session_state.pop("_refresh_all", False):
    clear_cache()
    _fetch_all(syms)
    st.rerun()

if syms:
    _ensure_data_loaded(syms)

tab_fund, tab_tech, tab_pat = st.tabs(
    ["Fundamental", "Technical Indicators", "Patterns"],
)

with tab_fund:
    if not syms:
        st.info("Enter valid tickers above.")
    else:
        _render_fundamentals_tab(syms)

with tab_tech:
    if not syms:
        st.info("Enter valid tickers above.")
    else:
        _render_technical_tab(syms)

with tab_pat:
    if not syms:
        st.info("Enter valid tickers above.")
    else:
        _render_patterns_tab(syms)
