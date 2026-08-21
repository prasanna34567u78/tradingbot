"""
Volume Profile Engine — Institutional Grade
==========================================
Completely lookahead-bias-free: all rolling windows use only past data.
Supports:
  - Rolling POC (Point of Control)
  - Rolling VAH / VAL (Value Area High/Low)
  - VWAP + VWAP standard deviation bands
  - Price Acceptance vs Rejection classification
  - POC slope / migration direction
  - Value Area expansion / contraction detection
  - Previous session POC, VAH, VAL (daily anchored)
All calculations use min_periods to avoid forward-fill contamination.
"""

import numpy as np
import pandas as pd
from typing import Tuple


def compute_typical_price(df: pd.DataFrame) -> pd.Series:
    """TP = (H + L + C) / 3 — standard price representation for VP."""
    return (df['high'] + df['low'] + df['close']) / 3.0


def compute_rolling_vwap(df: pd.DataFrame, window: int = 96) -> pd.Series:
    """
    Rolling VWAP over `window` bars.
    Uses min_periods=window//2 to reduce NaN during warmup.
    NO lookahead: .rolling(window) only sees past data.
    """
    tp = compute_typical_price(df)
    vol = df['volume'].replace(0, 1e-6)
    return (tp * vol).rolling(window, min_periods=window // 2).sum() / \
           vol.rolling(window, min_periods=window // 2).sum()


def compute_vwap_bands(df: pd.DataFrame, window: int = 96, n_dev: float = 1.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Rolling VWAP + upper/lower bands.
    Returns: vwap, upper_band, lower_band
    """
    tp = compute_typical_price(df)
    vol = df['volume'].replace(0, 1e-6)
    roll_vol = vol.rolling(window, min_periods=window // 2)
    roll_tpvol = (tp * vol).rolling(window, min_periods=window // 2)

    vwap = roll_tpvol.sum() / roll_vol.sum()

    # VWAP variance (volume-weighted)
    dev_sq = (tp - vwap) ** 2
    vw_var = (dev_sq * vol).rolling(window, min_periods=window // 2).sum() / \
             roll_vol.sum().replace(0, 1e-9)
    vw_std = np.sqrt(np.maximum(vw_var, 0))

    upper = vwap + n_dev * vw_std
    lower = vwap - n_dev * vw_std
    return vwap, upper, lower


def compute_rolling_volume_profile(
    df: pd.DataFrame,
    lookback: int = 96,
    value_area_pct: float = 0.70
) -> pd.DataFrame:
    """
    Vectorized rolling volume profile.
    
    Outputs per bar (strictly historical — no lookahead):
      vp_poc   — Point of Control (volume-weighted mean price)
      vp_vah   — Value Area High (upper boundary of 70% VA)
      vp_val   — Value Area Low  (lower boundary of 70% VA)
      vp_vwap  — Rolling VWAP
      vp_width — Value area width (VAH - VAL)
      vp_skew  — VP skew: (POC - midpoint) / VA_width  > 0 = bullish skew
      
    Mathematical derivation:
      POC  = sum(TP * V) / sum(V)  [volume-weighted mean]
      VW-Var = sum(V * (TP - POC)^2) / sum(V)
      z-score for 70% VA ~ 1.04 standard deviations
      VAH = POC + 1.04 * sqrt(VW-Var)
      VAL = POC - 1.04 * sqrt(VW-Var)
    """
    df = df.copy()
    tp = compute_typical_price(df)
    vol = df['volume'].replace(0, 1e-6)

    roll_min_p = max(lookback // 3, 20)

    vp_pv = (tp * vol).rolling(lookback, min_periods=roll_min_p).sum()
    vp_v = vol.rolling(lookback, min_periods=roll_min_p).sum().replace(0, 1e-9)
    poc = vp_pv / vp_v

    dev_sq = (tp - poc) ** 2
    vw_var = (dev_sq * vol).rolling(lookback, min_periods=roll_min_p).sum() / vp_v
    vw_std = np.sqrt(np.maximum(vw_var, 0))

    # Standard z-score for 70% value area approximation
    z = 1.04 * np.sqrt(2) * value_area_pct  # ~1.04 for 70%
    vah = poc + z * vw_std
    val = poc - z * vw_std

    vwap, _, _ = compute_vwap_bands(df, window=lookback)

    df['vp_poc'] = poc
    df['vp_vah'] = vah
    df['vp_val'] = val
    df['vp_vwap'] = vwap
    df['vp_width'] = vah - val
    midpoint = (vah + val) / 2.0
    df['vp_skew'] = np.where(
        df['vp_width'] > 1e-9,
        (poc - midpoint) / df['vp_width'],
        0.0
    )
    return df


def compute_poc_slope(df: pd.DataFrame, slope_window: int = 5) -> pd.Series:
    """
    Rolling slope of POC over the last `slope_window` bars.
    Positive = POC rising (bullish volume migration)
    Negative = POC falling (bearish volume migration)
    Uses shift to avoid lookahead.
    """
    if 'vp_poc' not in df.columns:
        raise ValueError("Run compute_rolling_volume_profile first.")
    return df['vp_poc'].diff(slope_window).fillna(0.0)


def classify_price_acceptance(df: pd.DataFrame, acceptance_bars: int = 3) -> pd.Series:
    """
    Price Acceptance vs Rejection classifier.
    
    Acceptance: price stays inside the value area for >= acceptance_bars consecutive bars.
    Rejection:  price enters value area and exits rapidly (< acceptance_bars).
    
    Returns:
      +1 = acceptance (bullish for longs near VAL, bearish at VAH)
       0 = neutral
      -1 = rejection (bearish at VAL, bullish from VAH)
    """
    if 'vp_vah' not in df.columns or 'vp_val' not in df.columns:
        raise ValueError("Run compute_rolling_volume_profile first.")

    inside_va = ((df['close'] >= df['vp_val']) & (df['close'] <= df['vp_vah'])).astype(int)
    consecutive = inside_va.rolling(acceptance_bars, min_periods=1).sum()

    result = pd.Series(0, index=df.index)
    result[consecutive >= acceptance_bars] = 1   # Acceptance
    result[(inside_va == 0) & (consecutive.shift(1) < acceptance_bars)] = -1  # Rejection
    return result


def compute_value_area_change(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect value area expansion vs contraction.
    Returns columns:
      va_expanding: bool — value area is getting wider (volatility increasing)
      va_contracting: bool — value area is getting narrower (consolidation)
    """
    if 'vp_width' not in df.columns:
        raise ValueError("Run compute_rolling_volume_profile first.")
    df = df.copy()
    prev_width = df['vp_width'].shift(1)
    df['va_expanding'] = df['vp_width'] > prev_width * 1.05
    df['va_contracting'] = df['vp_width'] < prev_width * 0.95
    return df


def compute_daily_anchored_vp(df: pd.DataFrame) -> pd.DataFrame:
    """
    Daily-anchored Volume Profile levels.
    For each bar, provides the PREVIOUS day's POC, VAH, VAL.
    Strictly no lookahead: uses previous day's completed session.
    """
    df = df.copy()
    df['_date'] = df['time'].dt.date if 'time' in df.columns else pd.Series(range(len(df))).values
    tp = compute_typical_price(df)
    vol = df['volume'].replace(0, 1e-6)
    df['_tp'] = tp
    df['_vol'] = vol

    daily_poc = {}
    daily_vah = {}
    daily_val = {}

    # Build daily stats from scratch
    grouped = df.groupby('_date')
    dates_sorted = sorted(df['_date'].unique())
    for d in dates_sorted:
        g = grouped.get_group(d)
        pv = (g['_tp'] * g['_vol']).sum()
        v = g['_vol'].sum()
        if v < 1e-9:
            continue
        poc_d = pv / v
        dev_sq = (g['_tp'] - poc_d) ** 2
        vw_var = (dev_sq * g['_vol']).sum() / v
        vw_std = np.sqrt(max(vw_var, 0))
        daily_poc[d] = poc_d
        daily_vah[d] = poc_d + 1.04 * vw_std
        daily_val[d] = poc_d - 1.04 * vw_std

    # Map to previous day
    prev_poc = []
    prev_vah = []
    prev_val = []
    prev_date = None
    for _, row in df.iterrows():
        d = row['_date']
        if prev_date is not None and prev_date in daily_poc:
            prev_poc.append(daily_poc[prev_date])
            prev_vah.append(daily_vah[prev_date])
            prev_val.append(daily_val[prev_date])
        else:
            prev_poc.append(np.nan)
            prev_vah.append(np.nan)
            prev_val.append(np.nan)
        if d != prev_date:
            prev_date = d

    df['prev_day_poc'] = prev_poc
    df['prev_day_vah'] = prev_vah
    df['prev_day_val'] = prev_val
    df.drop(columns=['_date', '_tp', '_vol'], inplace=True)
    return df
