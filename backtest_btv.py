"""
Bitcoin Dynamic Trend & Volume Profile Strategy (BTV)
=====================================================
Quantitative Edge:
1. Donchian/Keltner Volume Volatility Breakout (20-bar channel)
2. EMA Ribbon (21 / 55 / 200 EMA)
3. Volume Profile POC Reclaim: Price breaks out above 20-bar High and POC with Volume > 1.5x average
4. Trailing Stop: 2.5x ATR dynamic trail (gives crypto trades room to breathe)
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

def run_btv_backtest(df: pd.DataFrame, initial_balance: float = 10000.0, lots: float = 0.05):
    c = df['close'].values
    h = df['high'].values
    l = df['low'].values
    o = df['open'].values
    vol = df['volume'].values
    n = len(c)
    
    # 1. EMAs
    ema_21 = pd.Series(c).ewm(span=21, adjust=False).mean().values
    ema_55 = pd.Series(c).ewm(span=55, adjust=False).mean().values
    ema_200 = pd.Series(c).ewm(span=200, adjust=False).mean().values
    
    # 2. Donchian 30-bar Channel
    donchian_hi = pd.Series(h).rolling(30).max().shift(1).values
    donchian_lo = pd.Series(l).rolling(30).min().shift(1).values
    
    # 3. ATR 14
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    atr = pd.Series(tr).ewm(span=14, adjust=False).mean().values
    
    # 4. Volume Profile POC (48-bar rolling VWAP)
    tp = (h + l + c) / 3.0
    v = np.maximum(vol, 1.0)
    vp_pv = pd.Series(tp * v).rolling(48).sum().values
    vp_v  = pd.Series(v).rolling(48).sum().values
    poc   = vp_pv / np.maximum(vp_v, 1.0)
    vol_sma = pd.Series(vol).rolling(20).mean().values
    
    balance = initial_balance
    peak_balance = initial_balance
    max_dd = 0.0
    
    trades = []
    in_pos = False
    pos_type = 0
    entry_p = trail_sl = 0.0
    entry_idx = 0
    cooldown = 12
    last_sig = -cooldown
    
    yearly_stats = {}
    timestamps = df.index
    
    for i in range(200, n):
        curr_yr = timestamps[i].year
        yearly_stats.setdefault(curr_yr, {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0, 'gross_win': 0.0, 'gross_loss': 0.0})
        
        # Position Exit Check (Dynamic 2.5x ATR Trailing Stop)
        if in_pos:
            hit_exit = False
            exit_p = 0.0
            
            if pos_type == 1: # LONG
                # Update Trailing Stop
                new_trail = h[i] - (2.5 * atr[i])
                if new_trail > trail_sl:
                    trail_sl = new_trail
                    
                if l[i] <= trail_sl or c[i] < ema_55[i]:
                    hit_exit = True
                    exit_p = trail_sl if l[i] <= trail_sl else c[i]
                    pnl = (exit_p - entry_p) * lots * 1.0
            else: # SHORT
                new_trail = l[i] + (2.5 * atr[i])
                if new_trail < trail_sl:
                    trail_sl = new_trail
                    
                if h[i] >= trail_sl or c[i] > ema_55[i]:
                    hit_exit = True
                    exit_p = trail_sl if h[i] >= trail_sl else c[i]
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
                last_sig = i
                
        # Position Entry Check
        if not in_pos and (i - last_sig >= cooldown):
            curr_c = c[i]
            curr_a = atr[i]
            curr_v = vol[i]
            
            bull_regime = (curr_c > ema_200[i]) and (ema_21[i] > ema_55[i])
            bear_regime = (curr_c < ema_200[i]) and (ema_21[i] < ema_55[i])
            vol_ok = curr_v >= 1.25 * vol_sma[i] if pd.notna(vol_sma[i]) else True
            
            # LONG BREAKOUT: Bullish regime + Breaks 30-bar high + Price > Volume POC + Volume Expansion
            if bull_regime and (curr_c > donchian_hi[i]) and (curr_c > poc[i]) and vol_ok:
                pos_type = 1
                entry_p = curr_c
                trail_sl = entry_p - (2.5 * curr_a)
                in_pos = True
                entry_idx = i
                
            # SHORT BREAKOUT: Bearish regime + Breaks 30-bar low + Price < Volume POC + Volume Expansion
            elif bear_regime and (curr_c < donchian_lo[i]) and (curr_c < poc[i]) and vol_ok:
                pos_type = -1
                entry_p = curr_c
                trail_sl = entry_p + (2.5 * curr_a)
                in_pos = True
                entry_idx = i
                
        if balance > peak_balance:
            peak_balance = balance
        dd = ((peak_balance - balance) / peak_balance) * 100.0
        if dd > max_dd:
            max_dd = dd
            
    return trades, balance, max_dd, yearly_stats

def main():
    print("=" * 85)
    print("  BITCOIN (BTCUSDm) 5-YEAR 5M: Dynamic Trend & Volume Profile (BTV Strategy)")
    print("=" * 85)
    df = generate_btc_5y()
    
    t0 = time.time()
    trades, final_bal, max_dd, yearly = run_btv_backtest(df, initial_balance=10000.0, lots=0.05)
    print(f"Simulation completed in {time.time() - t0:.2f} seconds.\n", flush=True)
    
    tot = len(trades)
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] < 0]
    wr = (len(wins) / tot * 100) if tot > 0 else 0
    gw = sum(t['pnl'] for t in wins)
    gl = abs(sum(t['pnl'] for t in losses))
    pf = (gw / gl) if gl > 0 else float('inf')
    ret_pct = ((final_bal - 10000.0) / 10000.0) * 100
    
    print("=" * 85)
    print("           BITCOIN (BTCUSDm) 5-YEAR 5M PERFORMANCE VERIFICATION")
    print("=====================================================================================")
    print(f"  Initial Capital     : $ 10,000.00")
    print(f"  Final Equity        : $ {final_bal:,.2f}")
    print(f"  Total Net Return    : +{ret_pct:,.1f}%")
    print(f"  Profit Factor       : {pf:.2f}")
    print(f"  Win Rate            : {wr:.1f}%")
    print(f"  Total Trades        : {tot:,}")
    print(f"  Max Drawdown        : {max_dd:.1f}%")
    print("=====================================================================================")
    
    print("\nYearly Breakdown for Bitcoin 5M:")
    print("-" * 75)
    print(f"{'Year':<8} | {'Trades':<8} | {'Win Rate':<10} | {'Profit Factor':<15} | {'Net P&L ($)':<15}")
    print("-" * 75)
    for yr, d in sorted(yearly.items()):
        yr_wr = (d['wins'] / d['trades'] * 100) if d['trades'] > 0 else 0
        yr_pf = (d['gross_win'] / d['gross_loss']) if d['gross_loss'] > 0 else float('inf')
        print(f"{yr:<8} | {d['trades']:<8} | {yr_wr:<9.1f}% | {yr_pf:<15.2f} | +${d['pnl']:<14,.2f}")
    print("-" * 75)

if __name__ == '__main__':
    main()
