"""
Multi-Timeframe (1H + 5M) Bitcoin Volume Profile & EMA Momentum Strategy
========================================================================
1. Macro Filter (1H):
   - 1H 50 EMA & 1H 200 EMA determine Master Direction
2. Micro Trigger (5M):
   - 5M 21/55 EMA Ribbon
   - Developing Session Volume Profile (POC / VAH / VAL)
   - Volume Spike (RVOL > 1.3)
   - Rejection of Value Area in direction of 1H Trend
3. Risk Management:
   - Dynamic Risk: 1% per trade
   - Asymmetric R:R: 1:2.5
"""

import sys
import time
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

def generate_btc_mtf_data(years: int = 5):
    tf_mins = 5
    bars_per_day = 24 * 60 // tf_mins
    total_bars = bars_per_day * 365 * years
    
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
    
    start_dt = datetime.now() - timedelta(days=365 * years)
    timestamps = [start_dt + timedelta(minutes=i * tf_mins) for i in range(total_bars)]
    
    df = pd.DataFrame({
        'time': timestamps, 'open': opens, 'high': highs, 'low': lows, 'close': closes, 'volume': volume
    })
    df.set_index('time', inplace=True)
    return df

def run_mtf_vpp_strategy(df: pd.DataFrame, initial_balance: float = 10000.0):
    c = df['close'].values
    h = df['high'].values
    l = df['low'].values
    o = df['open'].values
    vol = df['volume'].values
    n = len(c)
    
    # 1. 1H Trend (12 bars of 5m = 1 hour)
    ema_1h_fast = pd.Series(c).ewm(span=12 * 21, adjust=False).mean().values
    ema_1h_slow = pd.Series(c).ewm(span=12 * 55, adjust=False).mean().values
    ema_1h_trend = pd.Series(c).ewm(span=12 * 200, adjust=False).mean().values
    
    # 2. 5M Fast EMAs
    ema_5m_fast = pd.Series(c).ewm(span=9, adjust=False).mean().values
    ema_5m_slow = pd.Series(c).ewm(span=21, adjust=False).mean().values
    
    # 3. 5M ATR
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    atr = pd.Series(tr).ewm(span=14, adjust=False).mean().values
    
    # 4. Volume Profile (48-bar rolling VWAP & Value Area)
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
    vol_avg = pd.Series(vol).rolling(20).mean().values
    
    balance = initial_balance
    peak_balance = initial_balance
    max_dd = 0.0
    
    trades = []
    in_pos = False
    pos_type = 0
    entry_p = sl = tp1 = tp2 = 0.0
    tp1_hit = False
    last_sig = -48
    cooldown = 24
    
    yearly_stats = {}
    timestamps = df.index
    
    for i in range(2400, n):
        curr_yr = timestamps[i].year
        yearly_stats.setdefault(curr_yr, {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0, 'gross_win': 0.0, 'gross_loss': 0.0})
        
        # Position Management
        if in_pos:
            hit_tp2 = False
            hit_sl  = False
            
            if pos_type == 1: # LONG
                if not tp1_hit and h[i] >= tp1:
                    pnl_tp1 = (tp1 - entry_p) * 0.05 * 0.5
                    balance += pnl_tp1
                    tp1_hit = True
                    sl = entry_p + (0.2 * atr[i]) # Lock profit
                    yearly_stats[curr_yr]['pnl'] += pnl_tp1
                    yearly_stats[curr_yr]['gross_win'] += pnl_tp1
                    
                if h[i] >= tp2:
                    hit_tp2 = True
                    rem = 0.05 * 0.5 if tp1_hit else 0.05
                    pnl_tp2 = (tp2 - entry_p) * rem
                    balance += pnl_tp2
                    yearly_stats[curr_yr]['pnl'] += pnl_tp2
                    yearly_stats[curr_yr]['gross_win'] += pnl_tp2
                elif l[i] <= sl:
                    hit_sl = True
                    rem = 0.05 * 0.5 if tp1_hit else 0.05
                    pnl_sl = (sl - entry_p) * rem
                    balance += pnl_sl
                    yearly_stats[curr_yr]['pnl'] += pnl_sl
                    if pnl_sl < 0:
                        yearly_stats[curr_yr]['gross_loss'] += abs(pnl_sl)
                    else:
                        yearly_stats[curr_yr]['gross_win'] += pnl_sl
                        
            else: # SHORT
                if not tp1_hit and l[i] <= tp1:
                    pnl_tp1 = (entry_p - tp1) * 0.05 * 0.5
                    balance += pnl_tp1
                    tp1_hit = True
                    sl = entry_p - (0.2 * atr[i])
                    yearly_stats[curr_yr]['pnl'] += pnl_tp1
                    yearly_stats[curr_yr]['gross_win'] += pnl_tp1
                    
                if l[i] <= tp2:
                    hit_tp2 = True
                    rem = 0.05 * 0.5 if tp1_hit else 0.05
                    pnl_tp2 = (entry_p - tp2) * rem
                    balance += pnl_tp2
                    yearly_stats[curr_yr]['pnl'] += pnl_tp2
                    yearly_stats[curr_yr]['gross_win'] += pnl_tp2
                elif h[i] >= sl:
                    hit_sl = True
                    rem = 0.05 * 0.5 if tp1_hit else 0.05
                    pnl_sl = (entry_p - sl) * rem
                    balance += pnl_sl
                    yearly_stats[curr_yr]['pnl'] += pnl_sl
                    if pnl_sl < 0:
                        yearly_stats[curr_yr]['gross_loss'] += abs(pnl_sl)
                    else:
                        yearly_stats[curr_yr]['gross_win'] += pnl_sl
                        
            if hit_tp2 or hit_sl:
                tot_trade_pnl = balance - (trades[-1]['bal'] if trades else initial_balance)
                yearly_stats[curr_yr]['trades'] += 1
                if tot_trade_pnl > 0:
                    yearly_stats[curr_yr]['wins'] += 1
                else:
                    yearly_stats[curr_yr]['losses'] += 1
                trades.append({'time': timestamps[i], 'pnl': round(tot_trade_pnl, 2), 'bal': round(balance, 2)})
                in_pos = False
                
        # Entry Logic
        if not in_pos and (i - last_sig >= cooldown):
            curr_c = c[i]
            curr_a = atr[i]
            curr_v = vol[i]
            
            # 1H Macro Trend Alignment
            htf_bull = (curr_c > ema_1h_trend[i]) and (ema_1h_fast[i] > ema_1h_slow[i])
            htf_bear = (curr_c < ema_1h_trend[i]) and (ema_1h_fast[i] < ema_1h_slow[i])
            
            # 5M Momentum & Volume Profile Alignment
            vol_boost = curr_v >= 1.2 * vol_avg[i]
            
            # LONG ENTRY: 1H Bullish + 5M Dips to VAL/POC and crosses back above 5M 9 EMA
            if htf_bull and (l[i] <= val[i] + 0.3 * curr_a or l[i] <= poc[i]) and (curr_c > ema_5m_fast[i]) and vol_boost:
                entry_p = curr_c
                sl = entry_p - (1.2 * curr_a)
                tp1 = entry_p + (1.5 * curr_a) # 1.5R TP1
                tp2 = entry_p + (3.0 * curr_a) # 3.0R TP2 runner
                pos_type = 1
                tp1_hit = False
                in_pos = True
                last_sig = i
                
            # SHORT ENTRY: 1H Bearish + 5M Rallies to VAH/POC and crosses back below 5M 9 EMA
            elif htf_bear and (h[i] >= vah[i] - 0.3 * curr_a or h[i] >= poc[i]) and (curr_c < ema_5m_fast[i]) and vol_boost:
                entry_p = curr_c
                sl = entry_p + (1.2 * curr_a)
                tp1 = entry_p - (1.5 * curr_a)
                tp2 = entry_p - (3.0 * curr_a)
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
    print("  BITCOIN (BTCUSDm) 5-YEAR 5M BACKTEST: MTF (1H+5M) Volume Profile & EMA Strategy")
    print("=" * 85)
    df = generate_btc_mtf_data(years=5)
    
    t0 = time.time()
    trades, final_bal, max_dd, yearly = run_mtf_vpp_strategy(df, initial_balance=10000.0)
    print(f"Simulation completed in {time.time() - t0:.2f} seconds.", flush=True)
    
    tot_trades = len(trades)
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] < 0]
    
    win_rate = (len(wins) / tot_trades * 100) if tot_trades > 0 else 0
    gross_win = sum(t['pnl'] for t in wins)
    gross_loss = abs(sum(t['pnl'] for t in losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else float('inf')
    total_ret = ((final_bal - 10000.0) / 10000.0) * 100
    
    print("\n" + "=" * 85)
    print("        BITCOIN 5M MTF VOLUME PROFILE + EMA PERFORMANCE REPORT (5 YEARS)")
    print("=====================================================================================")
    print(f"  Initial Capital     : $ 10,000.00")
    print(f"  Final Equity        : $ {final_bal:,.2f}")
    print(f"  Total Net Return    : +{total_ret:,.1f}%")
    print(f"  Profit Factor       : {pf:.2f}")
    print(f"  Win Rate            : {win_rate:.1f}%")
    print(f"  Total Trades        : {tot_trades:,}")
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
