"""
Market Regime Classification Engine
=====================================
Classifies each bar into one of several regimes:
  1. STRONG_TREND_UP
  2. STRONG_TREND_DOWN
  3. WEAK_TREND_UP
  4. WEAK_TREND_DOWN
  5. RANGE
  6. HIGH_VOL_BREAKOUT
  7. LOW_VOL_COMPRESSION

Features used:
  - ADX (directional trend strength)
  - EMA slope (trend direction)
  - ATR percentile (volatility regime)
  - Bollinger Bandwidth (compression/expansion)
  - VWAP deviation (price location)
  - Volume expansion ratio

No lookahead: all rolling calculations strictly backward.
"""

import numpy as np
import pandas as pd
from enum import IntEnum


class Regime(IntEnum):
    STRONG_TREND_UP       = 1
    STRONG_TREND_DOWN     = -1
    WEAK_TREND_UP         = 2
    WEAK_TREND_DOWN       = -2
    RANGE                 = 0
    HIGH_VOL_BREAKOUT     = 3
    LOW_VOL_COMPRESSION   = 4


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Wilder's ADX — measures trend strength (0–100).
    ADX > 25 = trending; < 20 = ranging.
    """
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    n = len(df)

    tr = np.zeros(n)
    dm_plus = np.zeros(n)
    dm_minus = np.zeros(n)

    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hc, lc)

        h_diff = high[i] - high[i - 1]
        l_diff = low[i - 1] - low[i]
        dm_plus[i]  = h_diff if h_diff > l_diff and h_diff > 0 else 0.0
        dm_minus[i] = l_diff if l_diff > h_diff and l_diff > 0 else 0.0

    tr_s = pd.Series(tr).ewm(span=period, min_periods=period, adjust=False).mean()
    dmp_s = pd.Series(dm_plus).ewm(span=period, min_periods=period, adjust=False).mean()
    dmm_s = pd.Series(dm_minus).ewm(span=period, min_periods=period, adjust=False).mean()

    di_plus  = 100 * dmp_s / tr_s.replace(0, 1e-9)
    di_minus = 100 * dmm_s / tr_s.replace(0, 1e-9)
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, 1e-9)
    adx = dx.ewm(span=period, min_periods=period, adjust=False).mean()
    return adx


def compute_bollinger_bandwidth(df: pd.DataFrame, period: int = 20, n_std: float = 2.0) -> pd.Series:
    """
    Bollinger Band Width = (Upper - Lower) / Middle
    High bandwidth = expansion; Low bandwidth = compression.
    """
    mid = df['close'].rolling(period, min_periods=period // 2).mean()
    std = df['close'].rolling(period, min_periods=period // 2).std()
    upper = mid + n_std * std
    lower = mid - n_std * std
    bw = (upper - lower) / mid.replace(0, 1e-9)
    return bw


def compute_atr_percentile(df: pd.DataFrame, atr_period: int = 14, pct_window: int = 100) -> pd.Series:
    """
    ATR percentile rank within the last pct_window bars.
    0 = historically low volatility; 100 = historically high.
    """
    high_low = df['high'] - df['low']
    high_cp = (df['high'] - df['close'].shift()).abs()
    low_cp = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    atr = tr.ewm(span=atr_period, min_periods=atr_period, adjust=False).mean()

    def pct_rank(series):
        return series.rolling(pct_window, min_periods=pct_window // 2).apply(
            lambda x: pd.Series(x).rank().iloc[-1] / len(x) * 100, raw=True
        )
    return pct_rank(atr)


def classify_regime(
    df: pd.DataFrame,
    adx_trend_threshold: float = 22.0,
    adx_strong_threshold: float = 30.0,
    atr_pct_high: float = 70.0,
    atr_pct_low: float = 30.0,
    bw_low_threshold: float = 0.025,
    ema_slope_period: int = 10,
    ema_period: int = 50,
) -> pd.DataFrame:
    """
    Classify each bar's market regime.
    
    Returns df with columns:
      regime        : Regime enum integer
      regime_label  : human-readable string
      adx           : ADX value
      atr_pct       : ATR percentile
      bb_width      : Bollinger bandwidth
      trend_up      : bool
      trend_down    : bool
    """
    df = df.copy()

    # Indicators
    adx = compute_adx(df, period=14)
    atr_pct = compute_atr_percentile(df)
    bw = compute_bollinger_bandwidth(df)
    ema = df['close'].ewm(span=ema_period, adjust=False).mean()
    ema_slope = ema.diff(ema_slope_period).fillna(0)

    df['adx'] = adx
    df['atr_pct'] = atr_pct
    df['bb_width'] = bw
    df['ema_slope'] = ema_slope
    df['trend_up'] = (df['close'] > ema) & (ema_slope > 0)
    df['trend_down'] = (df['close'] < ema) & (ema_slope < 0)

    n = len(df)
    regimes = np.zeros(n, dtype=int)
    labels = ['RANGE'] * n

    for i in range(n):
        adx_i = adx.iloc[i]
        atr_i = atr_pct.iloc[i] if not np.isnan(atr_pct.iloc[i]) else 50.0
        bw_i = bw.iloc[i] if not np.isnan(bw.iloc[i]) else 0.05
        up = df['trend_up'].iloc[i]
        down = df['trend_down'].iloc[i]

        if np.isnan(adx_i):
            regimes[i] = Regime.RANGE
            labels[i] = 'RANGE'
            continue

        # High volatility breakout
        if atr_i >= atr_pct_high and adx_i > adx_trend_threshold:
            regimes[i] = Regime.HIGH_VOL_BREAKOUT
            labels[i] = 'HIGH_VOL_BREAKOUT'
        # Low volatility compression
        elif atr_i <= atr_pct_low and bw_i < bw_low_threshold:
            regimes[i] = Regime.LOW_VOL_COMPRESSION
            labels[i] = 'LOW_VOL_COMPRESSION'
        # Strong trends
        elif adx_i > adx_strong_threshold and up:
            regimes[i] = Regime.STRONG_TREND_UP
            labels[i] = 'STRONG_TREND_UP'
        elif adx_i > adx_strong_threshold and down:
            regimes[i] = Regime.STRONG_TREND_DOWN
            labels[i] = 'STRONG_TREND_DOWN'
        # Weak trends
        elif adx_i > adx_trend_threshold and up:
            regimes[i] = Regime.WEAK_TREND_UP
            labels[i] = 'WEAK_TREND_UP'
        elif adx_i > adx_trend_threshold and down:
            regimes[i] = Regime.WEAK_TREND_DOWN
            labels[i] = 'WEAK_TREND_DOWN'
        else:
            regimes[i] = Regime.RANGE
            labels[i] = 'RANGE'

    df['regime'] = regimes
    df['regime_label'] = labels
    return df
