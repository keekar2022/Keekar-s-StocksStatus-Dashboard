# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""Annual ROIC approximation from SEC EDGAR, EODHD yearly financials, or Yahoo statements."""

from __future__ import annotations

from typing import Any

import pandas as pd

from stocks_dashboard.fundamentals import _fy_rows_for_concept, _pick_concept


def _approx_roic_rows(
    years: list[int],
    *,
    op_by: dict[int, float],
    tax_by: dict[int, float],
    pretax_by: dict[int, float],
    debt_by: dict[int, float],
    equity_by: dict[int, float],
    cash_by: dict[int, float],
) -> list[dict[str, float | str]]:
    """NOPAT / invested capital per fiscal year (same formula as Yahoo path)."""
    rows: list[dict[str, float | str]] = []
    for fy in years:
        op = op_by.get(fy)
        debt = debt_by.get(fy)
        equity = equity_by.get(fy)
        if op is None or debt is None or equity is None:
            continue
        tx = tax_by.get(fy)
        pre = pretax_by.get(fy)
        csh = cash_by.get(fy, 0.0)
        tr = (tx / pre) if (tx is not None and pre and abs(pre) > 1e-9) else 0.21
        tr = max(0.0, min(tr, 0.5))
        nopat = op * (1 - tr)
        ic = debt + equity - csh
        if abs(ic) < 1e-6:
            continue
        rows.append({"period": str(fy), "ROIC_approx": nopat / ic})
    return rows


def _edgar_fy_series(us_gaap: dict[str, Any], names: tuple[str, ...]) -> dict[int, float]:
    concept = _pick_concept(us_gaap, names)
    by_fy = _fy_rows_for_concept(concept)
    return {fy: float(r["val"]) for fy, r in by_fy.items()}


def roic_annual_from_edgar(company_facts_payload: dict[str, Any]) -> pd.DataFrame:
    """
    Annual ROIC ≈ NOPAT / invested capital from SEC **company facts** (US-GAAP, free).

    Requires a valid ``SEC_USER_AGENT`` and ``fetch_company_facts`` payload.
    """
    if not company_facts_payload:
        return pd.DataFrame()
    us_gaap = (company_facts_payload.get("facts") or {}).get("us-gaap") or {}
    if not us_gaap:
        return pd.DataFrame()

    op_by = _edgar_fy_series(us_gaap, ("OperatingIncomeLoss",))
    tax_by = _edgar_fy_series(
        us_gaap,
        ("IncomeTaxExpenseBenefit", "IncomeTaxExpense", "CurrentIncomeTaxExpenseBenefit"),
    )
    pretax_by = _edgar_fy_series(
        us_gaap,
        (
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxes",
            "IncomeBeforeTax",
        ),
    )
    st_by = _edgar_fy_series(
        us_gaap,
        ("ShortTermBorrowings", "CommercialPaper", "DebtCurrent", "OtherShortTermBorrowings"),
    )
    lt_by = _edgar_fy_series(us_gaap, ("LongTermDebtNoncurrent", "LongTermDebt"))
    eq_by = _edgar_fy_series(us_gaap, ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"))
    cash_by = _edgar_fy_series(
        us_gaap,
        (
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsAndShortTermInvestments",
        ),
    )

    debt_by: dict[int, float] = {}
    years = sorted(set(op_by) | set(eq_by) | set(st_by) | set(lt_by))
    for fy in years:
        st_v = st_by.get(fy, 0.0)
        lt_v = lt_by.get(fy, 0.0)
        debt_by[fy] = st_v + lt_v

    years_sorted = sorted(years)[-5:]
    rows = _approx_roic_rows(
        years_sorted,
        op_by=op_by,
        tax_by=tax_by,
        pretax_by=pretax_by,
        debt_by=debt_by,
        equity_by=eq_by,
        cash_by=cash_by,
    )
    return pd.DataFrame(rows)
