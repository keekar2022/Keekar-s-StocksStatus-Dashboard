# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""Parse EODHD ``Financials`` yearly blocks into a wide fundamentals table (EDGAR-compatible layout)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from stocks_dashboard.eodhd_client import EODHDError


def _to_float(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    if pd.isna(val):
        return None
    return val


def _yearly_block(financials: dict[str, Any], section: str) -> dict[str, dict[str, Any]]:
    fin = financials.get(section) if isinstance(financials, dict) else None
    if not isinstance(fin, dict):
        return {}
    yearly = fin.get("yearly")
    return yearly if isinstance(yearly, dict) else {}


def _series_for_field(
    financials: dict[str, Any],
    section: str,
    field_names: tuple[str, ...],
) -> dict[pd.Timestamp, float]:
    yearly = _yearly_block(financials, section)
    out: dict[pd.Timestamp, float] = {}
    for period_key, row in yearly.items():
        if not isinstance(row, dict):
            continue
        ts = pd.to_datetime(period_key, errors="coerce")
        if pd.isna(ts):
            ts = pd.to_datetime(row.get("date"), errors="coerce")
        if pd.isna(ts):
            continue
        for name in field_names:
            val = _to_float(row.get(name))
            if val is not None:
                out[pd.Timestamp(ts)] = val
                break
    return out


def _last_five_periods(*series: dict[pd.Timestamp, float]) -> list[pd.Timestamp]:
    keys: set[pd.Timestamp] = set()
    for s in series:
        keys.update(s.keys())
    if not keys:
        return []
    return sorted(keys)[-5:]


def fundamentals_table_from_eodhd(payload: dict[str, Any]) -> pd.DataFrame:
    """
    Wide fundamentals table: metric rows × last 5 fiscal years (ascending columns).

    Includes **Free cash flow** from ``Cash_Flow.yearly.freeCashFlow``.
    """
    if not isinstance(payload, dict) or not payload:
        raise EODHDError("EODHD fundamentals payload was empty.")

    financials = payload.get("Financials")
    if not isinstance(financials, dict):
        raise EODHDError("EODHD payload missing Financials block.")

    shares_stats = payload.get("SharesStats") if isinstance(payload.get("SharesStats"), dict) else {}

    specs: list[tuple[str, str, tuple[str, ...]]] = [
        ("Revenue", "Income_Statement", ("totalRevenue",)),
        ("Net income", "Income_Statement", ("netIncome",)),
        ("Diluted EPS", "Income_Statement", ("dilutedEPS", "eps", "dilutedEps")),
        (
            "Operating cash flow",
            "Cash_Flow",
            ("totalCashFromOperatingActivities",),
        ),
        ("Free cash flow", "Cash_Flow", ("freeCashFlow",)),
        (
            "Common shares outstanding",
            "Balance_Sheet",
            (
                "commonStockSharesOutstanding",
                "weightedAverageShsOutDil",
                "weightedAverageShsOut",
            ),
        ),
        (
            "Long-term debt",
            "Balance_Sheet",
            ("longTermDebt", "longTermDebtNoncurrent"),
        ),
        (
            "Stockholders equity",
            "Balance_Sheet",
            (
                "totalStockholderEquity",
                "totalStockholdersEquity",
                "commonStockholdersEquity",
            ),
        ),
    ]

    per_metric: dict[str, dict[pd.Timestamp, float]] = {}
    for label, section, fields in specs:
        per_metric[label] = _series_for_field(financials, section, fields)

    # Shares from SharesStats (single snapshot) — skip if no yearly series
    shs = _to_float(shares_stats.get("sharesOutstanding") or shares_stats.get("sharesFloat"))
    if shs is not None and not per_metric.get("Common shares outstanding"):
        periods = _last_five_periods(*per_metric.values())
        if periods:
            per_metric["Common shares outstanding"] = {periods[-1]: shs}

    st_debt = per_metric.get("Long-term debt", {})
    st_eq = per_metric.get("Stockholders equity", {})
    de_ratio: dict[pd.Timestamp, float] = {}
    for ts in set(st_debt) | set(st_eq):
        debt = st_debt.get(ts)
        equity = st_eq.get(ts)
        if debt is None or equity is None or abs(equity) < 1e-9:
            continue
        de_ratio[ts] = debt / equity
    if de_ratio:
        per_metric["Debt / equity (approx)"] = de_ratio

    periods = _last_five_periods(*per_metric.values())
    if not periods:
        raise EODHDError("No yearly financial periods parsed from EODHD Financials.")

    col_labels = [str(p.year) if hasattr(p, "year") else str(p.date()) for p in periods]
    ordered_labels = [lbl for lbl, _, _ in specs]
    if de_ratio:
        ordered_labels.append("Debt / equity (approx)")

    rows: list[list[float | None]] = []
    for label in ordered_labels:
        series = per_metric.get(label, {})
        rows.append([series.get(p) for p in periods])

    df = pd.DataFrame(rows, index=ordered_labels, columns=col_labels)
    df.columns.name = "Fiscal year"
    return df
