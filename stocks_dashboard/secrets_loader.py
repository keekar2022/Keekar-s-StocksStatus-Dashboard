# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""Load Streamlit Cloud secrets into os.environ (``.env`` is used for local dev)."""

from __future__ import annotations

import os

# Keys the dashboard reads from the environment (see `.env.example`).
_SECRET_KEYS = (
    "EODHD_API_KEY",
    "EODHD_DEFAULT_EXCHANGE",
    "EODHD_FUNDAMENTALS_ENABLED",
    "EODHD_OHLCV_FALLBACK",
    "OHLCV_PRIMARY",
    "OHLCV_CACHE_TTL_HOURS",
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


def _set_from_mapping(mapping: object) -> None:
    if not hasattr(mapping, "items"):
        return
    for key, value in mapping.items():
        if key in _SECRET_KEYS and value is not None:
            text = str(value).strip()
            if text and not (os.environ.get(key) or "").strip():
                os.environ[key] = text


def apply_streamlit_secrets() -> None:
    """
    Copy ``st.secrets`` into ``os.environ`` when not already set.

    Local dev: use ``.env`` (``load_dotenv`` in ``app.py``). No ``secrets.toml`` required.
    Streamlit Cloud: configure App settings → Secrets (TOML).
    """
    try:
        import streamlit as st
        from streamlit.errors import StreamlitSecretNotFoundError
    except ImportError:
        return

    try:
        _set_from_mapping(st.secrets)
        if hasattr(st.secrets, "get"):
            env_section = st.secrets.get("env")
            if env_section is not None:
                _set_from_mapping(env_section)
    except StreamlitSecretNotFoundError:
        # No secrets.toml locally — expected; .env supplies variables instead.
        return
    except (AttributeError, TypeError, KeyError):
        return
