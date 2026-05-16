# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""Parse comma-separated ticker lists (max 10)."""

from __future__ import annotations

import re

_MAX = 10


def parse_symbols(text: str, *, max_symbols: int = _MAX) -> tuple[list[str], str | None]:
    raw = [p.strip().upper() for p in text.split(",")]
    seen: set[str] = set()
    out: list[str] = []
    for p in raw:
        if not p:
            continue
        if not re.fullmatch(r"[A-Z0-9.\-]{1,15}", p):
            return [], f"Invalid ticker: {p!r}"
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
        if len(out) > max_symbols:
            return [], f"Enter at most {max_symbols} distinct tickers."
    if not out:
        return [], "Enter at least one ticker (e.g. AAPL, MSFT)."
    return out, None
