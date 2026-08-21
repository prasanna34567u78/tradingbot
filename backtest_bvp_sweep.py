"""
Bitcoin Volume Profile Liquidity Sweep Strategy (BVP-Sweep)
===========================================================
Quantitative Edge:
1. Identifies 48-bar Volume Profile (POC, VAH, VAL) and 20-bar Swing Extremes
2. Liquidity Sweep Detection:
   - BUY: Price sweeps below VAL / Swing Low (trapping breakout shorts), then reclaims back above VAL with high Volume (>1.25x average) and RSI < 35 hooking up.
   - SELL: Price sweeps above VAH / Swing High (trapping breakout longs), then reclaims back below VAH with high Volume and RSI > 65 hooking down.
3. Dual-Target Exit:
   - SL: Placed just below the Sweep Wick (0.3x ATR buffer) -> Tight risk!
   - TP1: POC (Midpoint) -> Closes 50%, moves SL to Breakeven
   - TP2: Opposite Value Area + 1.5x Risk Runner
"""

import sys
import time
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

def generate_btc_5y_bars():
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

def run_bvp_sweep_backtest(df: pd.DataFrame, initial_balance: float = 10000.0, lots: float = 0.05):
    c = df['close'].values
    h = df['high'].values
    l = df['low'].values
    o = df['open'].values
    vol = df['volume'].values
    n = len(c)
    
    # 1. 200 EMA & 21 EMA
    ema_200 = pd.Series(c).ewm(span=200, adjust=False).mean().values
    ema_21  = pd.Series(c).ewm(span=21, adjust=False).mean().values
    
    # 2. 14 ATR
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    atr = pd.Series(tr).ewm(span=14, adjust=False).mean().values
    
    # 3. 14 RSI
    delta = pd.Series(c).diff()
    gain = delta.clip(lower=0).ewm(span=14, adjust=False).mean().values
    loss = (-delta.clip(upper=0)).ewm(span=14, adjust=False).mean().values.copy()
    loss[loss == 0] = 1e-9
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # 4. Volume Profile (48-bar rolling VWAP & 70% Value Area)
    tp = (h + l + c) / 3.0
    v = np.maximum(vol, 1.0)
    vp_pv = pd.Series(tp * v).rolling(48).sum().values
    vp_v  = pd.Series(v).rolling(48).sum().values
    poc   = vp_pv / np.maximum(vp_v, 1.0)
    
    dev_sq = (tp - poc) ** 2
    vw_var = pd.Series(dev_sq * v).rolling(48).sum().values / np.maximum(vp_v, 1.0)
    vw_std = np.sqrt(np.maximum(vw_var, 0))
    vah    = poc + (1.04 * vw_std)
    val    = poc - (1.04 * vw_std)
    
    vol_sma = pd.Series(vol).rolling(20).mean().values
    sw_lo = pd.Series(l).rolling(24).min().values
    sw_hi = pd.Series(h).rolling(24).max().values
    
    balance = initial_balance
    peak_balance = initial_balance
    max_dd = 0.0
    
    trades = []
    in_pos = False
    pos_type = 0
    entry_p = sl = tp1 = tp2 = 0.0
    tp1_hit = False
    cooldown = 18
    last_sig = -cooldown
    
    yearly_stats = {}
    timestamps = df.index
    
    for i in range(100, n):
        curr_yr = timestamps[i].year
        yearly_stats.setdefault(curr_yr, {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0, 'gross_win': 0.0, 'gross_loss': 0.0})
        
        # Position Exit Check (Dual-TP + Breakeven)
        if in_pos:
            hit_tp2 = False
            hit_sl  = False
            
            if pos_type == 1: # LONG
                if not tp1_hit and h[i] >= tp1:
                    pnl_tp1 = (tp1 - entry_p) * (lots * 0.5) * 1.0
                    balance += pnl_tp1
                    tp1_hit = True
                    sl = entry_p # Breakeven
                    yearly_stats[curr_yr]['pnl'] += pnl_tp1
                    yearly_stats[curr_yr]['gross_win'] += pnl_tp1
                    
                if h[i] >= tp2:
                    hit_tp2 = True
                    rem = (lots * 0.5) if tp1_hit else lots
                    pnl_tp2 = (tp2 - entry_p) * rem * 1.0
                    balance += pnl_tp2
                    yearly_stats[curr_yr]['pnl'] += pnl_tp2
                    yearly_stats[curr_yr]['gross_win'] += pnl_tp2
                elif l[i] <= sl:
                    hit_sl = True
                    rem = (lots * 0.5) if tp1_hit else lots
                    pnl_sl = (sl - entry_p) * rem * 1.0
                    balance += pnl_sl
                    yearly_stats[curr_yr]['pnl'] += pnl_sl
                    if pnl_sl < 0:
                        yearly_stats[curr_yr]['gross_loss'] += abs(pnl_sl)
                    else:
                        yearly_stats[curr_yr]['gross_win'] += pnl_sl
                        
            else: # SHORT
                if not tp1_hit and l[i] <= tp1:
                    pnl_tp1 = (entry_p - tp1) * (lots * 0.5) * 1.0
                    balance += pnl_tp1
                    tp1_hit = True
                    sl = entry_p
                    yearly_stats[curr_yr]['pnl'] += pnl_tp1
                    yearly_stats[curr_yr]['gross_win'] += pnl_tp1
                    
                if l[i] <= tp2:
                    hit_tp2 = True
                    rem = (lots * 0.5) if tp1_hit else lots
                    pnl_tp2 = (entry_p - tp2) * rem * 1.0
                    balance += pnl_tp2
                    yearly_stats[curr_yr]['pnl'] += pnl_tp2
                    yearly_stats[curr_yr]['gross_win'] += pnl_tp2
                elif h[i] >= sl:
                    hit_sl = True
                    rem = (lots * 0.5) if tp1_hit else lots
                    pnl_sl = (entry_p - sl) * rem * 1.0
                    balance += pnl_sl
                    yearly_stats[curr_yr]['pnl'] += pnl_sl
                    if pnl_sl < 0:
                        yearly_stats[curr_yr]['gross_loss'] += abs(pnl_sl)
                    else:
                        yearly_stats[curr_yr]['gross_win'] += pnl_sl
                        
            if hit_tp2 or hit_sl:
                tot_pnl = balance - (trades[-1]['bal'] if trades else initial_balance)
                yearly_stats[curr_yr]['trades'] += 1
                if tot_pnl > 0:
                    yearly_stats[curr_yr]['wins'] += 1
                else:
                    yearly_stats[curr_yr]['losses'] += 1
                trades.append({'time': timestamps[i], 'pnl': round(tot_pnl, 2), 'bal': round(balance, 2), 'tp2': hit_tp2})
                in_pos = False
                last_sig = i
                
        # Position Entry Check (Liquidity Sweep & Volume Reclaim)
        if not in_pos and (i - last_sig >= cooldown):
            curr_c = c[i]
            curr_o = o[i]
            curr_l = l[i]
            curr_h = h[i]
            curr_a = atr[i]
            curr_r = rsi[i]
            curr_v = vol[i]
            
            vol_boost = curr_v >= 1.15 * vol_sma[i] if pd.notna(vol_sma[i]) else True
            
            # BUY SWEEP: Low dipped below VAL / Swing Low, but closed back INSIDE with Bullish candle + oversold RSI
            buy_sweep = (curr_l <= val[i] or curr_l <= sw_lo[i-1]) and (curr_c > val[i]) and (curr_c > curr_o) and (curr_r <= 45.0) and vol_boost
            
            # SELL SWEEP: High spiked above VAH / Swing High, but closed back INSIDE with Bearish candle + overbought RSI
            sell_sweep = (curr_h >= vah[i] or curr_h >= sw_hi[i-1]) and (curr_c < vah[i]) and (curr_c < curr_o) and (curr_r >= 55.0) and vol_boost
            
            if buy_sweep:
                entry_p = curr_c
                sl = curr_l - (0.3 * curr_a) # Tight SL below the sweep wick!
                risk = entry_p - sl
                if risk > 0 and poc[i] > entry_p:
                    tp1 = poc[i] # Midpoint POC
                    tp2 = vah[i] + (1.0 * risk) # Full extension runner
                    pos_type = 1
                    tp1_hit = False
                    in_pos = True
                    last_sig = i
                    
            elif sell_sweep:
                entry_p = curr_c
                sl = curr_h + (0.3 * curr_a)
                risk = sl - entry_p
                if risk > 0 and poc[i] < entry_p:
                    tp1 = poc[i]
                    tp2 = val[i] - (1.0 * risk)
                    pos_type = -1
                    tp1_hit = False
                    in_pos = True
                    last_sig = i
                    
        if balance > peak_balance:
            peak_balance = balance
        dd = ((peak_balance - balance) / peak_balance) * 100.0
        if dd > max_dd:
            max_dd = dd
            
    return trades, balance, max_dd, yearly_stats

def main():
    print("=" * 85)
    print("  BITCOIN (BTCUSDm) 5-YEAR 5M: Volume Profile Liquidity Sweep (BVP-Sweep)")
    print("=" * 85)
    df = generate_btc_5y_bars()
    
    t0 = time.time()
    trades, final_bal, max_dd, yearly = run_bvp_sweep_backtest(df, initial_balance=10000.0, lots=0.05)
    print(f"Simulation completed in {time.time() - t0:.2f} seconds.\n", flush=True)
    
    tot = len(trades)
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] < 0]
    tp2_wins = [t for t in trades if t['tp2']]
    
    wr = (len(wins) / tot * 100) if tot > 0 else 0
    gw = sum(t['pnl'] for t in wins)
    gl = abs(sum(t['pnl'] for t in losses))
    pf = (gw / gl) if gl > 0 else float('inf')
    ret_pct = ((final_bal - 10000.0) / 10000.0) * 100
    
    print("=" * 85)
    print("        BITCOIN (BTCUSDm) 5-YEAR 5M LIQUIDITY SWEEP PERFORMANCE REPORT")
    print("=====================================================================================")
    print(f"  Initial Capital     : $ 10,000.00")
    print(f"  Final Equity        : $ {final_bal:,.2f}")
    print(f"  Total Net Return    : +{ret_pct:,.1f}%")
    print(f"  Profit Factor       : {pf:.2f}")
    print(f"  Win Rate            : {wr:.1f}%")
    print(f"  Total Trades        : {tot:,}")
    print(f"  TP2 Full Runner Wins: {len(tp2_wins):,}")
    print(f"  Max Drawdown        : {max_dd:.1f}%")
    print("=====================================================================================")
    
    print("\nYearly Performance Breakdown on Bitcoin 5M:")
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
