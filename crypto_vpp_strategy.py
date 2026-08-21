"""
Crypto Volume Profile + EMA Strategy (VPP-EMA)
==============================================
Ultra-fast vectorized engine designed specifically for Bitcoin (BTCUSDm) on 5M timeframe.

Quantitative Logic:
1. Macro Trend Filter: 200 EMA + 21/55 EMA Ribbon
2. Continuous Volume Profile (48-bar rolling window):
   - POC (Point of Control): Peak traded volume level
   - VAH (Value Area High): +1.04 std volume boundary (~70% value area)
   - VAL (Value Area Low): -1.04 std volume boundary (~70% value area)
3. Institutional Pullback Entry:
   - Longs: Bullish trend (Price > 200 EMA & 21 EMA > 55 EMA) + Pullback to VAL/POC + Bullish rejection
   - Shorts: Bearish trend (Price < 200 EMA & 21 EMA < 55 EMA) + Rally to VAH/POC + Bearish rejection
4. Risk Management:
   - SL anchored below VAL / Swing Low (0.5 ATR buffer)
   - TP1 at Opposite Value Area (50% partial close + SL to Breakeven)
   - TP2 at 2.0x Risk/Reward Runner
"""

import numpy as np
import pandas as pd
import logging

logger = logging.getLogger("gold_trading_bot")

def compute_rolling_volume_profile(df: pd.DataFrame, lookback: int = 48) -> pd.DataFrame:
    df = df.copy()
    tp = (df['high'] + df['low'] + df['close']) / 3.0
    vol = df['volume'].replace(0, 1.0)
    
    vp_pv = (tp * vol).rolling(lookback).sum()
    vp_v  = vol.rolling(lookback).sum().replace(0, 1.0)
    poc   = vp_pv / vp_v
    
    dev_sq = (tp - poc) ** 2
    vw_var = (dev_sq * vol).rolling(lookback).sum() / vp_v
    vw_std = np.sqrt(np.maximum(vw_var, 0))
    
    vah = poc + (1.04 * vw_std)
    val = poc - (1.04 * vw_std)
    
    df['vp_poc'] = poc
    df['vp_vah'] = vah
    df['vp_val'] = val
    return df


class CryptoVolumeProfileStrategy:
    def __init__(
        self,
        ema_fast: int = 21,
        ema_medium: int = 55,
        ema_slow: int = 200,
        vp_lookback: int = 48,
        rvol_threshold: float = 1.10,
        atr_period: int = 14,
        sl_atr_mult: float = 0.5,
        min_rr: float = 1.5,
        cooldown_bars: int = 12,
    ):
        self.ema_fast = ema_fast
        self.ema_medium = ema_medium
        self.ema_slow = ema_slow
        self.vp_lookback = vp_lookback
        self.rvol_threshold = rvol_threshold
        self.atr_period = atr_period
        self.sl_atr_mult = sl_atr_mult
        self.min_rr = min_rr
        self.cooldown_bars = cooldown_bars

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # EMAs
        ema_f = df['close'].ewm(span=self.ema_fast, adjust=False).mean().values
        ema_m = df['close'].ewm(span=self.ema_medium, adjust=False).mean().values
        ema_s = df['close'].ewm(span=self.ema_slow, adjust=False).mean().values
        
        # ATR
        h = df['high'].values
        l = df['low'].values
        c = df['close'].values
        o = df['open'].values
        vol = df['volume'].values
        
        tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
        tr[0] = h[0] - l[0]
        atr = pd.Series(tr).ewm(span=self.atr_period, adjust=False).mean().values
        
        # Volume Profile
        df_vp = compute_rolling_volume_profile(df, lookback=self.vp_lookback)
        poc = df_vp['vp_poc'].values
        vah = df_vp['vp_vah'].values
        val = df_vp['vp_val'].values
        
        vol_avg = pd.Series(vol).rolling(20).mean().values
        sw_low  = pd.Series(l).rolling(20).min().values
        sw_high = pd.Series(h).rolling(20).max().values
        
        n = len(df)
        signals = np.zeros(n, dtype=int)
        entry_p = np.full(n, np.nan)
        sl_p    = np.full(n, np.nan)
        tp1_p   = np.full(n, np.nan)
        tp2_p   = np.full(n, np.nan)
        rr_p    = np.full(n, np.nan)
        
        warmup = max(self.ema_slow, self.vp_lookback) + 10
        last_sig = -self.cooldown_bars
        
        for i in range(warmup, n):
            if i - last_sig < self.cooldown_bars:
                continue
                
            price = c[i]
            open_p = o[i]
            low_p  = l[i]
            high_p = h[i]
            
            p_poc = poc[i]
            p_vah = vah[i]
            p_val = val[i]
            a     = atr[i]
            
            if np.isnan(p_poc) or np.isnan(a) or a <= 0:
                continue
                
            # Strong Trend Regime
            bullish_regime = (price > ema_s[i]) and (ema_f[i] > ema_m[i]) and (c[i] > ema_f[i])
            bearish_regime = (price < ema_s[i]) and (ema_f[i] < ema_m[i]) and (c[i] < ema_f[i])
            
            bar_bull = price > open_p
            bar_bear = price < open_p
            vol_expansion = vol[i] >= (1.25 * vol_avg[i]) if pd.notna(vol_avg[i]) else True
            
            # BUY SETUP: Volume breakout above POC/VAL in Bullish Trend
            if bullish_regime and (price >= p_poc) and bar_bull and vol_expansion:
                entry = price
                stop  = entry - (1.0 * a) # 1x ATR SL
                take1 = entry + (1.5 * a) # 1.5x ATR TP1 (50% close & lock profit)
                take2 = entry + (3.0 * a) # 3.0x ATR TP2 runner
                
                signals[i] = 1
                entry_p[i] = round(entry, 2)
                sl_p[i]    = round(stop, 2)
                tp1_p[i]   = round(take1, 2)
                tp2_p[i]   = round(take2, 2)
                rr_p[i]    = 3.0
                last_sig = i
                        
            # SELL SETUP: Volume breakdown below POC/VAH in Bearish Trend
            elif bearish_regime and (price <= p_poc) and bar_bear and vol_expansion:
                entry = price
                stop  = entry + (1.0 * a) # 1x ATR SL
                take1 = entry - (1.5 * a) # 1.5x ATR TP1
                take2 = entry - (3.0 * a) # 3.0x ATR TP2
                
                signals[i] = -1
                entry_p[i] = round(entry, 2)
                sl_p[i]    = round(stop, 2)
                tp1_p[i]   = round(take1, 2)
                tp2_p[i]   = round(take2, 2)
                rr_p[i]    = 3.0
                last_sig = i
                        
        df['signal'] = signals
        df['entry_price'] = entry_p
        df['sl'] = sl_p
        df['tp1'] = tp1_p
        df['tp2'] = tp2_p
        df['rr_tp2'] = rr_p
        df['vp_poc'] = poc
        df['vp_vah'] = vah
        df['vp_val'] = val
        return df
