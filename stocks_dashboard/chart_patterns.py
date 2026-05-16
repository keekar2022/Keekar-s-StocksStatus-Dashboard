# Concept: Mukesh Kesharwani
# Contact: mukesh.kesharwani@adobe.com

"""
Heuristic chart-pattern scans on daily OHLCV (POC — not trading advice).

Detectors are intentionally simple: tuned for transparency over institutional-grade accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from ta.trend import EMAIndicator


@dataclass(frozen=True)
class PatternRow:
    pattern: str
    signal: str
    confidence: str
    detail: str


def _ema(series: pd.Series, window: int) -> pd.Series:
    return EMAIndicator(close=series, window=window).ema_indicator()


def _golden_crossover(close: pd.Series) -> PatternRow:
    """Classic: EMA50 crosses above EMA200. Short windows: EMA20 vs EMA50 proxy."""
    n = len(close.dropna())
    if n < 30:
        return PatternRow(
            "Golden crossover",
            "No",
            "n/a",
            "Need at least ~30 daily closes for a reliable moving-average cross scan.",
        )
    if n >= 200:
        e50 = _ema(close, 50)
        e200 = _ema(close, 200)
        bull = e50.iloc[-1] > e200.iloc[-1]
        crossed = ((e50.shift(1) <= e200.shift(1)) & (e50 > e200)).tail(30).any()
        if crossed and bull:
            return PatternRow(
                "Golden crossover",
                "Yes",
                "medium",
                "EMA(50) crossed above EMA(200) within the last ~30 sessions and remains bullish.",
            )
        if bull:
            return PatternRow(
                "Golden crossover",
                "Partial",
                "low",
                "EMA(50) is above EMA(200) now, but no fresh cross detected in the last ~30 sessions.",
            )
        return PatternRow(
            "Golden crossover",
            "No",
            "low",
            "EMA(50) is not above EMA(200); no golden cross in this window.",
        )
    # Short window: 20/50 proxy
    e20 = _ema(close, 20)
    e50 = _ema(close, 50)
    crossed = ((e20.shift(1) <= e50.shift(1)) & (e20 > e50)).tail(15).any()
    bull = e20.iloc[-1] > e50.iloc[-1]
    if crossed and bull:
        return PatternRow(
            "Golden crossover (proxy)",
            "Yes",
            "low",
            "Shorter history: using **EMA(20) vs EMA(50)** as a small-window proxy (classic is 50/200).",
        )
    return PatternRow(
        "Golden crossover (proxy)",
        "No" if not bull else "Partial",
        "low",
        "Short window — classic 50/200 golden cross not available; 20/50 proxy did not show a fresh cross.",
    )


def _rounding_bottom(close: pd.Series) -> PatternRow:
    """U-shaped recovery: drawdown into a mid-window trough, then recovery."""
    s = close.dropna()
    n = len(s)
    if n < 20:
        return PatternRow("Rounding bottom", "No", "n/a", "Need at least ~20 sessions to scan a bowl shape.")

    smooth = s.rolling(window=min(7, n // 4), min_periods=3).mean().dropna()
    if len(smooth) < 12:
        return PatternRow("Rounding bottom", "No", "n/a", "Insufficient smooth series length.")

    # Trough should sit in the middle band (not at edges)
    lo_i, hi_i = int(len(smooth) * 0.25), int(len(smooth) * 0.75)
    mid = smooth.iloc[lo_i:hi_i]
    trough_rel = mid.idxmin()
    trough_pos = smooth.index.get_loc(trough_rel)
    if trough_pos < len(smooth) * 0.15 or trough_pos > len(smooth) * 0.85:
        return PatternRow(
            "Rounding bottom",
            "No",
            "low",
            "Deepest smooth low is too close to an edge for a classic rounding profile.",
        )

    left = smooth.iloc[: trough_pos + 1]
    right = smooth.iloc[trough_pos:]
    if len(left) < 4 or len(right) < 4:
        return PatternRow("Rounding bottom", "No", "low", "Not enough bars on one side of the trough.")

    xl, yl = np.arange(len(left)), left.to_numpy(dtype=float)
    xr, yr = np.arange(len(right)), right.to_numpy(dtype=float)
    m_left, _ = np.polyfit(xl, yl, 1)
    m_right, _ = np.polyfit(xr, yr, 1)
    trough_val = float(smooth.loc[trough_rel])
    left_peak = float(left.iloc[0])
    right_tip = float(right.iloc[-1])
    rebound = (right_tip - trough_val) / max(trough_val, 1e-9)
    drawdown = (left_peak - trough_val) / max(left_peak, 1e-9)

    bowl = m_left < 0 and m_right > 0 and drawdown > 0.03 and rebound > 0.03
    if bowl:
        return PatternRow(
            "Rounding bottom",
            "Yes",
            "low",
            f"Heuristic bowl: decline into mid-window low (~{drawdown:.1%} vs start), then rise (~{rebound:.1%} off trough).",
        )
    return PatternRow(
        "Rounding bottom",
        "No",
        "low",
        "Price path does not match a simple U-shaped decline→trough→recovery heuristic.",
    )


def _local_max_indices(values: np.ndarray, min_sep: int) -> list[int]:
    peaks: list[int] = []
    for i in range(1, len(values) - 1):
        if values[i] >= values[i - 1] and values[i] >= values[i + 1]:
            if not peaks or i - peaks[-1] >= min_sep:
                peaks.append(i)
            elif values[i] > values[peaks[-1]]:
                peaks[-1] = i
    return peaks


def _head_and_shoulders(df: pd.DataFrame) -> PatternRow:
    """Three prominent highs with center (head) highest."""
    highs = df["High"].dropna().to_numpy(dtype=float)
    n = len(highs)
    if n < 25:
        return PatternRow("Head & shoulders", "No", "n/a", "Need more bars to separate three swing highs.")

    min_sep = max(3, n // 12)
    peaks = _local_max_indices(highs, min_sep)
    if len(peaks) < 3:
        return PatternRow(
            "Head & shoulders",
            "No",
            "low",
            f"Fewer than three spaced swing highs found (min separation ~{min_sep} bars).",
        )

    best = None
    best_score = -1.0
    for i in range(len(peaks) - 2):
        l, h, r = peaks[i], peaks[i + 1], peaks[i + 2]
        hl, hh, hr = highs[l], highs[h], highs[r]
        if hh > hl and hh > hr:
            shoulder_sym = abs(hl - hr) / max(hh, 1e-9) < 0.22  # shoulders roughly similar height
            if shoulder_sym:
                score = hh - max(hl, hr)
                if score > best_score:
                    best_score = score
                    best = (l, h, r, hl, hh, hr)
    if best is None:
        return PatternRow(
            "Head & shoulders",
            "No",
            "low",
            "No triple-peak structure with a clear higher middle (head) and similar shoulders.",
        )
    l, h, r, hl, hh, hr = best
    return PatternRow(
        "Head & shoulders",
        "Yes",
        "low",
        f"Heuristic H&S peaks at bar offsets {l}, {h}, {r} (head ≈{hh:.2f}, shoulders ≈{hl:.2f} / {hr:.2f}).",
    )


def _asymmetric_triangle_breakout(df: pd.DataFrame) -> PatternRow:
    """
    Converging highs (down) + rising lows (up), slope magnitudes meaningfully different,
    and a recent close outside the wedge implied by the two trendlines.
    """
    n = len(df)
    if n < 30:
        return PatternRow(
            "Asymmetric triangle breakout",
            "No",
            "n/a",
            "Need at least ~30 sessions to fit converging boundary lines.",
        )

    k = max(20, min(n, n // 3))
    seg = df.iloc[-k:]
    x = np.arange(k, dtype=float)
    hi = seg["High"].to_numpy(dtype=float)
    lo = seg["Low"].to_numpy(dtype=float)
    cl = seg["Close"].to_numpy(dtype=float)

    m_h, b_h = np.polyfit(x, hi, 1)
    m_l, b_l = np.polyfit(x, lo, 1)
    # Symmetrical triangle: highs slope down, lows slope up
    if not (m_h < -1e-6 and m_l > 1e-6):
        return PatternRow(
            "Asymmetric triangle breakout",
            "No",
            "low",
            "High/low trendlines are not both converging (need falling highs and rising lows in the tail window).",
        )

    ratio = abs(m_h) / max(abs(m_l), 1e-9)
    asym = ratio > 1.45 or ratio < (1 / 1.45) or min(abs(m_h), abs(m_l)) < 1e-4 * float(np.nanmean(cl))
    if not asym:
        return PatternRow(
            "Asymmetric triangle breakout",
            "No",
            "low",
            "Boundaries look closer to symmetric convergence than a clearly asymmetric triangle.",
        )

    last_x = float(k - 1)
    upper = m_h * last_x + b_h
    lower = m_l * last_x + b_l
    last_c = float(cl[-1])
    band = upper - lower
    buf = max(band * 0.01, 1e-4 * last_c)
    broke_up = last_c > upper + buf
    broke_dn = last_c < lower - buf
    if broke_up or broke_dn:
        side = "upside" if broke_up else "downside"
        return PatternRow(
            "Asymmetric triangle breakout",
            "Yes",
            "low",
            f"Asymmetric wedge in last {k} bars; latest close suggests **{side}** break vs fitted bounds.",
        )
    return PatternRow(
        "Asymmetric triangle breakout",
        "Partial",
        "low",
        "Converging asymmetric wedge-like structure, but the latest close has not clearly broken a boundary yet.",
    )


def scan_patterns(ohlcv: pd.DataFrame) -> list[PatternRow]:
    """
    Run all pattern heuristics on a single OHLCV slice (must include Open/High/Low/Close/Volume).
    """
    if ohlcv.empty or "Close" not in ohlcv.columns:
        return [
            PatternRow("—", "No", "n/a", "Empty or invalid OHLCV frame."),
        ]
    close = pd.to_numeric(ohlcv["Close"], errors="coerce")
    return [
        _golden_crossover(close),
        _rounding_bottom(close),
        _head_and_shoulders(ohlcv),
        _asymmetric_triangle_breakout(ohlcv),
    ]
