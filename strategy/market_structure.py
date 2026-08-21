"""
Market Structure & Liquidity Engine
====================================
Detects:
  - Higher Highs (HH), Higher Lows (HL)
  - Lower Highs (LH), Lower Lows (LL)
  - Break of Structure (BOS)
  - Change of Character (ChoCh)
  - Liquidity sweeps (stop hunts above/below key swing points)
  - Equal highs / equal lows (liquidity pools)
  - Swing failure patterns

All swing detection uses ONLY confirmed past bars (no lookahead).
Swing confirmed only AFTER n_right bars have printed to the right.
"""

import numpy as np
import pandas as pd
from typing import Optional


def detect_swing_points(
    df: pd.DataFrame,
    n_left: int = 5,
    n_right: int = 5
) -> pd.DataFrame:
    """
    Detect confirmed swing highs and swing lows.
    A swing high at bar i is confirmed at bar i + n_right.
    A swing low  at bar i is confirmed at bar i + n_right.
    
    IMPORTANT: No lookahead — we mark the detection at i + n_right (when confirmed).
    """
    df = df.copy()
    n = len(df)
    highs = df['high'].values
    lows = df['low'].values

    sh = np.zeros(n, dtype=bool)  # swing high confirmed
    sl = np.zeros(n, dtype=bool)  # swing low confirmed

    for i in range(n_left, n - n_right):
        # Swing High: highest in the left window, and all right bars are lower
        if highs[i] == max(highs[i - n_left:i + n_right + 1]):
            sh[i + n_right] = True  # confirmed at i+n_right

        # Swing Low: lowest in the left+right window
        if lows[i] == min(lows[i - n_left:i + n_right + 1]):
            sl[i + n_right] = True  # confirmed at i+n_right

    df['swing_high'] = sh
    df['swing_low'] = sl
    df['swing_high_price'] = np.where(sh, df['high'], np.nan)
    df['swing_low_price'] = np.where(sl, df['low'], np.nan)

    # Forward fill last confirmed swing levels
    df['last_sh'] = df['swing_high_price'].ffill()
    df['last_sl'] = df['swing_low_price'].ffill()
    return df


def detect_market_structure(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classify market structure from confirmed swings:
      HH + HL = Bullish trend
      LH + LL = Bearish trend
      Mixed   = Consolidation / chop
    
    Also detects Break of Structure (BOS) and Change of Character (ChoCh).
    """
    if 'swing_high' not in df.columns:
        df = detect_swing_points(df)

    df = df.copy()
    n = len(df)

    # Track last two confirmed swings of each type
    prev_sh_price = np.nan
    prev_sl_price = np.nan
    prev2_sh_price = np.nan
    prev2_sl_price = np.nan

    structure = np.zeros(n, dtype=int)   # +1=bullish, -1=bearish, 0=neutral
    bos = np.zeros(n, dtype=bool)        # Break of Structure
    choch = np.zeros(n, dtype=bool)      # Change of Character

    for i in range(n):
        sh = df['swing_high'].iloc[i]
        sl = df['swing_low'].iloc[i]
        price = df['high'].iloc[i]
        low_p = df['low'].iloc[i]

        if sh:
            prev2_sh_price = prev_sh_price
            prev_sh_price = df['swing_high_price'].iloc[i]

        if sl:
            prev2_sl_price = prev_sl_price
            prev_sl_price = df['swing_low_price'].iloc[i]

        # Classify based on last two swings of each type
        hh = (not np.isnan(prev_sh_price)) and (not np.isnan(prev2_sh_price)) and (prev_sh_price > prev2_sh_price)
        hl = (not np.isnan(prev_sl_price)) and (not np.isnan(prev2_sl_price)) and (prev_sl_price > prev2_sl_price)
        lh = (not np.isnan(prev_sh_price)) and (not np.isnan(prev2_sh_price)) and (prev_sh_price < prev2_sh_price)
        ll = (not np.isnan(prev_sl_price)) and (not np.isnan(prev2_sl_price)) and (prev_sl_price < prev2_sl_price)

        if hh and hl:
            structure[i] = 1
        elif lh and ll:
            structure[i] = -1
        elif i > 0:
            structure[i] = structure[i - 1]

        # BOS: price breaks above last swing high in bearish trend
        if structure[i] == -1 and (not np.isnan(prev_sh_price)) and price > prev_sh_price:
            bos[i] = True
            choch[i] = True  # Also ChoCh since trend was bearish

        # BOS: price breaks below last swing low in bullish trend
        if structure[i] == 1 and (not np.isnan(prev_sl_price)) and low_p < prev_sl_price:
            bos[i] = True
            choch[i] = True  # ChoCh — bullish trend broken

    df['market_structure'] = structure
    df['bos'] = bos
    df['choch'] = choch
    df['is_bullish_structure'] = structure == 1
    df['is_bearish_structure'] = structure == -1
    return df


def detect_liquidity_sweeps(
    df: pd.DataFrame,
    sweep_threshold: float = 0.001,
    recovery_bars: int = 3
) -> pd.DataFrame:
    """
    Detect liquidity sweeps (stop hunts).
    
    A bullish sweep (long setup):
      1. Price wicks below last_sl (sweeps sell-stops below swing low)
      2. Price closes ABOVE the last_sl within recovery_bars
      → Institutional buy after stop hunt
    
    A bearish sweep (short setup):
      1. Price wicks above last_sh (sweeps buy-stops above swing high)
      2. Price closes BELOW last_sh within recovery_bars
      → Institutional sell after stop hunt
    
    sweep_threshold: fraction of price to define "significant" wick beyond swing level
    """
    if 'last_sh' not in df.columns:
        df = detect_swing_points(df)

    df = df.copy()
    n = len(df)
    bull_sweep = np.zeros(n, dtype=bool)
    bear_sweep = np.zeros(n, dtype=bool)
    sweep_low_level = np.full(n, np.nan)
    sweep_high_level = np.full(n, np.nan)

    for i in range(recovery_bars, n):
        lsl = df['last_sl'].iloc[i]
        lsh = df['last_sh'].iloc[i]
        curr_low = df['low'].iloc[i]
        curr_high = df['high'].iloc[i]
        curr_close = df['close'].iloc[i]
        prev_close = df['close'].iloc[i - 1]

        if np.isnan(lsl) or np.isnan(lsh):
            continue

        min_wick = lsl * sweep_threshold

        # Bullish sweep: wick below swing low, close above it
        if curr_low < lsl - min_wick and curr_close > lsl and prev_close > lsl * 0.995:
            bull_sweep[i] = True
            sweep_low_level[i] = curr_low

        # Bearish sweep: wick above swing high, close below it
        if curr_high > lsh + min_wick and curr_close < lsh and prev_close < lsh * 1.005:
            bear_sweep[i] = True
            sweep_high_level[i] = curr_high

    df['bull_sweep'] = bull_sweep
    df['bear_sweep'] = bear_sweep
    df['sweep_low_level'] = sweep_low_level
    df['sweep_high_level'] = sweep_high_level
    return df


def detect_equal_levels(
    df: pd.DataFrame,
    tolerance: float = 0.001,
    lookback: int = 50
) -> pd.DataFrame:
    """
    Detect equal highs and equal lows (liquidity pools).
    These are untested stops waiting to be swept.
    """
    df = df.copy()
    n = len(df)
    equal_highs = np.zeros(n, dtype=bool)
    equal_lows = np.zeros(n, dtype=bool)

    for i in range(lookback, n):
        curr_high = df['high'].iloc[i]
        curr_low = df['low'].iloc[i]
        window_highs = df['high'].iloc[i - lookback:i].values
        window_lows = df['low'].iloc[i - lookback:i].values

        tol_h = curr_high * tolerance
        tol_l = curr_low * tolerance

        if np.any(np.abs(window_highs - curr_high) < tol_h):
            equal_highs[i] = True
        if np.any(np.abs(window_lows - curr_low) < tol_l):
            equal_lows[i] = True

    df['equal_highs'] = equal_highs
    df['equal_lows'] = equal_lows
    return df
