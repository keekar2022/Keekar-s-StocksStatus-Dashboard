# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""Load Streamlit Cloud secrets into os.environ (`.env` is not deployed)."""

from __future__ import annotations

import os

# Keys the dashboard reads from the environment (see `.env.example`).
_SECRET_KEYS = (
    "EODHD_API_KEY",
    "EODHD_DEFAULT_EXCHANGE",
    "EODHD_FUNDAMENTALS_ENABLED",
    "EODHD_OHLCV_FALLBACK",
    "SEC_USER_AGENT",
    "YAHOO_PE_ROIC_ENABLE",
    "LEGACY_SOURCES",
    "ALPHA_VANTAGE_API_KEY",
    "ALPHA_VANTAGE_CALL_INTERVAL_SEC",
    "INVESTING_ENABLE",
    "NASDAQ_DATA_LINK_API_KEY",
    "NASDAQ_DATA_LINK_CODE",
    "NASDAQ_DATA_LINK_ROWS",
)


def apply_streamlit_secrets() -> None:
    """
    Copy ``st.secrets`` into ``os.environ`` when not already set.

    On Streamlit Community Cloud, configure App settings → Secrets (TOML).
    Local dev uses .env via load_dotenv.
    """
    try:
        import streamlit as st
    except ImportError:
        return

    try:
        secrets_obj = st.secrets
    except Exception:
        return

    def _set_from_mapping(mapping: object) -> None:
        if not hasattr(mapping, "items"):
            return
        for key, value in mapping.items():
            if key in _SECRET_KEYS and value is not None:
                text = str(value).strip()
                if text and not (os.environ.get(key) or "").strip():
                    os.environ[key] = text

    _set_from_mapping(secrets_obj)
    # Support optional [env] section in secrets.toml
    if hasattr(secrets_obj, "get"):
        _set_from_mapping(secrets_obj.get("env"))
