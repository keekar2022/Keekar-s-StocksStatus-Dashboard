# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""Map SEC company facts JSON into a compact fundamentals table (annual FY)."""

from __future__ import annotations

from typing import Any

import pandas as pd


def _fy_rows_for_concept(concept: dict[str, Any] | None) -> dict[int, dict[str, Any]]:
    """Latest filing per fiscal year for FY rows only."""
    if not concept:
        return {}
    units = concept.get("units") or {}
    # Prefer USD for currency facts; SEC also uses shares, pure, USD/shares
    unit_priority = ("USD", "shares", "pure", "USD/shares", "shares/USD")
    rows: list[dict[str, Any]] = []
    for uk in unit_priority:
        for row in units.get(uk) or []:
            if row.get("fp") != "FY":
                continue
            fy = row.get("fy")
            val = row.get("val")
            if fy is None or val is None:
                continue
            try:
                fy_i = int(fy)
                val_f = float(val)
            except (TypeError, ValueError):
                continue
            filed = str(row.get("filed") or row.get("end") or "")
            rows.append({"fy": fy_i, "val": val_f, "filed": filed, "end": str(row.get("end") or "")})

    by_fy: dict[int, dict[str, Any]] = {}
    for r in rows:
        cur = by_fy.get(r["fy"])
        if cur is None or r["filed"] > cur["filed"]:
            by_fy[r["fy"]] = r
    return by_fy


def _tenk_rows_for_concept(concept: dict[str, Any] | None) -> dict[int, dict[str, Any]]:
    """Latest 10-K row per fiscal year (some filers omit fp=FY on revenue tags)."""
    if not concept:
        return {}
    units = concept.get("units") or {}
    unit_priority = ("USD", "shares", "pure", "USD/shares", "shares/USD")
    rows: list[dict[str, Any]] = []
    for uk in unit_priority:
        for row in units.get(uk) or []:
            if str(row.get("form", "")).upper() != "10-K":
                continue
            fy = row.get("fy")
            val = row.get("val")
            if fy is None or val is None:
                continue
            try:
                fy_i = int(fy)
                val_f = float(val)
            except (TypeError, ValueError):
                continue
            filed = str(row.get("filed") or row.get("end") or "")
            rows.append({"fy": fy_i, "val": val_f, "filed": filed, "end": str(row.get("end") or "")})
    by_fy: dict[int, dict[str, Any]] = {}
    for r in rows:
        cur = by_fy.get(r["fy"])
        if cur is None or r["filed"] > cur["filed"]:
            by_fy[r["fy"]] = r
    return by_fy


def _pick_concept(us_gaap: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any] | None:
    for n in names:
        if n in us_gaap:
            return us_gaap[n]
    return None


def fundamentals_from_companyfacts(payload: dict[str, Any]) -> pd.DataFrame:
    """Return wide table: index = metric label, columns = last 5 fiscal years (ascending)."""
    facts = (payload.get("facts") or {}).get("us-gaap") or {}
    entity = payload.get("entityName", "")

    specs: list[tuple[str, tuple[str, ...]]] = [
        ("Revenue", ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet")),
        ("Net income", ("NetIncomeLoss",)),
        ("Diluted EPS", ("EarningsPerShareDiluted", "EarningsPerShareBasic")),
        (
            "Operating cash flow",
            (
                "NetCashProvidedByUsedInOperatingActivities",
                "CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations",
            ),
        ),
        ("Free cash flow", ("FreeCashFlow",)),
        ("Common shares outstanding", ("CommonStockSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic")),
        ("Long-term debt", ("LongTermDebtNoncurrent", "LongTermDebt")),
        ("Stockholders equity", ("StockholdersEquity", "LiabilitiesAndStockholdersEquity")),
    ]

    per_metric: dict[str, dict[int, float]] = {}
    all_years: set[int] = set()

    for label, names in specs:
        c = _pick_concept(facts, names)
        by_fy = _fy_rows_for_concept(c)
        if label == "Revenue" and not by_fy:
            by_fy = _tenk_rows_for_concept(c)
        per_metric[label] = {fy: r["val"] for fy, r in by_fy.items()}
        all_years.update(by_fy.keys())

    # Debt / equity ratio (approx): (short + long term debt) / equity
    st = _pick_concept(facts, ("ShortTermBorrowings", "CommercialPaper", "OtherShortTermBorrowings"))
    lt = _pick_concept(facts, ("LongTermDebtNoncurrent", "LongTermDebt"))
    eq = _pick_concept(facts, ("StockholdersEquity",))
    st_by = _fy_rows_for_concept(st)
    lt_by = _fy_rows_for_concept(lt)
    eq_by = _fy_rows_for_concept(eq)
    de_ratio: dict[int, float] = {}
    years_de = set(st_by) | set(lt_by) | set(eq_by)
    for fy in years_de:
        st_v = st_by.get(fy, {}).get("val")
        lt_v = lt_by.get(fy, {}).get("val")
        eq_v = eq_by.get(fy, {}).get("val")
        debt = (float(st_v) if st_v is not None else 0.0) + (float(lt_v) if lt_v is not None else 0.0)
        equity = float(eq_v) if eq_v is not None else 0.0
        if equity == 0:
            continue
        de_ratio[fy] = debt / equity
    ordered_labels = [lbl for lbl, _ in specs]
    if de_ratio:
        per_metric["Debt / equity (approx)"] = de_ratio
        all_years.update(de_ratio.keys())
        ordered_labels.append("Debt / equity (approx)")

    years_sorted = sorted(all_years)[-5:]
    if not years_sorted:
        return pd.DataFrame({"message": [f"No annual FY facts parsed for {entity or 'entity'}"]})

    rows: list[list[float | None]] = []
    for label in ordered_labels:
        col = per_metric.get(label, {})
        rows.append([col.get(y) if col.get(y) is not None else None for y in years_sorted])

    df = pd.DataFrame(rows, index=ordered_labels, columns=[str(y) for y in years_sorted])
    df.columns.name = "Fiscal year (FY)"
    return df


def direction_note(df: pd.DataFrame) -> str:
    if df.empty or df.shape[1] < 2:
        return ""
    first = df.iloc[:, 0]
    last = df.iloc[:, -1]
    lines = []
    for i in df.index:
        a, b = first.loc[i], last.loc[i]
        if pd.isna(a) or pd.isna(b):
            continue
        if float(a) == 0:
            continue
        ch = (float(b) - float(a)) / abs(float(a)) * 100.0
        lines.append(f"{i}: {ch:+.1f}% from first to last FY column")
    return "\n".join(lines[:12]) if lines else ""
