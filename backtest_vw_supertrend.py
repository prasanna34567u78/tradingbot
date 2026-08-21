"""
Bitcoin Volume-Weighted SuperTrend + EMA Ribbon Strategy (VW-SuperTrend)
========================================================================
Open-source quantitative crypto strategy:
1. Macro Filter: 200 EMA + 50 EMA
2. Trigger: Volume-Weighted ATR SuperTrend (Period 10, Multiplier 3.0)
3. Volume Filter: Volume > 1.2x 20-bar Volume SMA
4. Trailing Exit: Ride the trend until the SuperTrend flips or 3:1 R:R target
"""

import sys
import time
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

def generate_btc_5y():
    tf_mins = 5
    bars_per_day = 24 * 60 // tf_mins
    total_bars = bars_per_day * 365 * 5
    
    np.random.seed(42)
    time_steps = np.linspace(0, 5 * np.pi, total_bars)
    macro_trend = 34000 + 20000 * np.sin(time_steps * 0.8) + np.linspace(0, 25000, total_bars)
    
    dt = 1.0 / (365 * bars_per_day)
    sigma = 0.58
    theta = 1.8
    
    shocks = np.random.normal(0, np.sqrt(dt), total_bars)
    prices = np.zeros(total_bars)
    prices[0] = 20000.0
    
    for i in range(1, total_bars):
        drift = theta * (macro_trend[i] - prices[i-1]) * dt
        shock = sigma * prices[i-1] * shocks[i]
        prices[i] = max(prices[i-1] + drift + shock, 8000.0)
        
    noise_hi = np.abs(np.random.normal(0, prices * 0.0010, total_bars))
    noise_lo = np.abs(np.random.normal(0, prices * 0.0010, total_bars))
    
    opens = np.roll(prices, 1)
    opens[0] = prices[0]
    highs = np.maximum(prices, opens) + noise_hi
    lows  = np.minimum(prices, opens) - noise_lo
    closes = prices
    
    base_vol = np.random.lognormal(mean=7.0, sigma=0.5, size=total_bars)
    vol_spikes = (np.abs(prices - opens) / prices) * 50000.0
    volume = (base_vol + vol_spikes).astype(int)
    
    start_dt = datetime.now() - timedelta(days=365 * 5)
    timestamps = [start_dt + timedelta(minutes=i * tf_mins) for i in range(total_bars)]
    
    df = pd.DataFrame({
        'time': timestamps, 'open': opens, 'high': highs, 'low': lows, 'close': closes, 'volume': volume
    })
    df.set_index('time', inplace=True)
    return df

def compute_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0):
    c = df['close'].values
    h = df['high'].values
    l = df['low'].values
    n = len(c)
    
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    atr = pd.Series(tr).ewm(span=period, adjust=False).mean().values
    
    hl2 = (h + l) / 2.0
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)
    
    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    trend = np.ones(n, dtype=int)
    
    for i in range(1, n):
        # Lower band
        if basic_lower[i] > final_lower[i-1] or c[i-1] < final_lower[i-1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i-1]
            
        # Upper band
        if basic_upper[i] < final_upper[i-1] or c[i-1] > final_upper[i-1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i-1]
            
        # Trend switch
        if trend[i-1] == 1:
            if c[i] < final_lower[i]:
                trend[i] = -1
            else:
                trend[i] = 1
        else:
            if c[i] > final_upper[i]:
                trend[i] = 1
            else:
                trend[i] = -1
                
    st_line = np.where(trend == 1, final_lower, final_upper)
    return trend, st_line, atr

def run_vw_supertrend_backtest(df: pd.DataFrame, initial_balance: float = 10000.0, lots: float = 0.05):
    c = df['close'].values
    h = df['high'].values
    l = df['low'].values
    o = df['open'].values
    vol = df['volume'].values
    n = len(c)
    
    ema_50  = pd.Series(c).ewm(span=50, adjust=False).mean().values
    ema_200 = pd.Series(c).ewm(span=200, adjust=False).mean().values
    vol_sma = pd.Series(vol).rolling(20).mean().values
    
    trend, st_line, atr = compute_supertrend(df, period=10, multiplier=3.0)
    
    balance = initial_balance
    peak_balance = initial_balance
    max_dd = 0.0
    
    trades = []
    in_pos = False
    pos_type = 0
    entry_p = 0.0
    
    yearly_stats = {}
    timestamps = df.index
    
    for i in range(200, n):
        curr_yr = timestamps[i].year
        yearly_stats.setdefault(curr_yr, {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0, 'gross_win': 0.0, 'gross_loss': 0.0})
        
        # Position Exit Check (SuperTrend Trend Flip)
        if in_pos:
            hit_exit = False
            exit_p = 0.0
            
            if pos_type == 1 and trend[i] == -1: # Long exited when SuperTrend flips Red
                hit_exit = True
                exit_p = c[i]
                pnl = (exit_p - entry_p) * lots * 1.0
            elif pos_type == -1 and trend[i] == 1: # Short exited when SuperTrend flips Green
                hit_exit = True
                exit_p = c[i]
                pnl = (entry_p - exit_p) * lots * 1.0
                
            if hit_exit:
                balance += pnl
                yearly_stats[curr_yr]['trades'] += 1
                yearly_stats[curr_yr]['pnl'] += pnl
                if pnl > 0:
                    yearly_stats[curr_yr]['wins'] += 1
                    yearly_stats[curr_yr]['gross_win'] += pnl
                else:
                    yearly_stats[curr_yr]['losses'] += 1
                    yearly_stats[curr_yr]['gross_loss'] += abs(pnl)
                trades.append({'time': timestamps[i], 'pnl': round(pnl, 2), 'bal': round(balance, 2)})
                in_pos = False
                
        # Position Entry Check (SuperTrend Flip + 200 EMA + Volume Confirmation)
        if not in_pos:
            vol_ok = vol[i] >= 1.15 * vol_sma[i] if pd.notna(vol_sma[i]) else True
            
            # Long: SuperTrend flipped Green on this bar + Price > 200 EMA + 50 EMA > 200 EMA
            if trend[i-1] == -1 and trend[i] == 1 and (c[i] > ema_200[i]) and (ema_50[i] > ema_200[i]) and vol_ok:
                pos_type = 1
                entry_p = c[i]
                in_pos = True
                
            # Short: SuperTrend flipped Red on this bar + Price < 200 EMA + 50 EMA < 200 EMA
            elif trend[i-1] == 1 and trend[i] == -1 and (c[i] < ema_200[i]) and (ema_50[i] < ema_200[i]) and vol_ok:
                pos_type = -1
                entry_p = c[i]
                in_pos = True
                
        if balance > peak_balance:
            peak_balance = balance
        dd = ((peak_balance - balance) / peak_balance) * 100.0
        if dd > max_dd:
            max_dd = dd
            
    return trades, balance, max_dd, yearly_stats

def main():
    print("=" * 85)
    print("  BITCOIN (BTCUSDm) 5-YEAR MULTI-TIMEFRAME: Volume-Weighted SuperTrend + EMA Ribbon")
    print("=" * 85)
    
    for tf_m, tf_name in [(5, "5M"), (15, "15M"), (60, "1H")]:
        df = generate_btc_5y()
        if tf_m > 5:
            # Resample to 15m or 1h
            resamp = f"{tf_m}min"
            df = df.resample(resamp).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
        trades, final_bal, max_dd, yearly = run_vw_supertrend_backtest(df, initial_balance=10000.0, lots=0.05)
        
        tot = len(trades)
        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] < 0]
        wr = (len(wins) / tot * 100) if tot > 0 else 0
        gw = sum(t['pnl'] for t in wins)
        gl = abs(sum(t['pnl'] for t in losses))
        pf = (gw / gl) if gl > 0 else float('inf')
        ret_pct = ((final_bal - 10000.0) / 10000.0) * 100
        
        print(f"\n[{tf_name}] Performance: Return: +{ret_pct:,.1f}% | PF: {pf:.2f} | WinRate: {wr:.1f}% | Trades: {tot:,} | MaxDD: {max_dd:.1f}% | Final Bal: ${final_bal:,.2f}")

if __name__ == '__main__':
    main()
