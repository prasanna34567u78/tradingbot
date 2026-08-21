"""
Ultra-Fast Pure Numpy 5-Year Backtest: LuxAlgo 1H SMC + 5M PDE vs Single 5M PDE
================================================================================
"""

import sys
import time
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

def run_all_tests():
    years = 5
    tf_minutes = 5
    bars = years * 252 * (24 * 60 // tf_minutes)
    
    print(f"Generating 5 Years (362,880 5M bars) Gold Data...", flush=True)
    np.random.seed(42)
    dt = 1.0 / (252 * 288)
    theta = 1.2
    sigma = 0.16
    
    shocks = np.random.normal(0, np.sqrt(dt), bars)
    prices = np.zeros(bars)
    prices[0] = 1800.0
    drift_trend = np.linspace(1800.0, 2450.0, bars)
    
    for i in range(1, bars):
        prices[i] = prices[i-1] + theta * (drift_trend[i] - prices[i-1]) * dt + sigma * prices[i-1] * shocks[i]
        
    noise_hi = np.abs(np.random.normal(0, prices * 0.0008, bars))
    noise_lo = np.abs(np.random.normal(0, prices * 0.0008, bars))
    
    opens = np.roll(prices, 1)
    opens[0] = prices[0]
    highs = np.maximum(prices, opens) + noise_hi
    lows = np.minimum(prices, opens) - noise_lo
    closes = prices
    volume = np.random.randint(100, 2000, bars)
    
    start_dt = datetime(2021, 8, 1)
    timestamps = [start_dt + timedelta(minutes=i * tf_minutes) for i in range(bars)]
    
    df = pd.DataFrame({
        'time': timestamps, 'open': opens, 'high': highs, 'low': lows, 'close': closes, 'volume': volume
    })
    df.set_index('time', inplace=True)
    
    # Pre-calculate 1H HTF (resampled)
    df_1h = df[['open', 'high', 'low', 'close', 'volume']].resample('1h').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
    }).dropna()
    
    sw_hi_1h = df_1h['high'].rolling(50).max()
    sw_lo_1h = df_1h['low'].rolling(50).min()
    r_1h = sw_hi_1h - sw_lo_1h
    
    df_1h['htf_prem'] = sw_lo_1h + 0.618 * r_1h
    df_1h['htf_eq']   = sw_lo_1h + 0.500 * r_1h
    df_1h['htf_disc'] = sw_lo_1h + 0.382 * r_1h
    df_1h_shifted = df_1h.shift(1)  # No lookahead
    
    aligned_htf = df_1h_shifted[['htf_prem', 'htf_eq', 'htf_disc']].reindex(df.index, method='ffill')
    
    # 5M Indicators
    h = df['high'].values
    l = df['low'].values
    c = df['close'].values
    o = df['open'].values
    vol = df['volume'].values
    
    # 5M Rolling Swings
    sw_hi_5m = df['high'].rolling(50).max().values
    sw_lo_5m = df['low'].rolling(50).min().values
    vol_avg = df['volume'].rolling(20).mean().values
    
    # ATR
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    atr = pd.Series(tr).ewm(span=14, adjust=False).mean().values
    
    # RSI
    delta = pd.Series(c).diff()
    gain = delta.clip(lower=0).ewm(span=14, adjust=False).mean().values
    loss = (-delta.clip(upper=0)).ewm(span=14, adjust=False).mean().values.copy()
    loss[loss == 0] = 1e-9
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    htf_prem_arr = aligned_htf['htf_prem'].values
    htf_eq_arr   = aligned_htf['htf_eq'].values
    htf_disc_arr = aligned_htf['htf_disc'].values
    
    def simulate_fast(use_htf: bool, cooldown: int):
        bal = 2000.0
        peak = 2000.0
        max_dd = 0.0
        trades = []
        
        in_pos = False
        pos_type = 0 # 1=BUY, -1=SELL
        entry_p = sl = tp1 = tp2 = 0.0
        tp1_hit = False
        pos_size = 0.0
        last_sig = -cooldown
        
        for i in range(100, len(c)):
            curr_h = h[i]
            curr_l = l[i]
            curr_c = c[i]
            curr_o = o[i]
            curr_a = atr[i]
            
            if in_pos:
                hit_tp2 = False
                hit_sl = False
                
                if pos_type == 1:
                    if not tp1_hit and curr_h >= tp1:
                        tp1_hit = True
                        pnl_tp1 = (tp1 - entry_p) * (pos_size * 0.5) * 100.0
                        bal += pnl_tp1
                        sl = entry_p # Breakeven
                    if curr_h >= tp2:
                        hit_tp2 = True
                        rem = pos_size * 0.5 if tp1_hit else pos_size
                        bal += (tp2 - entry_p) * rem * 100.0
                    elif curr_l <= sl:
                        hit_sl = True
                        rem = pos_size * 0.5 if tp1_hit else pos_size
                        bal += (sl - entry_p) * rem * 100.0
                else:
                    if not tp1_hit and curr_l <= tp1:
                        tp1_hit = True
                        pnl_tp1 = (entry_p - tp1) * (pos_size * 0.5) * 100.0
                        bal += pnl_tp1
                        sl = entry_p
                    if curr_l <= tp2:
                        hit_tp2 = True
                        rem = pos_size * 0.5 if tp1_hit else pos_size
                        bal += (entry_p - tp2) * rem * 100.0
                    elif curr_h >= sl:
                        hit_sl = True
                        rem = pos_size * 0.5 if tp1_hit else pos_size
                        bal += (entry_p - sl) * rem * 100.0
                        
                if hit_tp2 or hit_sl:
                    pnl = bal - (trades[-1]['bal'] if trades else 2000.0)
                    trades.append({'pnl': pnl, 'bal': bal})
                    in_pos = False
                    
            if not in_pos and (i - last_sig >= cooldown):
                bar_bull = curr_c > curr_o
                bar_bear = curr_c < curr_o
                vol_ok = vol[i] >= 0.75 * vol_avg[i]
                r_val = rsi[i]
                
                if use_htf:
                    h_prem = htf_prem_arr[i]
                    h_eq = htf_eq_arr[i]
                    h_disc = htf_disc_arr[i]
                    
                    if np.isnan(h_prem) or np.isnan(h_disc):
                        continue
                        
                    # BUY
                    if curr_c <= h_disc and r_val <= 42.0 and bar_bull and vol_ok:
                        entry_p = curr_c
                        sl = sw_lo_5m[i] - 0.5 * curr_a
                        tp1 = h_eq
                        tp2 = h_prem
                        risk = entry_p - sl
                        if risk > 0 and (tp2 - entry_p) / risk >= 1.5:
                            pos_type = 1
                            tp1_hit = False
                            pos_size = max(0.01, min(round((bal * 0.01) / (risk * 100.0), 2), 5.0))
                            in_pos = True
                            last_sig = i
                            
                    # SELL
                    elif curr_c >= h_prem and r_val >= 58.0 and bar_bear and vol_ok:
                        entry_p = curr_c
                        sl = sw_hi_5m[i] + 0.5 * curr_a
                        tp1 = h_eq
                        tp2 = h_disc
                        risk = sl - entry_p
                        if risk > 0 and (entry_p - tp2) / risk >= 1.5:
                            pos_type = -1
                            tp1_hit = False
                            pos_size = max(0.01, min(round((bal * 0.01) / (risk * 100.0), 2), 5.0))
                            in_pos = True
                            last_sig = i
                else:
                    r5 = sw_hi_5m[i] - sw_lo_5m[i]
                    d5 = sw_lo_5m[i] + 0.382 * r5
                    p5 = sw_lo_5m[i] + 0.618 * r5
                    eq5 = sw_lo_5m[i] + 0.500 * r5
                    
                    if curr_c <= d5 and r_val <= 42.0 and bar_bull and vol_ok:
                        entry_p = curr_c
                        sl = sw_lo_5m[i] - 0.5 * curr_a
                        tp1 = eq5
                        tp2 = p5
                        risk = entry_p - sl
                        if risk > 0 and (tp2 - entry_p) / risk >= 1.5:
                            pos_type = 1
                            tp1_hit = False
                            pos_size = max(0.01, min(round((bal * 0.01) / (risk * 100.0), 2), 5.0))
                            in_pos = True
                            last_sig = i
                    elif curr_c >= p5 and r_val >= 58.0 and bar_bear and vol_ok:
                        entry_p = curr_c
                        sl = sw_hi_5m[i] + 0.5 * curr_a
                        tp1 = eq5
                        tp2 = d5
                        risk = sl - entry_p
                        if risk > 0 and (entry_p - tp2) / risk >= 1.5:
                            pos_type = -1
                            tp1_hit = False
                            pos_size = max(0.01, min(round((bal * 0.01) / (risk * 100.0), 2), 5.0))
                            in_pos = True
                            last_sig = i
                            
            if bal > peak:
                peak = bal
            dd = ((peak - bal) / peak) * 100.0
            if dd > max_dd:
                max_dd = dd
                
        return trades, bal, max_dd

    print("\nRunning Backtest Simulators...", flush=True)
    t0 = time.time()
    t_single, b_single, dd_single = simulate_fast(use_htf=False, cooldown=48)
    t_htf, b_htf, dd_htf = simulate_fast(use_htf=True, cooldown=24)
    print(f"Simulation completed in {time.time() - t0:.2f} seconds.\n", flush=True)

    def calc(trades, bal, dd, name):
        tot = len(trades)
        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] < 0]
        wr = len(wins) / tot * 100 if tot > 0 else 0
        gw = sum(t['pnl'] for t in wins)
        gl = abs(sum(t['pnl'] for t in losses))
        pf = gw / gl if gl > 0 else float('inf')
        ret = ((bal - 2000.0) / 2000.0) * 100
        return {
            'Strategy': name,
            'Total Trades': tot,
            'Win Rate': f"{wr:.1f}%",
            'Profit Factor': f"{pf:.2f}",
            'Total Return': f"+{ret:,.1f}%",
            'Final Balance': f"${bal:,.2f}",
            'Max Drawdown': f"{dd:.1f}%"
        }

    res = [
        calc(t_single, b_single, dd_single, "1. Single-TF (5M Only) PDE"),
        calc(t_htf, b_htf, dd_htf, "2. Multi-TF (1H LuxAlgo SMC + 5M PDE)")
    ]
    df_out = pd.DataFrame(res)
    print("=" * 95)
    print("                5-YEAR COMPREHENSIVE BACKTEST PERFORMANCE (362,880 5M BARS)")
    print("=" * 95)
    print(df_out.to_string(index=False))
    print("=" * 95)

if __name__ == '__main__':
    run_all_tests()
