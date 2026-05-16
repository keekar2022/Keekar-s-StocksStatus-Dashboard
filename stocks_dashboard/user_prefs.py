# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""Persist user symbol list across browser sessions."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_SYMBOLS_TEXT = "AAPL.US, ADBE.US, BHEL.NSE, MSFT.US, RELIANCE.NSE"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
PREFS_PATH = _PROJECT_ROOT / ".streamlit" / "user_prefs.json"


def load_symbols_text() -> str:
    """Read saved symbols from JSON; fall back to default."""
    if not PREFS_PATH.is_file():
        return DEFAULT_SYMBOLS_TEXT
    try:
        data = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
        text = (data.get("symbols_text") or "").strip()
        return text if text else DEFAULT_SYMBOLS_TEXT
    except (OSError, json.JSONDecodeError, TypeError):
        return DEFAULT_SYMBOLS_TEXT


def save_symbols_text(text: str) -> None:
    """Write symbols to JSON atomically."""
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"symbols_text": text}
    tmp = PREFS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(PREFS_PATH)
