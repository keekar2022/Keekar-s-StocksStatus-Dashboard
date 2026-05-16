#!/usr/bin/env python3
# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""
Copy non-empty variables from project ``.env`` into ``.streamlit/secrets.toml``.

Use after editing ``.env`` so local ``streamlit run`` and ``st.secrets`` stay in sync.

  python scripts/sync_secrets_from_env.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE_PATH = ROOT / ".env.example"
OUT_PATH = ROOT / ".streamlit" / "secrets.toml"

# Same keys as stocks_dashboard/secrets_loader.py (order preserved for readability).
_KEYS = (
    "EODHD_API_KEY",
    "EODHD_DEFAULT_EXCHANGE",
    "EODHD_FUNDAMENTALS_ENABLED",
    "EODHD_OHLCV_FALLBACK",
    "OHLCV_PRIMARY",
    "OHLCV_CACHE_TTL_HOURS",
    "YAHOO_PE_ROIC_ENABLE",
    "SEC_USER_AGENT",
    "LEGACY_SOURCES",
    "ALPHA_VANTAGE_API_KEY",
    "ALPHA_VANTAGE_CALL_INTERVAL_SEC",
    "INVESTING_ENABLE",
    "NASDAQ_DATA_LINK_API_KEY",
    "NASDAQ_DATA_LINK_CODE",
    "NASDAQ_DATA_LINK_ROWS",
)


def _parse_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise SystemExit(f"Missing {path}. Copy from .env.example first.")
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip()
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        elif raw.startswith("'") and raw.endswith("'"):
            raw = raw[1:-1]
        out[key] = raw
    return out


def _toml_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def main() -> int:
    merged: dict[str, str] = {}
    if ENV_EXAMPLE_PATH.is_file():
        merged.update(_parse_env(ENV_EXAMPLE_PATH))
    merged.update(_parse_env(ENV_PATH))
    env = merged
    lines = [
        "# Local Streamlit secrets — synced from project .env (gitignored; do not commit).",
        "# Regenerate: python scripts/sync_secrets_from_env.py",
        "# https://www.sec.gov/os/accessing-edgar-data",
        "",
    ]
    written = 0
    for key in _KEYS:
        val = (env.get(key) or "").strip()
        if not val:
            continue
        lines.append(f"{key} = {_toml_value(val)}")
        written += 1

    if written == 0:
        raise SystemExit("No matching keys with values found in .env")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {written} keys to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
