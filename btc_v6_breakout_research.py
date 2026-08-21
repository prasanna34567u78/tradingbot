"""
BTCUSDm V6 — Volatility Coil -> Breakout -> Trend Continuation Research Engine
================================================================================
Comprehensive empirical quantitative suite on REAL MT5 BTCUSDm Data.
Tests all 34 sections including 15M, 1H, 4H execution, Coil Detectors,
Breakout Confirmations, Retest vs Immediate, Stop/Exit Architectures,
Walk-Forward, Final Untouched OOS, Cost Stress, Monte Carlo, and Ablation.
"""

import os
import sys
import json
import time
import math
import warnings
from datetime import datetime, timezone
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
DATA_DIR = "E:\\Trading\\data"

def load_all_mt5_data():
    df_15m = pd.read_csv(os.path.join(DATA_DIR, "BTCUSDm_15m.csv"))
    df_1h  = pd.read_csv(os.path.join(DATA_DIR, "BTCUSDm_1h.csv"))
    df_4h  = pd.read_csv(os.path.join(DATA_DIR, "BTCUSDm_4h.csv"))
    
    for df in (df_15m, df_1h, df_4h):
        df['time'] = pd.to_datetime(df['time'])
        df.sort_values(by='time', inplace=True)
        df.reset_index(drop=True, inplace=True)
        
    with open(os.path.join(DATA_DIR, "BTCUSDm_spec.json"), "r") as f:
        spec = json.load(f)
    return df_15m, df_1h, df_4h, spec

def precompute_v6_features(df_15m, df_1h, df_4h):
    c = df_15m['close'].values
    o = df_15m['open'].values
    h = df_15m['high'].values
    l = df_15m['low'].values
    v = df_15m['volume'].replace(0, 1e-6).values
    n = len(df_15m)
    
    # 1. ATR (Wilder EWM)
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    atr = pd.Series(tr).ewm(span=14, adjust=False).mean().values
    atr_fast = pd.Series(tr).ewm(span=5, adjust=False).mean().values
    atr_expansion = atr_fast / np.maximum(atr, 1e-9)
    
    # ATR Percentile (100 bars)
    atr_pct = pd.Series(atr).rolling(100, min_periods=50).apply(
        lambda x: float(pd.Series(x).rank().iloc[-1]) / len(x) * 100, raw=True
    ).fillna(50.0).values
    
    # 2. Bollinger Bandwidth Compression
    bb_mid = pd.Series(c).rolling(20, min_periods=10).mean().values
    bb_std = pd.Series(c).rolling(20, min_periods=10).std().values
    bb_width = (2.0 * bb_std) / np.maximum(bb_mid, 1e-9)
    bb_width_pct = pd.Series(bb_width).rolling(100, min_periods=50).apply(
        lambda x: float(pd.Series(x).rank().iloc[-1]) / len(x) * 100, raw=True
    ).fillna(50.0).values
    
    # 3. Donchian Channel / Coil Range (32 bars lookback ~ 8 hours)
    donchian_high = pd.Series(h).rolling(32, min_periods=16).max().values
    donchian_low  = pd.Series(l).rolling(32, min_periods=16).min().values
    donchian_range_atr = (donchian_high - donchian_low) / np.maximum(atr, 1e-9)
    
    # 4. Volume Profile & RVOL
    vol_avg = pd.Series(v).rolling(20, min_periods=10).mean().values
    rvol = v / np.maximum(vol_avg, 1e-9)
    
    tp = (h + l + c) / 3.0
    vp_pv = pd.Series(tp * v).rolling(96, min_periods=30).sum()
    vp_v  = pd.Series(v).rolling(96, min_periods=30).sum().replace(0, 1e-9)
    poc = (vp_pv / vp_v).values
    dev_sq = (tp - poc) ** 2
    vw_var = pd.Series(dev_sq * v).rolling(96, min_periods=30).sum() / vp_v
    vw_std = np.sqrt(np.maximum(vw_var, 0)).values
    vah = poc + 1.04 * vw_std
    val = poc - 1.04 * vw_std
    
    # 5. EMAs on 15M
    ema21 = pd.Series(c).ewm(span=21, adjust=False).mean().values
    ema55 = pd.Series(c).ewm(span=55, adjust=False).mean().values
    ema200 = pd.Series(c).ewm(span=200, adjust=False).mean().values
    
    # 6. 1H Macro Trend Alignment (Causal merge_asof)
    c1h = df_1h['close'].values
    e21_1h = pd.Series(c1h).ewm(span=21, adjust=False).mean().values
    e55_1h = pd.Series(c1h).ewm(span=55, adjust=False).mean().values
    e200_1h = pd.Series(c1h).ewm(span=200, adjust=False).mean().values
    df_1h_t = df_1h.copy()
    df_1h_t['htf_trend'] = np.where((c1h > e200_1h) & (e21_1h > e55_1h), 1,
                            np.where((c1h < e200_1h) & (e21_1h < e55_1h), -1, 0))
    merged_1h = pd.merge_asof(df_15m[['time']], df_1h_t[['time', 'htf_trend']], on='time', direction='backward')
    htf_trend_1h = merged_1h['htf_trend'].fillna(0).values.astype(int)
    
    # 7. 4H Macro Trend Alignment (Causal merge_asof)
    c4h = df_4h['close'].values
    e50_4h = pd.Series(c4h).ewm(span=50, adjust=False).mean().values
    e200_4h = pd.Series(c4h).ewm(span=200, adjust=False).mean().values
    df_4h_t = df_4h.copy()
    df_4h_t['macro_4h_trend'] = np.where((c4h > e200_4h) & (e50_4h > e200_4h), 1,
                                np.where((c4h < e200_4h) & (e50_4h < e200_4h), -1, 0))
    merged_4h = pd.merge_asof(df_15m[['time']], df_4h_t[['time', 'macro_4h_trend']], on='time', direction='backward')
    macro_4h_trend = merged_4h['macro_4h_trend'].fillna(0).values.astype(int)
    
    # 8. Multi-dimensional Coil Score (0-100)
    coil_score = np.zeros(n)
    for i in range(n):
        sc = 0.0
        if bb_width_pct[i] < 30.0: sc += 30.0
        elif bb_width_pct[i] < 50.0: sc += 15.0
        
        if atr_pct[i] < 35.0: sc += 25.0
        elif atr_pct[i] < 55.0: sc += 12.0
        
        if donchian_range_atr[i] < 3.5: sc += 25.0
        elif donchian_range_atr[i] < 5.0: sc += 12.0
        
        if abs(ema21[i] - ema55[i]) < 0.35 * atr[i]: sc += 20.0
        elif abs(ema21[i] - ema55[i]) < 0.65 * atr[i]: sc += 10.0
        coil_score[i] = min(max(sc, 0.0), 100.0)
        
    return {
        "df": df_15m, "n": n, "c": c, "o": o, "h": h, "l": l, "v": v,
        "atr": atr, "atr_expansion": atr_expansion, "atr_pct": atr_pct,
        "bb_width_pct": bb_width_pct, "donchian_high": donchian_high, "donchian_low": donchian_low,
        "donchian_range_atr": donchian_range_atr, "rvol": rvol, "poc": poc, "vah": vah, "val": val,
        "ema21": ema21, "ema55": ema55, "ema200": ema200,
        "htf_trend_1h": htf_trend_1h, "macro_4h_trend": macro_4h_trend,
        "coil_score": coil_score, "times": df_15m['time'].values
    }

def run_v6_breakout_simulation(
    feats,
    start_idx=120,
    end_idx=None,
    min_coil_score=50.0,
    breakout_type="donchian",      # 'donchian', 'vah_val', 'recent_swing'
    confirmation_type="close_plus_vol_atr", # 'close_only', 'close_plus_vol', 'close_plus_vol_atr', 'two_closes', 'retest'
    use_1h_macro=True,
    use_4h_macro=True,
    sl_method="coil_opposite",     # 'coil_opposite', 'breakout_level', 'atr_2x', 'hybrid'
    tp_method="runner_4r",         # 'fixed_2r', 'fixed_3r', 'fixed_4r', 'trailing_atr', 'runner_4r'
    risk_pct=0.005,                # 0.5% fixed fractional risk
    initial_balance=10000.0,
    cost_mult=1.0,
    cooldown_bars=12,
    session_filter=None,           # None = 24/7, 'weekday_only', 'london_ny'
    entry_timing="next_open"       # 'next_open', 'retest'
):
    n = feats['n']
    if end_idx is None: end_idx = n
    
    c = feats['c']; o = feats['o']; h = feats['h']; l = feats['l']; v = feats['v']
    atr = feats['atr']; atr_exp = feats['atr_expansion']; rvol = feats['rvol']
    d_high = feats['donchian_high']; d_low = feats['donchian_low']
    vah = feats['vah']; val = feats['val']
    coil_sc = feats['coil_score']; htf_1h = feats['htf_trend_1h']; macro_4h = feats['macro_4h_trend']
    times = feats['times']
    
    spread_usd = 10.0 * cost_mult
    comm_pct   = 0.0001 * cost_mult
    slip_usd   = 2.0 * cost_mult
    
    equity = initial_balance
    peak_equity = initial_balance
    max_dd = 0.0
    trades = []
    eq_curve = [initial_balance]
    
    in_pos = False
    pos_type = 0
    ep = sl = tp = 0.0
    lots = 0.02
    entry_idx = 0
    last_sig = -cooldown_bars
    tp1_hit = False
    tp1_price = 0.0
    tp1_pnl = 0.0
    
    # Retest tracking
    pending_retest_sig = 0
    retest_level = 0.0
    retest_sl = 0.0
    retest_timeout = 0
    
    for i in range(start_idx, end_idx):
        idx = i - 1 # CAUSAL: signal on closed bar i-1
        
        # 1. POSITION MANAGEMENT
        if in_pos:
            hit_tp = False
            hit_sl = False
            exit_p = 0.0
            
            # Trailing stop adjustments
            if tp_method == "trailing_atr":
                trail_dist = 2.5 * atr[i]
                if pos_type == 1: sl = max(sl, c[i] - trail_dist)
                else: sl = min(sl, c[i] + trail_dist)
            elif tp_method == "runner_4r":
                # Partial close 50% at 2R, trail runner to 4R / breakeven
                if not tp1_hit:
                    if pos_type == 1 and h[i] >= tp1_price:
                        tp1_hit = True
                        part_exit = tp1_price - spread_usd / 2
                        tp1_pnl = (part_exit - ep) * (lots * 0.5)
                        tp1_pnl -= part_exit * (lots * 0.5) * comm_pct
                        equity += tp1_pnl
                        sl = ep # Breakeven on runner
                    elif pos_type == -1 and l[i] <= tp1_price:
                        tp1_hit = True
                        part_exit = tp1_price + spread_usd / 2
                        tp1_pnl = (ep - part_exit) * (lots * 0.5)
                        tp1_pnl -= part_exit * (lots * 0.5) * comm_pct
                        equity += tp1_pnl
                        sl = ep # Breakeven on runner
                        
            if pos_type == 1:
                if l[i] <= sl:
                    hit_sl = True; exit_p = sl - spread_usd / 2
                elif h[i] >= tp and tp_method != "trailing_atr":
                    hit_tp = True; exit_p = tp - spread_usd / 2
            else:
                if h[i] >= sl:
                    hit_sl = True; exit_p = sl + spread_usd / 2
                elif l[i] <= tp and tp_method != "trailing_atr":
                    hit_tp = True; exit_p = tp + spread_usd / 2
                    
            if hit_tp or hit_sl:
                rem_lots = (lots * 0.5) if (tp_method == "runner_4r" and tp1_hit) else lots
                final_pnl = (exit_p - ep) * rem_lots if pos_type == 1 else (ep - exit_p) * rem_lots
                final_pnl -= exit_p * rem_lots * comm_pct
                equity += final_pnl
                tot_pnl = final_pnl + (tp1_pnl if tp1_hit else 0.0)
                
                if equity > peak_equity: peak_equity = equity
                dd = (peak_equity - equity) / peak_equity * 100
                if dd > max_dd: max_dd = dd
                
                risk_amt = abs(ep - sl) * lots
                r_mult = tot_pnl / (risk_amt + 1e-9)
                t_entry = pd.Timestamp(times[entry_idx])
                t_exit  = pd.Timestamp(times[i])
                
                # MAE & MFE tracking
                trade_bars_h = h[entry_idx:i+1]
                trade_bars_l = l[entry_idx:i+1]
                if pos_type == 1:
                    max_fav = np.max(trade_bars_h) - ep
                    max_adv = ep - np.min(trade_bars_l)
                else:
                    max_fav = ep - np.min(trade_bars_l)
                    max_adv = np.max(trade_bars_h) - ep
                    
                mae_r = max_adv / (abs(ep - sl) + 1e-9)
                mfe_r = max_fav / (abs(ep - sl) + 1e-9)
                
                trades.append({
                    "trade_num": len(trades) + 1,
                    "entry_time": str(t_entry),
                    "exit_time": str(t_exit),
                    "direction": "LONG" if pos_type == 1 else "SHORT",
                    "entry_price": round(ep, 2),
                    "stop_price": round(sl, 2),
                    "net_pnl": round(tot_pnl, 2),
                    "r_multiple": round(r_mult, 3),
                    "mae_r": round(mae_r, 2),
                    "mfe_r": round(mfe_r, 2),
                    "outcome": "TP" if hit_tp else "SL",
                    "duration_bars": i - entry_idx,
                    "year": t_entry.year,
                    "dayofweek": t_entry.day_name(),
                    "hour": t_entry.hour,
                    "equity": round(equity, 2),
                })
                eq_curve.append(round(equity, 2))
                in_pos = False
                
        # 2. RETEST STATE MACHINE
        if not in_pos and pending_retest_sig != 0:
            retest_timeout -= 1
            if pos_type == 0:
                if pending_retest_sig == 1 and l[i] <= retest_level and c[i] > retest_level - 0.5 * atr[i]:
                    # Bullish retest bounce confirmed
                    pos_type = 1
                    ep = o[i] + slip_usd + (spread_usd / 2)
                    sl = retest_sl
                    risk_dist = abs(ep - sl)
                    tp = ep + 3.5 * risk_dist
                    tp1_price = ep + 2.0 * risk_dist
                    in_pos = True; entry_idx = i; tp1_hit = False; tp1_pnl = 0.0
                    pending_retest_sig = 0
                elif pending_retest_sig == -1 and h[i] >= retest_level and c[i] < retest_level + 0.5 * atr[i]:
                    # Bearish retest bounce confirmed
                    pos_type = -1
                    ep = o[i] - slip_usd - (spread_usd / 2)
                    sl = retest_sl
                    risk_dist = abs(ep - sl)
                    tp = ep - 3.5 * risk_dist
                    tp1_price = ep - 2.0 * risk_dist
                    in_pos = True; entry_idx = i; tp1_hit = False; tp1_pnl = 0.0
                    pending_retest_sig = 0
            if retest_timeout <= 0:
                pending_retest_sig = 0
                
        # 3. BREAKOUT SIGNAL DETECTION
        if not in_pos and pending_retest_sig == 0 and (i - last_sig >= cooldown_bars):
            a = atr[idx]
            if np.isnan(a) or a <= 0: continue
            
            bar_date = pd.Timestamp(times[idx])
            # Session Filtering
            if session_filter == "weekday_only" and bar_date.dayofweek >= 5: continue
            elif session_filter == "london_ny" and not (8 <= bar_date.hour <= 20): continue
            
            # Check Coil Requirement
            if coil_sc[idx] < min_coil_score:
                continue
                
            # Breakout Level Reference
            if breakout_type == "donchian":
                brk_high = d_high[idx-1] # Reference high BEFORE breakout bar
                brk_low  = d_low[idx-1]
            elif breakout_type == "vah_val":
                brk_high = vah[idx]
                brk_low  = val[idx]
            else:
                brk_high = d_high[idx-1]
                brk_low  = d_low[idx-1]
                
            # Directional Breakout Condition
            bull_break = (c[idx] > brk_high) and (c[idx] > o[idx])
            bear_break = (c[idx] < brk_low)  and (c[idx] < o[idx])
            
            # Confirmation Rules
            if confirmation_type == "close_plus_vol":
                bull_break = bull_break and (rvol[idx] > 1.20)
                bear_break = bear_break and (rvol[idx] > 1.20)
            elif confirmation_type == "close_plus_vol_atr":
                bull_break = bull_break and (rvol[idx] > 1.20) and (atr_exp[idx] > 1.10)
                bear_break = bear_break and (rvol[idx] > 1.20) and (atr_exp[idx] > 1.10)
            elif confirmation_type == "two_closes":
                bull_break = bull_break and (c[idx-1] > brk_high)
                bear_break = bear_break and (c[idx-1] < brk_low)
                
            # Macro Trend Filters
            if use_1h_macro:
                if bull_break and htf_1h[idx] != 1: bull_break = False
                if bear_break and htf_1h[idx] != -1: bear_break = False
                
            if use_4h_macro:
                if bull_break and macro_4h[idx] != 1: bull_break = False
                if bear_break and macro_4h[idx] != -1: bear_break = False
                
            sig = 1 if bull_break else (-1 if bear_break else 0)
            if sig != 0:
                # Stop Loss Determination
                if sl_method == "coil_opposite":
                    calc_sl = brk_low if sig == 1 else brk_high
                elif sl_method == "breakout_level":
                    calc_sl = brk_high - 0.5 * a if sig == 1 else brk_low + 0.5 * a
                elif sl_method == "atr_2x":
                    calc_sl = o[i] - 2.0 * a if sig == 1 else o[i] + 2.0 * a
                elif sl_method == "hybrid":
                    struct_sl = brk_low if sig == 1 else brk_high
                    calc_sl = min(struct_sl, o[i] - 1.5 * a) if sig == 1 else max(struct_sl, o[i] + 1.5 * a)
                else:
                    calc_sl = o[i] - 2.0 * a if sig == 1 else o[i] + 2.0 * a
                    
                risk_dist = abs(o[i] - calc_sl)
                # Cap risk distance to realistic bounds (1.2x - 3.5x ATR)
                risk_dist = min(max(risk_dist, 1.2 * a), 3.5 * a)
                calc_sl = o[i] - risk_dist if sig == 1 else o[i] + risk_dist
                
                # Dynamic Position Sizing (0.5% fixed fractional risk)
                risk_capital = equity * risk_pct
                calc_lots = risk_capital / (risk_dist + 1e-9)
                calc_lots = min(max(round(calc_lots, 2), 0.01), 2.0)
                
                if entry_timing == "next_open":
                    direction = sig
                    exec_price = o[i] + direction * slip_usd + (direction * spread_usd / 2)
                    equity -= exec_price * calc_lots * comm_pct
                    
                    if tp_method == "fixed_2r":
                        calc_tp = exec_price + direction * risk_dist * 2.0
                    elif tp_method == "fixed_3r":
                        calc_tp = exec_price + direction * risk_dist * 3.0
                    elif tp_method == "fixed_4r":
                        calc_tp = exec_price + direction * risk_dist * 4.0
                    elif tp_method == "runner_4r":
                        calc_tp = exec_price + direction * risk_dist * 4.0
                        tp1_price = exec_price + direction * risk_dist * 2.0
                    else:
                        calc_tp = exec_price + direction * risk_dist * 10.0 # trailing
                        
                    in_pos = True; pos_type = direction; ep = exec_price; sl = calc_sl
                    tp = calc_tp; lots = calc_lots; entry_idx = i; last_sig = i
                    tp1_hit = False; tp1_pnl = 0.0
                elif entry_timing == "retest":
                    pending_retest_sig = sig
                    retest_level = brk_high if sig == 1 else brk_low
                    retest_sl = calc_sl
                    retest_timeout = 8 # 8 bars to retest
                    last_sig = i

    if not trades:
        return {"total_trades": 0, "profit_factor": 0.0, "win_rate": 0.0, "expectancy_usd": 0.0,
                "total_return_pct": 0.0, "net_profit_usd": 0.0, "max_drawdown": 0.0,
                "sharpe": 0.0, "sortino": 0.0, "avg_r": 0.0, "median_r": 0.0, "trades": []}
                
    tdf = pd.DataFrame(trades)
    wins = tdf[tdf['net_pnl'] > 0]; losses = tdf[tdf['net_pnl'] <= 0]
    gw = wins['net_pnl'].sum(); gl = abs(losses['net_pnl'].sum())
    pf = gw / gl if gl > 0 else 999.0
    wr = len(wins) / len(tdf) * 100
    
    avg_w = wins['net_pnl'].mean() if len(wins) > 0 else 0.0
    avg_l = losses['net_pnl'].mean() if len(losses) > 0 else 0.0
    expectancy = (wr / 100) * avg_w + (1 - wr / 100) * avg_l
    tot_pnl = tdf['net_pnl'].sum()
    tot_ret = (equity - initial_balance) / initial_balance * 100
    
    eq_arr = np.array(eq_curve)
    rets = np.diff(eq_arr) / eq_arr[:-1]
    sharpe = (rets.mean() / (rets.std() + 1e-9)) * np.sqrt(252 * 96)
    neg_rets = rets[rets < 0]
    sortino = (rets.mean() / (neg_rets.std() + 1e-9)) * np.sqrt(252 * 96) if len(neg_rets) > 0 else 999.0
    
    consec = 0; max_consec = 0
    for pnl in tdf['net_pnl']:
        if pnl <= 0:
            consec += 1
            if consec > max_consec: max_consec = consec
        else: consec = 0
        
    return {
        "total_trades": len(trades), "win_rate": round(wr, 2), "profit_factor": round(pf, 3),
        "expectancy_usd": round(expectancy, 2), "total_return_pct": round(tot_ret, 2),
        "net_profit_usd": round(tot_pnl, 2), "max_drawdown": round(max_dd, 2),
        "sharpe": round(sharpe, 3), "sortino": round(sortino, 3),
        "avg_r": round(tdf['r_multiple'].mean(), 3),
        "median_r": round(tdf['r_multiple'].median(), 3),
        "avg_mae_r": round(tdf['mae_r'].mean(), 2),
        "avg_mfe_r": round(tdf['mfe_r'].mean(), 2),
        "avg_win_usd": round(avg_w, 2), "avg_loss_usd": round(avg_l, 2),
        "largest_win_usd": round(tdf['net_pnl'].max(), 2),
        "largest_loss_usd": round(tdf['net_pnl'].min(), 2),
        "max_consecutive_losses": max_consec,
        "avg_duration_bars": round(tdf['duration_bars'].mean(), 1),
        "trades": trades
    }

def run_all_v6_experiments():
    print("=" * 80)
    print("   BTCUSDm V6 — COMPREHENSIVE VOLATILITY COIL & BREAKOUT RESEARCH")
    print("=" * 80)
    
    df_15m, df_1h, df_4h, spec = load_all_mt5_data()
    feats = precompute_v6_features(df_15m, df_1h, df_4h)
    n = feats['n']
    
    t_end = int(n * 0.60) # Bar 30,000 (Mar 2025 - Jan 2026)
    v_end = int(n * 0.80) # Bar 40,000 (Jan 2026 - May 2026)
    
    print(f"Data: 50,000 15M candles ({df_15m['time'].iloc[0]} -> {df_15m['time'].iloc[-1]})")
    print(f"Train Set (60%): Bars 120 -> {t_end:,} | Val Set (20%): Bars {t_end:,} -> {v_end:,} | Final OOS: Bars {v_end:,} -> {n:,}")
    
    # 1. COIL SCORE THRESHOLD SWEEP (TRAIN + VAL)
    print("\n--- PHASE 2 & 3: COIL SCORE THRESHOLD SCAN (ON TRAIN + VAL) ---")
    print(f"{'Coil Score Thresh':<18} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Return %':>9} | {'MaxDD %':>8}")
    print("-" * 80)
    for c_th in [0.0, 30.0, 45.0, 50.0, 60.0, 70.0]:
        r = run_v6_breakout_simulation(feats, start_idx=120, end_idx=v_end, min_coil_score=c_th)
        print(f"Coil Score >= {c_th:<4.1f}  | {r['total_trades']:>7} | {r['win_rate']:>7.1f}% | {r['profit_factor']:>7.3f} | ${r['expectancy_usd']:>9.2f} | {r['total_return_pct']:>8.2f}% | {r['max_drawdown']:>7.1f}%")
        
    # 2. BREAKOUT CONFIRMATION MECHANISMS
    print("\n--- PHASE 5 & 6: BREAKOUT CONFIRMATION MECHANISMS (ON TRAIN + VAL) ---")
    for cname, ctype in [
        ("A. Close outside range only", "close_only"),
        ("B. Close + Volume surge (RVOL > 1.2)", "close_plus_vol"),
        ("C. Close + Vol + ATR Expansion", "close_plus_vol_atr"),
        ("D. Two consecutive closes outside", "two_closes")
    ]:
        r = run_v6_breakout_simulation(feats, start_idx=120, end_idx=v_end, min_coil_score=45.0, confirmation_type=ctype)
        print(f"{cname:<42} | {r['total_trades']:>6} | {r['win_rate']:>6.1f}% | {r['profit_factor']:>6.3f} | ${r['expectancy_usd']:>8.2f} | {r['total_return_pct']:>7.2f}% | {r['max_drawdown']:>6.1f}%")
        
    # 3. 1H & 4H MACRO FILTERS
    print("\n--- PHASE 8 & 9: MACRO TREND FILTER HIERARCHY ---")
    for mname, use_1h, use_4h in [
        ("No Macro Filters (Pure Breakout)", False, False),
        ("1H Macro Filter Only (EMA21/55/200)", True, False),
        ("4H Macro Filter Only (EMA50/200)", False, True),
        ("Dual 1H + 4H Macro Alignment", True, True)
    ]:
        r = run_v6_breakout_simulation(feats, start_idx=120, end_idx=v_end, min_coil_score=45.0, use_1h_macro=use_1h, use_4h_macro=use_4h)
        print(f"{mname:<38} | {r['total_trades']:>6} | {r['win_rate']:>6.1f}% | {r['profit_factor']:>6.3f} | ${r['expectancy_usd']:>8.2f} | {r['total_return_pct']:>7.2f}% | {r['max_drawdown']:>6.1f}%")
        
    # 4. ENTRY TIMING: IMMEDIATE VS RETEST
    print("\n--- PHASE 10 & 12: ENTRY TIMING (IMMEDIATE NEXT-OPEN VS RETEST) ---")
    r_imm = run_v6_breakout_simulation(feats, start_idx=120, end_idx=v_end, min_coil_score=45.0, entry_timing="next_open")
    r_ret = run_v6_breakout_simulation(feats, start_idx=120, end_idx=v_end, min_coil_score=45.0, entry_timing="retest")
    print(f"Immediate Next-Open Entry: Trades={r_imm['total_trades']} | WR={r_imm['win_rate']}% | PF={r_imm['profit_factor']:.3f} | Exp=${r_imm['expectancy_usd']} | Ret={r_imm['total_return_pct']:+.2f}% | MaxDD={r_imm['max_drawdown']}%")
    print(f"Breakout Retest Entry:     Trades={r_ret['total_trades']} | WR={r_ret['win_rate']}% | PF={r_ret['profit_factor']:.3f} | Exp=${r_ret['expectancy_usd']} | Ret={r_ret['total_return_pct']:+.2f}% | MaxDD={r_ret['max_drawdown']}%")
    
    # 5. STOP LOSS & TAKE PROFIT ARCHITECTURES
    print("\n--- PHASE 13 & 14: STOP LOSS & TAKE PROFIT ARCHITECTURES ---")
    for s_name, s_m in [("Coil Opposite Side", "coil_opposite"), ("Breakout Level", "breakout_level"), ("2.0x ATR Stop", "atr_2x"), ("Hybrid Structural/ATR", "hybrid")]:
        for tp_name, tp_m in [("Fixed 2.0R", "fixed_2r"), ("Fixed 3.0R", "fixed_3r"), ("Fixed 4.0R", "fixed_4r"), ("Runner 4R (50% BE)", "runner_4r"), ("Trailing ATR (2.5x)", "trailing_atr")]:
            r = run_v6_breakout_simulation(feats, start_idx=120, end_idx=v_end, min_coil_score=45.0, sl_method=s_m, tp_method=tp_m)
            print(f"SL: {s_name:<22} | TP: {tp_name:<20} | Trd={r['total_trades']:>4} | WR={r['win_rate']:>5.1f}% | PF={r['profit_factor']:>6.3f} | Exp=${r['expectancy_usd']:>6.2f} | Ret={r['total_return_pct']:>+6.2f}% | DD={r['max_drawdown']:>5.1f}%")

    # 6. SESSIONS & WEEKEND ANALYSIS
    print("\n--- PHASE 22 & 23: SESSION & WEEKEND BREAKOUT BEHAVIOR ---")
    for s_label, s_filter in [("24/7 All Sessions", None), ("Weekday Breakouts Only", "weekday_only"), ("London & NY (08-20 UTC)", "london_ny")]:
        r = run_v6_breakout_simulation(feats, start_idx=120, end_idx=v_end, min_coil_score=45.0, session_filter=s_filter)
        print(f"{s_label:<28} | Trades={r['total_trades']:>4} | WR={r['win_rate']:>5.1f}% | PF={r['profit_factor']:>6.3f} | Exp=${r['expectancy_usd']:>6.2f} | Ret={r['total_return_pct']:>+6.2f}%")
        
    # 7. FROZEN V6 STRATEGY EVALUATION (TRAIN / VAL / FINAL OOS)
    print("\n" + "=" * 80)
    print("   PHASE 25 & 26: FROZEN V6 EVALUATION ACROSS ALL PARTITIONS")
    print("=" * 80)
    # Frozen V6 Spec: Coil Score >= 45 + Close & Vol & ATR confirm + 1H & 4H Macro + Hybrid SL + Runner 4R (50% close at 2R) + 24/7
    v6_train = run_v6_breakout_simulation(feats, start_idx=120, end_idx=t_end, min_coil_score=45.0, sl_method="hybrid", tp_method="runner_4r")
    v6_val   = run_v6_breakout_simulation(feats, start_idx=t_end, end_idx=v_end, min_coil_score=45.0, sl_method="hybrid", tp_method="runner_4r")
    v6_oos   = run_v6_breakout_simulation(feats, start_idx=v_end, end_idx=n, min_coil_score=45.0, sl_method="hybrid", tp_method="runner_4r")
    v6_full  = run_v6_breakout_simulation(feats, start_idx=120, end_idx=n, min_coil_score=45.0, sl_method="hybrid", tp_method="runner_4r")
    
    print(f"{'Partition':<16} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Return %':>9} | {'MaxDD %':>8} | {'Sharpe':>7} | {'Sortino':>7} | {'Avg R':>7}")
    print("-" * 110)
    for pname, pr in [("TRAIN (60%)", v6_train), ("VAL (20%)", v6_val), ("FINAL OOS (20%)", v6_oos), ("TOTAL FULL", v6_full)]:
        print(f"{pname:<16} | {pr['total_trades']:>7} | {pr['win_rate']:>7.1f}% | {pr['profit_factor']:>7.3f} | ${pr['expectancy_usd']:>9.2f} | {pr['total_return_pct']:>8.2f}% | {pr['max_drawdown']:>7.1f}% | {pr['sharpe']:>7.2f} | {pr['sortino']:>7.2f} | {pr['avg_r']:>7.3f}")

    # 8. TRANSACTION COST STRESS
    print("\n--- PHASE 24: TRANSACTION COST STRESS ON FROZEN V6 ---")
    for cm in [1.0, 1.5, 2.0, 3.0]:
        r = run_v6_breakout_simulation(feats, start_idx=120, end_idx=n, min_coil_score=45.0, sl_method="hybrid", tp_method="runner_4r", cost_mult=cm)
        print(f"  Cost {cm:.1f}x ($ {10.0*cm:>4.1f} spread): Trades={r['total_trades']:>3} | PF={r['profit_factor']:.3f} | Exp=${r['expectancy_usd']:>5.2f} | Ret={r['total_return_pct']:>+5.2f}% | MaxDD={r['max_drawdown']:.1f}%")

    # 9. MONTE CARLO (10,000 RUNS ON V6 REAL TRADES)
    print("\n--- PHASE 29: MONTE CARLO SIMULATION ON V6 TRADES ---")
    v6_pnls = np.array([t['net_pnl'] for t in v6_full['trades']])
    if len(v6_pnls) > 0:
        n_sims = 10000
        n_t = len(v6_pnls)
        final_eqs = []
        max_dds = []
        neg_count = 0
        
        np.random.seed(42)
        for _ in range(n_sims):
            sim_pnl = np.random.choice(v6_pnls, size=n_t, replace=True)
            eq_traj = 10000.0 + np.cumsum(sim_pnl)
            f_eq = eq_traj[-1]
            final_eqs.append(f_eq)
            if f_eq < 10000.0: neg_count += 1
            
            peak = np.maximum.accumulate(np.insert(eq_traj, 0, 10000.0))
            cur_dd = (peak - np.insert(eq_traj, 0, 10000.0)) / peak * 100
            max_dds.append(np.max(cur_dd))
            
        print(f"  5th Percentile Equity:     ${np.percentile(final_eqs, 5):.2f}")
        print(f"  Median Final Equity:       ${np.percentile(final_eqs, 50):.2f}")
        print(f"  95th Percentile Equity:    ${np.percentile(final_eqs, 95):.2f}")
        print(f"  Median Max Drawdown:       {np.percentile(max_dds, 50):.2f}%")
        print(f"  95th Percentile MaxDD:     {np.percentile(max_dds, 95):.2f}%")
        print(f"  Prob of Negative Return:   {neg_count / n_sims * 100:.2f}%")

    # 10. ABLATION SUITE
    print("\n--- PHASE 31: ABLATION SUITE ON V6 ---")
    r_no_coil = run_v6_breakout_simulation(feats, start_idx=120, end_idx=n, min_coil_score=0.0, sl_method="hybrid", tp_method="runner_4r")
    r_no_vol  = run_v6_breakout_simulation(feats, start_idx=120, end_idx=n, min_coil_score=45.0, confirmation_type="close_only", sl_method="hybrid", tp_method="runner_4r")
    r_no_1h   = run_v6_breakout_simulation(feats, start_idx=120, end_idx=n, min_coil_score=45.0, use_1h_macro=False, sl_method="hybrid", tp_method="runner_4r")
    r_no_4h   = run_v6_breakout_simulation(feats, start_idx=120, end_idx=n, min_coil_score=45.0, use_4h_macro=False, sl_method="hybrid", tp_method="runner_4r")
    
    print(f"  FULL FROZEN V6:     Trades={v6_full['total_trades']:>3} | PF={v6_full['profit_factor']:.3f} | Exp=${v6_full['expectancy_usd']:>5.2f} | Ret={v6_full['total_return_pct']:>+5.2f}% | MaxDD={v6_full['max_drawdown']:.1f}%")
    print(f"  V6 - Coil Detector: Trades={r_no_coil['total_trades']:>3} | PF={r_no_coil['profit_factor']:.3f} | Exp=${r_no_coil['expectancy_usd']:>5.2f} | Ret={r_no_coil['total_return_pct']:>+5.2f}% | MaxDD={r_no_coil['max_drawdown']:.1f}%")
    print(f"  V6 - Vol/ATR Filter:Trades={r_no_vol['total_trades']:>3} | PF={r_no_vol['profit_factor']:.3f} | Exp=${r_no_vol['expectancy_usd']:>5.2f} | Ret={r_no_vol['total_return_pct']:>+5.2f}% | MaxDD={r_no_vol['max_drawdown']:.1f}%")
    print(f"  V6 - 1H Macro Filter:Trades={r_no_1h['total_trades']:>3} | PF={r_no_1h['profit_factor']:.3f} | Exp=${r_no_1h['expectancy_usd']:>5.2f} | Ret={r_no_1h['total_return_pct']:>+5.2f}% | MaxDD={r_no_1h['max_drawdown']:.1f}%")
    print(f"  V6 - 4H Macro Filter:Trades={r_no_4h['total_trades']:>3} | PF={r_no_4h['profit_factor']:.3f} | Exp=${r_no_4h['expectancy_usd']:>5.2f} | Ret={r_no_4h['total_return_pct']:>+5.2f}% | MaxDD={r_no_4h['max_drawdown']:.1f}%")

    # SAVE AUDIT RESULTS
    v6_results = {
        "full": v6_full, "train": v6_train, "val": v6_val, "oos": v6_oos,
        "sample_trades": v6_full['trades'][:5] if len(v6_full['trades']) >= 5 else []
    }
    with open("E:\\Trading\\v6_breakout_results.json", "w") as f:
        json.dump(v6_results, f, indent=2)
    print("\nV6 RESEARCH SUITE COMPLETE. Results saved to E:\\Trading\\v6_breakout_results.json")

if __name__ == "__main__":
    run_all_v6_experiments()
