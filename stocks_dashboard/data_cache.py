# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""Disk cache for fundamentals and OHLCV so data survives browser refresh."""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = _PROJECT_ROOT / ".streamlit" / "dashboard_cache"
META_FILE = CACHE_DIR / "meta.json"
FUNDAMENTALS_FILE = CACHE_DIR / "fundamentals.pkl"
OHLCV_FILE = CACHE_DIR / "ohlcv.pkl"


def symbols_key(symbols: list[str]) -> str:
    """Stable cache key from normalized symbol list."""
    return "|".join(s.strip().upper() for s in symbols if s.strip())


@dataclass
class CachedFundamental:
    symbol: str
    primary_source: str
    df: pd.DataFrame | None
    log: tuple[tuple[str, str], ...]


@dataclass
class CachedOHLCV:
    symbol: str
    df: pd.DataFrame
    primary_source: str
    tried: tuple[str, ...]


@dataclass
class DashboardCache:
    symbols_key: str
    fetched_at: str
    fundamentals: list[CachedFundamental]
    ohlcv: dict[str, CachedOHLCV]


def load_cache(symbols: list[str]) -> DashboardCache | None:
    """Load cache if present and symbol list matches."""
    key = symbols_key(symbols)
    if not META_FILE.is_file():
        return None
    try:
        meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if meta.get("symbols_key") != key:
        return None
    if not FUNDAMENTALS_FILE.is_file() or not OHLCV_FILE.is_file():
        return None
    try:
        with FUNDAMENTALS_FILE.open("rb") as f:
            fund_raw = pickle.load(f)
        with OHLCV_FILE.open("rb") as f:
            ohlcv_raw = pickle.load(f)
    except (OSError, pickle.PickleError, TypeError):
        return None

    fundamentals = [
        CachedFundamental(
            symbol=item["symbol"],
            primary_source=item["primary_source"],
            df=item.get("df"),
            log=tuple(tuple(x) for x in item.get("log", [])),
        )
        for item in fund_raw
    ]
    ohlcv: dict[str, CachedOHLCV] = {}
    for sym, item in ohlcv_raw.items():
        ohlcv[sym] = CachedOHLCV(
            symbol=sym,
            df=item["df"],
            primary_source=item["primary_source"],
            tried=tuple(item.get("tried", ())),
        )
    return DashboardCache(
        symbols_key=key,
        fetched_at=meta.get("fetched_at", ""),
        fundamentals=fundamentals,
        ohlcv=ohlcv,
    )


def save_cache(
    symbols: list[str],
    fundamentals: list[CachedFundamental],
    ohlcv: dict[str, CachedOHLCV],
) -> None:
    """Persist fundamentals and OHLCV to disk."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = symbols_key(symbols)
    fetched_at = datetime.now(timezone.utc).isoformat()
    meta = {"symbols_key": key, "fetched_at": fetched_at}
    META_FILE.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    fund_raw = [
        {
            "symbol": f.symbol,
            "primary_source": f.primary_source,
            "df": f.df,
            "log": list(f.log),
        }
        for f in fundamentals
    ]
    ohlcv_raw = {
        sym: {
            "df": o.df,
            "primary_source": o.primary_source,
            "tried": list(o.tried),
        }
        for sym, o in ohlcv.items()
    }
    with FUNDAMENTALS_FILE.open("wb") as f:
        pickle.dump(fund_raw, f, protocol=pickle.HIGHEST_PROTOCOL)
    with OHLCV_FILE.open("wb") as f:
        pickle.dump(ohlcv_raw, f, protocol=pickle.HIGHEST_PROTOCOL)


def clear_cache() -> None:
    """Remove cached data files."""
    for path in (META_FILE, FUNDAMENTALS_FILE, OHLCV_FILE):
        if path.is_file():
            path.unlink(missing_ok=True)
