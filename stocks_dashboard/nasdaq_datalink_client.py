# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""Nasdaq Data Link (formerly Quandl) — optional table fetch."""

from __future__ import annotations

import os

import pandas as pd


class NasdaqDataLinkError(Exception):
    pass


def fetch_dataset_table(code: str, *, rows: int = 250) -> pd.DataFrame:
    """
    Load a tabular dataset the account is entitled to.

    ``code`` is the Data Link code, e.g. ``WIKI/AAPL`` (legacy examples may be retired;
    use a code from your Nasdaq Data Link subscription / free tier).
    """
    key = (os.environ.get("NASDAQ_DATA_LINK_API_KEY") or "").strip()
    if not key:
        raise NasdaqDataLinkError(
            "Set NASDAQ_DATA_LINK_API_KEY (see https://data.nasdaq.com/account/profile)."
        )
    if not code.strip():
        raise NasdaqDataLinkError("Set a dataset code (e.g. from your Nasdaq Data Link account).")

    import nasdaqdatalink as ndl

    ndl.ApiConfig.api_key = key
    try:
        table = ndl.get_table(code, rows=rows)
    except Exception as exc:  # noqa: BLE001 — vendor errors vary
        raise NasdaqDataLinkError(str(exc)) from exc
    if table is None or getattr(table, "empty", True):
        return pd.DataFrame({"info": ["Empty result — check dataset code and entitlements."]})
    return table
