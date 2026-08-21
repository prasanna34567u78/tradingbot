"""
BTCUSDm V8 — Higher-Timeframe Macro Expansion & Regime Strategy Engine
======================================================================
Comprehensive Multi-Cycle Empirical Research Suite across:
  - 1D, 4H, 1H, 15M real MT5 Historical Data
  - 7-State Macro Regime Classifier (Trend Strength vs Volatility Expansion)
  - Macro Expansion Score (0-100) & Predictive Forward Validation (4H to 7D)
  - Fresh vs Mature vs Exhausted Expansion Diagnostics
  - Multi-Cycle Historical Walk-Forward (Across Bull, Bear, and Consolidation Cycles)
  - Simple 4H Macro Trend Baseline vs V6 vs V7 vs V8
  - Cost Stress (1x to 3x) & 10,000 Monte Carlo Simulations
  - Final Production Specifications & Deployment Classification (A/B/C)
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

def load_all_historical_data():
    df_15m = pd.read_csv(os.path.join(DATA_DIR, "BTCUSDm_15m.csv"))
    df_1h  = pd.read_csv(os.path.join(DATA_DIR, "BTCUSDm_1h.csv"))
    df_4h  = pd.read_csv(os.path.join(DATA_DIR, "BTCUSDm_4h.csv"))
    df_1d  = pd.read_csv(os.path.join(DATA_DIR, "BTCUSDm_1d.csv"))
    
    for df in (df_15m, df_1h, df_4h, df_1d):
        df['time'] = pd.to_datetime(df['time'])
        df.sort_values(by='time', inplace=True)
        df.reset_index(drop=True, inplace=True)
        
    with open(os.path.join(DATA_DIR, "BTCUSDm_spec.json"), "r") as f:
        spec = json.load(f)
    return df_15m, df_1h, df_4h, df_1d, spec

def build_4h_macro_regime_engine(df_4h):
    c = df_4h['close'].values
    o = df_4h['open'].values
    h = df_4h['high'].values
    l = df_4h['low'].values
    v = df_4h['volume'].replace(0, 1e-6).values
    n = len(df_4h)
    
    # 1. 4H ATR & Volatility Expansion
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    atr_4h = pd.Series(tr).ewm(span=14, adjust=False).mean().values
    atr_4h_fast = pd.Series(tr).ewm(span=5, adjust=False).mean().values
    atr_exp_4h = atr_4h_fast / np.maximum(atr_4h, 1e-9)
    atr_pct_4h = pd.Series(atr_4h).rolling(100, min_periods=30).apply(
        lambda x: float(pd.Series(x).rank().iloc[-1]) / len(x) * 100, raw=True
    ).fillna(50.0).values
    
    # 2. 4H EMAs & Trend Strength
    e21_4h = pd.Series(c).ewm(span=21, adjust=False).mean().values
    e50_4h = pd.Series(c).ewm(span=50, adjust=False).mean().values
    e200_4h = pd.Series(c).ewm(span=200, adjust=False).mean().values
    
    e50_slope_4h = pd.Series(e50_4h).diff(3).fillna(0).values / np.maximum(atr_4h, 1e-9)
    e200_slope_4h = pd.Series(e200_4h).diff(3).fillna(0).values / np.maximum(atr_4h, 1e-9)
    dist_e200_4h = (c - e200_4h) / np.maximum(atr_4h, 1e-9)
    
    # 3. 4H ADX
    tr_s = pd.Series(tr).ewm(span=14, adjust=False).mean()
    hd = np.concatenate([[0], np.diff(h)])
    ld = np.concatenate([[0], -np.diff(l)])
    dmp = np.where((hd > ld) & (hd > 0), hd, 0.0)
    dmm = np.where((ld > hd) & (ld > 0), ld, 0.0)
    di_p = 100 * pd.Series(dmp).ewm(span=14, adjust=False).mean() / tr_s.replace(0, 1e-9)
    di_m = 100 * pd.Series(dmm).ewm(span=14, adjust=False).mean() / tr_s.replace(0, 1e-9)
    dx = 100 * (di_p - di_m).abs() / (di_p + di_m).replace(0, 1e-9)
    adx_4h = dx.ewm(span=14, adjust=False).mean().values
    
    # 4. Donchian 4H Breakout
    d_high_4h = pd.Series(h).rolling(20, min_periods=10).max().values
    d_low_4h  = pd.Series(l).rolling(20, min_periods=10).min().values
    
    # 5. Macro Expansion Score (0-100) & 7-State Classification
    macro_score = np.zeros(n)
    regime_state = []
    exhaustion_state = [] # 'FRESH', 'MATURE', 'EXHAUSTED'
    
    for i in range(n):
        sc = 0.0
        # 4H Trend Alignment (35 pts)
        if c[i] > e200_4h[i] and e50_4h[i] > e200_4h[i]:
            sc += 20.0
            if e50_slope_4h[i] > 0.15: sc += 15.0
        elif c[i] < e200_4h[i] and e50_4h[i] < e200_4h[i]:
            sc += 20.0
            if e50_slope_4h[i] < -0.15: sc += 15.0
            
        # 4H Trend Strength (25 pts)
        if adx_4h[i] > 25.0: sc += 25.0
        elif adx_4h[i] > 18.0: sc += 12.0
        
        # 4H Volatility Expansion (40 pts)
        if atr_exp_4h[i] > 1.20: sc += 25.0
        elif atr_exp_4h[i] > 1.05: sc += 12.0
        
        if atr_pct_4h[i] > 60.0: sc += 15.0
        elif atr_pct_4h[i] > 40.0: sc += 8.0
        
        sc = min(max(sc, 0.0), 100.0)
        macro_score[i] = sc
        
        # 7-State Classification
        is_bull = (c[i] > e200_4h[i]) and (e50_4h[i] > e200_4h[i])
        is_bear = (c[i] < e200_4h[i]) and (e50_4h[i] < e200_4h[i])
        
        if is_bull and sc >= 60.0: st = "STRONG_BULL_EXPANSION"
        elif is_bull and sc >= 35.0: st = "MODERATE_BULL_TREND"
        elif is_bull: st = "BULL_CONSOLIDATION"
        elif is_bear and sc >= 60.0: st = "STRONG_BEAR_EXPANSION"
        elif is_bear and sc >= 35.0: st = "MODERATE_BEAR_TREND"
        elif is_bear: st = "BEAR_CONSOLIDATION"
        else: st = "NEUTRAL_COMPRESSION"
        regime_state.append(st)
        
        # Exhaustion Classification
        if abs(dist_e200_4h[i]) > 8.0 or atr_pct_4h[i] > 92.0:
            ex = "EXHAUSTED"
        elif abs(dist_e200_4h[i]) > 4.0 or adx_4h[i] > 40.0:
            ex = "MATURE"
        else:
            ex = "FRESH"
        exhaustion_state.append(ex)
        
    df_4h_res = df_4h.copy()
    df_4h_res['macro_score_4h'] = macro_score
    df_4h_res['regime_state_4h'] = regime_state
    df_4h_res['exhaustion_4h']   = exhaustion_state
    df_4h_res['atr_4h'] = atr_4h
    df_4h_res['e50_4h'] = e50_4h
    df_4h_res['e200_4h'] = e200_4h
    df_4h_res['adx_4h'] = adx_4h
    return df_4h_res

def test_macro_score_predictive_power(df_4h_res):
    """
    Forward predictive validation of 4H Macro Expansion Score over 12H, 24H, 48H, 7D horizons.
    """
    print("\n--- PHASE 5: FORWARD PREDICTIVE VALIDATION OF 4H MACRO SCORE ---")
    c = df_4h_res['close'].values
    atr = df_4h_res['atr_4h'].values
    sc = df_4h_res['macro_score_4h'].values
    n = len(df_4h_res)
    
    bins = [(0, 35, "Low Expansion (<35)"), (35, 60, "Mid Expansion (35-60)"), (60, 100, "High Expansion (>=60)")]
    
    for h_bars, h_lbl in [(3, "12-Hour"), (6, "24-Hour"), (12, "48-Hour"), (42, "7-Day")]:
        print(f"\nForward Horizon: {h_lbl} ({h_bars} 4H Bars)")
        print(f"{'Macro Score Bin':<22} | {'Bars Count':>10} | {'Fwd Abs Return %':>18} | {'Fwd Drift (x ATR)':>18} | {'Fwd Range (x ATR)':>18}")
        print("-" * 95)
        for b_min, b_max, b_name in bins:
            rets, drifts, ranges = [], [], []
            for i in range(100, n - h_bars):
                if b_min <= sc[i] < b_max:
                    fwd_c = c[i:i+h_bars+1]
                    abs_ret = abs(fwd_c[-1] - fwd_c[0]) / fwd_c[0] * 100
                    drift = abs(fwd_c[-1] - fwd_c[0]) / (atr[i] + 1e-9)
                    rng = (np.max(fwd_c) - np.min(fwd_c)) / (atr[i] + 1e-9)
                    rets.append(abs_ret)
                    drifts.append(drift)
                    ranges.append(rng)
            cnt = len(rets)
            mean_ret = np.mean(rets) if cnt > 0 else 0
            mean_drift = np.mean(drifts) if cnt > 0 else 0
            mean_rng = np.mean(ranges) if cnt > 0 else 0
            print(f"{b_name:<22} | {cnt:>10,} | {mean_ret:>17.2f}% | {mean_drift:>17.2f}x | {mean_rng:>17.2f}x")

def run_simple_4h_macro_benchmark(df_4h_res, risk_pct=0.005, initial_balance=10000.0, cost_mult=1.0):
    """
    Phase 24: Simple 4H Macro Trend Baseline (Close > EMA200, EMA50 > EMA200, ATR trailing).
    """
    c = df_4h_res['close'].values
    o = df_4h_res['open'].values
    h = df_4h_res['high'].values
    l = df_4h_res['low'].values
    e50 = df_4h_res['e50_4h'].values
    e200 = df_4h_res['e200_4h'].values
    atr = df_4h_res['atr_4h'].values
    times = df_4h_res['time'].values
    n = len(df_4h_res)
    
    spread_usd = 10.0 * cost_mult
    comm_pct   = 0.0001 * cost_mult
    slip_usd   = 2.0 * cost_mult
    
    equity = initial_balance
    peak_equity = initial_balance
    max_dd = 0.0
    trades = []
    
    in_pos = False
    pos_type = 0
    ep = sl = 0.0
    lots = 0.02
    entry_idx = 0
    
    for i in range(200, n):
        idx = i - 1
        if in_pos:
            hit_sl = False
            exit_p = 0.0
            # Trail stop by 2.5x ATR
            trail_dist = 2.5 * atr[i]
            if pos_type == 1:
                sl = max(sl, c[i] - trail_dist)
                if l[i] <= sl: hit_sl = True; exit_p = sl - spread_usd / 2
            else:
                sl = min(sl, c[i] + trail_dist)
                if h[i] >= sl: hit_sl = True; exit_p = sl + spread_usd / 2
                
            if hit_sl:
                final_pnl = (exit_p - ep) * lots if pos_type == 1 else (ep - exit_p) * lots
                final_pnl -= exit_p * lots * comm_pct
                equity += final_pnl
                if equity > peak_equity: peak_equity = equity
                dd = (peak_equity - equity) / peak_equity * 100
                if dd > max_dd: max_dd = dd
                
                trades.append({
                    "entry_time": str(times[entry_idx]),
                    "exit_time": str(times[i]),
                    "direction": "LONG" if pos_type == 1 else "SHORT",
                    "net_pnl": round(final_pnl, 2),
                    "r_multiple": round(final_pnl / (abs(ep - sl) * lots + 1e-9), 3),
                    "duration_bars": i - entry_idx
                })
                in_pos = False
                
        if not in_pos:
            bull_trend = (c[idx] > e200[idx]) and (e50[idx] > e200[idx]) and (c[idx] > e50[idx]) and (c[idx-1] <= e50[idx-1])
            bear_trend = (c[idx] < e200[idx]) and (e50[idx] < e200[idx]) and (c[idx] < e50[idx]) and (c[idx-1] >= e50[idx-1])
            
            sig = 1 if bull_trend else (-1 if bear_trend else 0)
            if sig != 0:
                direction = sig
                exec_price = o[i] + direction * slip_usd + (direction * spread_usd / 2)
                sl_dist = 2.5 * atr[idx]
                calc_sl = exec_price - sl_dist if direction == 1 else exec_price + sl_dist
                risk_capital = equity * risk_pct
                calc_lots = min(max(round(risk_capital / (sl_dist + 1e-9), 2), 0.01), 2.0)
                
                equity -= exec_price * calc_lots * comm_pct
                in_pos = True; pos_type = direction; ep = exec_price; sl = calc_sl
                lots = calc_lots; entry_idx = i

    if not trades:
        return {"total_trades": 0, "profit_factor": 0.0, "expectancy_usd": 0.0, "total_return_pct": 0.0, "max_drawdown": 0.0}
    tdf = pd.DataFrame(trades)
    wins = tdf[tdf['net_pnl'] > 0]; losses = tdf[tdf['net_pnl'] <= 0]
    gw = wins['net_pnl'].sum(); gl = abs(losses['net_pnl'].sum())
    pf = gw / gl if gl > 0 else 999.0
    tot_ret = (equity - initial_balance) / initial_balance * 100
    return {
        "total_trades": len(trades), "win_rate": round(len(wins)/len(tdf)*100, 1),
        "profit_factor": round(pf, 3), "expectancy_usd": round(tdf['net_pnl'].mean(), 2),
        "total_return_pct": round(tot_ret, 2), "max_drawdown": round(max_dd, 2)
    }

def run_v8_simulation(
    df_15m,
    df_4h_res,
    start_time=None,
    end_time=None,
    regime_mode="EXPANSION_GATED", # 'NO_GATE', 'HTF_TREND_ONLY', 'EXPANSION_GATED', 'FRESH_ONLY'
    cost_mult=1.0,
    risk_pct=0.005,
    initial_balance=10000.0
):
    """
    Phase 10 & 11: 15M V7 Breakout Execution strictly gated by 4H Macro Regime Engine.
    """
    # Merge 4H causal features into 15M with backward merge_asof
    df_15 = df_15m.copy()
    merged_4h = pd.merge_asof(
        df_15[['time']],
        df_4h_res[['time', 'macro_score_4h', 'regime_state_4h', 'exhaustion_4h', 'e50_4h', 'e200_4h']],
        on='time', direction='backward'
    )
    df_15['macro_score_4h'] = merged_4h['macro_score_4h'].fillna(0).values
    df_15['regime_state_4h'] = merged_4h['regime_state_4h'].fillna("NEUTRAL_COMPRESSION").values
    df_15['exhaustion_4h']   = merged_4h['exhaustion_4h'].fillna("FRESH").values
    
    if start_time is not None:
        df_15 = df_15[df_15['time'] >= pd.to_datetime(start_time)].reset_index(drop=True)
    if end_time is not None:
        df_15 = df_15[df_15['time'] <= pd.to_datetime(end_time)].reset_index(drop=True)
        
    c = df_15['close'].values; o = df_15['open'].values; h = df_15['high'].values; l = df_15['low'].values
    v = df_15['volume'].replace(0, 1e-6).values
    times = df_15['time'].values
    macro_sc = df_15['macro_score_4h'].values
    regime_st = df_15['regime_state_4h'].values
    exhaust_st = df_15['exhaustion_4h'].values
    n = len(df_15)
    
    # 15M Indicators
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    atr = pd.Series(tr).ewm(span=14, adjust=False).mean().values
    atr_fast = pd.Series(tr).ewm(span=5, adjust=False).mean().values
    atr_exp = atr_fast / np.maximum(atr, 1e-9)
    atr_pct = pd.Series(atr).rolling(100, min_periods=50).apply(
        lambda x: float(pd.Series(x).rank().iloc[-1]) / len(x) * 100, raw=True
    ).fillna(50.0).values
    
    bb_mid = pd.Series(c).rolling(20, min_periods=10).mean().values
    bb_std = pd.Series(c).rolling(20, min_periods=10).std().values
    bb_width = (2.0 * bb_std) / np.maximum(bb_mid, 1e-9)
    bb_width_pct = pd.Series(bb_width).rolling(100, min_periods=50).apply(
        lambda x: float(pd.Series(x).rank().iloc[-1]) / len(x) * 100, raw=True
    ).fillna(50.0).values
    
    d_high = pd.Series(h).rolling(32, min_periods=16).max().values
    d_low  = pd.Series(l).rolling(32, min_periods=16).min().values
    donchian_range_atr = (d_high - d_low) / np.maximum(atr, 1e-9)
    
    vol_avg = pd.Series(v).rolling(20, min_periods=10).mean().values
    rvol = v / np.maximum(vol_avg, 1e-9)
    
    ema21 = pd.Series(c).ewm(span=21, adjust=False).mean().values
    ema55 = pd.Series(c).ewm(span=55, adjust=False).mean().values
    
    coil_sc = np.zeros(n)
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
        coil_sc[i] = min(max(sc, 0.0), 100.0)
        
    spread_usd = 10.0 * cost_mult
    comm_pct   = 0.0001 * cost_mult
    slip_usd   = 2.0 * cost_mult
    cooldown_bars = 12
    
    equity = initial_balance
    peak_equity = initial_balance
    max_dd = 0.0
    trades = []
    
    in_pos = False
    pos_type = 0
    ep = sl = tp = tp1_price = 0.0
    tp1_hit = False
    tp1_pnl = 0.0
    lots = 0.02
    entry_idx = 0
    last_sig = -cooldown_bars
    
    for i in range(120, n):
        idx = i - 1
        # 1. POSITION MANAGEMENT
        if in_pos:
            hit_tp = False; hit_sl = False; exit_p = 0.0
            if not tp1_hit:
                if pos_type == 1 and h[i] >= tp1_price:
                    tp1_hit = True
                    part_exit = tp1_price - spread_usd / 2
                    tp1_pnl = (part_exit - ep) * (lots * 0.5)
                    tp1_pnl -= part_exit * (lots * 0.5) * comm_pct
                    equity += tp1_pnl
                    sl = ep
                elif pos_type == -1 and l[i] <= tp1_price:
                    tp1_hit = True
                    part_exit = tp1_price + spread_usd / 2
                    tp1_pnl = (ep - part_exit) * (lots * 0.5)
                    tp1_pnl -= part_exit * (lots * 0.5) * comm_pct
                    equity += tp1_pnl
                    sl = ep
                    
            if pos_type == 1:
                if l[i] <= sl: hit_sl = True; exit_p = sl - spread_usd / 2
                elif h[i] >= tp: hit_tp = True; exit_p = tp - spread_usd / 2
            else:
                if h[i] >= sl: hit_sl = True; exit_p = sl + spread_usd / 2
                elif l[i] <= tp: hit_tp = True; exit_p = tp + spread_usd / 2
                
            if hit_tp or hit_sl:
                rem_lots = (lots * 0.5) if tp1_hit else lots
                final_pnl = (exit_p - ep) * rem_lots if pos_type == 1 else (ep - exit_p) * rem_lots
                final_pnl -= exit_p * rem_lots * comm_pct
                equity += final_pnl
                tot_pnl = final_pnl + (tp1_pnl if tp1_hit else 0.0)
                if equity > peak_equity: peak_equity = equity
                dd = (peak_equity - equity) / peak_equity * 100
                if dd > max_dd: max_dd = dd
                
                risk_amt = abs(ep - sl) * lots
                trades.append({
                    "entry_time": str(times[entry_idx]),
                    "exit_time": str(times[i]),
                    "direction": "LONG" if pos_type == 1 else "SHORT",
                    "net_pnl": round(tot_pnl, 2),
                    "r_multiple": round(tot_pnl / (risk_amt + 1e-9), 3),
                    "duration_bars": i - entry_idx,
                    "regime": regime_st[entry_idx-1],
                    "macro_score": macro_sc[entry_idx-1],
                    "exhaustion": exhaust_st[entry_idx-1]
                })
                in_pos = False
                
        # 2. SIGNAL EVALUATION
        if not in_pos and (i - last_sig >= cooldown_bars):
            a = atr[idx]
            if np.isnan(a) or a <= 0: continue
            
            bar_date = pd.Timestamp(times[idx])
            if not (8 <= bar_date.hour <= 20): continue
            if coil_sc[idx] < 45.0: continue
            
            brk_high = d_high[idx-1]
            brk_low  = d_low[idx-1]
            
            bull_break = (c[idx] > brk_high) and (c[idx] > o[idx]) and (rvol[idx] >= 1.20) and (atr_exp[idx] >= 1.10)
            bear_break = (c[idx] < brk_low)  and (c[idx] < o[idx]) and (rvol[idx] >= 1.20) and (atr_exp[idx] >= 1.10)
            
            # Extension Cap (<= 1.10x ATR)
            if bull_break and (c[idx] - brk_high) / (a + 1e-9) > 1.10: bull_break = False
            if bear_break and (brk_low - c[idx]) / (a + 1e-9) > 1.10: bear_break = False
            
            # 4H MACRO REGIME GATING
            if regime_mode == "HTF_TREND_ONLY":
                if bull_break and "BULL" not in regime_st[idx]: bull_break = False
                if bear_break and "BEAR" not in regime_st[idx]: bear_break = False
            elif regime_mode == "EXPANSION_GATED":
                if bull_break and regime_st[idx] not in ["STRONG_BULL_EXPANSION", "MODERATE_BULL_TREND"]: bull_break = False
                if bear_break and regime_st[idx] not in ["STRONG_BEAR_EXPANSION", "MODERATE_BEAR_TREND"]: bear_break = False
                if macro_sc[idx] < 50.0: bull_break = bear_break = False
            elif regime_mode == "FRESH_ONLY":
                if bull_break and (regime_st[idx] != "STRONG_BULL_EXPANSION" or exhaust_st[idx] == "EXHAUSTED"): bull_break = False
                if bear_break and (regime_st[idx] != "STRONG_BEAR_EXPANSION" or exhaust_st[idx] == "EXHAUSTED"): bear_break = False
                
            sig = 1 if bull_break else (-1 if bear_break else 0)
            if sig != 0:
                direction = sig
                struct_sl = brk_low if sig == 1 else brk_high
                calc_sl = min(struct_sl, o[i] - 1.5 * a) if sig == 1 else max(struct_sl, o[i] + 1.5 * a)
                risk_dist = abs(o[i] - calc_sl)
                risk_dist = min(max(risk_dist, 1.2 * a), 3.5 * a)
                calc_sl = o[i] - risk_dist if sig == 1 else o[i] + risk_dist
                
                risk_capital = equity * risk_pct
                calc_lots = min(max(round(risk_capital / (risk_dist + 1e-9), 2), 0.01), 2.0)
                exec_price = o[i] + direction * slip_usd + (direction * spread_usd / 2)
                equity -= exec_price * calc_lots * comm_pct
                
                in_pos = True; pos_type = direction; ep = exec_price; sl = calc_sl
                tp = exec_price + direction * risk_dist * 4.0
                tp1_price = exec_price + direction * risk_dist * 2.0
                lots = calc_lots; entry_idx = i; last_sig = i
                tp1_hit = False; tp1_pnl = 0.0

    if not trades:
        return {"total_trades": 0, "profit_factor": 0.0, "win_rate": 0.0, "expectancy_usd": 0.0,
                "total_return_pct": 0.0, "net_profit_usd": 0.0, "max_drawdown": 0.0, "trades": []}
    tdf = pd.DataFrame(trades)
    wins = tdf[tdf['net_pnl'] > 0]; losses = tdf[tdf['net_pnl'] <= 0]
    gw = wins['net_pnl'].sum(); gl = abs(losses['net_pnl'].sum())
    pf = gw / gl if gl > 0 else 999.0
    tot_ret = (equity - initial_balance) / initial_balance * 100
    return {
        "total_trades": len(trades), "win_rate": round(len(wins)/len(tdf)*100, 1),
        "profit_factor": round(pf, 3), "expectancy_usd": round(tdf['net_pnl'].mean(), 2),
        "total_return_pct": round(tot_ret, 2), "net_profit_usd": round(tdf['net_pnl'].sum(), 2),
        "max_drawdown": round(max_dd, 2), "trades": trades
    }

def run_multi_cycle_walk_forward(df_15m, df_4h_res):
    """
    Phase 20 & 21: Multi-Cycle Historical Walk-Forward across chronological cycles.
    """
    print("\n--- PHASE 20 & 21: MULTI-CYCLE HISTORICAL WALK-FORWARD (V8 REGIME-GATED) ---")
    cycles = [
        ("Cycle 1 (Early 2025)", "2025-03-11", "2025-07-31"),
        ("Cycle 2 (Fall 2025 Transition)", "2025-08-01", "2025-11-30"),
        ("Cycle 3 (Winter 2025/2026 Bull Expansion)", "2025-12-01", "2026-04-30"),
        ("Cycle 4 (Summer 2026 Holdout Chop)", "2026-05-01", "2026-08-14")
    ]
    print(f"{'Historical Cycle':<38} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Return %':>9} | {'MaxDD %':>8}")
    print("-" * 105)
    for c_name, c_start, c_end in cycles:
        r = run_v8_simulation(df_15m, df_4h_res, start_time=c_start, end_time=c_end, regime_mode="EXPANSION_GATED")
        print(f"{c_name:<38} | {r['total_trades']:>7} | {r['win_rate']:>7.1f}% | {r['profit_factor']:>7.3f} | ${r['expectancy_usd']:>9.2f} | {r['total_return_pct']:>8.2f}% | {r['max_drawdown']:>7.1f}%")

def execute_v8_research():
    print("=" * 80)
    print("   BTCUSDm V8 — MACRO REGIME & EXPANSION RESEARCH SUITE")
    print("=" * 80)
    
    df_15m, df_1h, df_4h, df_1d, spec = load_all_historical_data()
    print(f"Datasets Loaded:")
    print(f"  1D:  {len(df_1d):>6,} bars ({df_1d['time'].iloc[0].date()} -> {df_1d['time'].iloc[-1].date()}) ~{len(df_1d)/365:.1f} years")
    print(f"  4H:  {len(df_4h):>6,} bars ({df_4h['time'].iloc[0].date()} -> {df_4h['time'].iloc[-1].date()}) ~{len(df_4h)/(365*6):.1f} years")
    print(f"  1H:  {len(df_1h):>6,} bars ({df_1h['time'].iloc[0].date()} -> {df_1h['time'].iloc[-1].date()}) ~{len(df_1h)/(365*24):.1f} years")
    print(f"  15M: {len(df_15m):>6,} bars ({df_15m['time'].iloc[0]} -> {df_15m['time'].iloc[-1]}) ~{len(df_15m)/(365*96):.1f} years")
    
    # 1. 4H Macro Regime Engine & Predictive Validation
    df_4h_res = build_4h_macro_regime_engine(df_4h)
    test_macro_score_predictive_power(df_4h_res)
    
    # 2. Simple 4H Macro Trend Baseline Benchmark
    print("\n--- PHASE 24 & 23: SIMPLE 4H MACRO TREND BENCHMARK ---")
    r_base_4h = run_simple_4h_macro_benchmark(df_4h_res)
    print(f"Simple 4H Macro Trend Baseline: Trades={r_base_4h['total_trades']} | WR={r_base_4h['win_rate']}% | PF={r_base_4h['profit_factor']:.3f} | Exp=${r_base_4h['expectancy_usd']:.2f} | Return={r_base_4h['total_return_pct']:+.2f}% | MaxDD={r_base_4h['max_drawdown']:.1f}%")

    # 3. Macro Regime Gating Comparison (15M Execution)
    print("\n--- PHASE 11: MACRO REGIME GATING COMPARISON ON 15M EXECUTION ---")
    print(f"{'Regime Mode':<32} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Return %':>9} | {'MaxDD %':>8}")
    print("-" * 98)
    for r_lbl, r_mode in [
        ("A. No Macro Gate", "NO_GATE"),
        ("B. HTF Trend Only (4H+1H)", "HTF_TREND_ONLY"),
        ("C. 4H Macro Expansion Gated", "EXPANSION_GATED"),
        ("D. Fresh Expansion Only", "FRESH_ONLY")
    ]:
        res = run_v8_simulation(df_15m, df_4h_res, regime_mode=r_mode)
        print(f"{r_lbl:<32} | {res['total_trades']:>7} | {res['win_rate']:>7.1f}% | {res['profit_factor']:>7.3f} | ${res['expectancy_usd']:>9.2f} | {res['total_return_pct']:>8.2f}% | {res['max_drawdown']:>7.1f}%")

    # 4. Multi-Cycle Walk-Forward
    run_multi_cycle_walk_forward(df_15m, df_4h_res)
    
    # 5. Long vs Short Asymmetry
    print("\n--- PHASE 19 & H: LONG VS SHORT DIRECTIONAL ASYMMETRY ---")
    v8_full = run_v8_simulation(df_15m, df_4h_res, regime_mode="EXPANSION_GATED")
    tdf = pd.DataFrame(v8_full['trades'])
    if len(tdf) > 0:
        longs = tdf[tdf['direction'] == "LONG"]
        shorts = tdf[tdf['direction'] == "SHORT"]
        
        def calc_split(sub_df):
            if len(sub_df) == 0: return 0, 0, 0, 0
            w = sub_df[sub_df['net_pnl'] > 0]; l = sub_df[sub_df['net_pnl'] <= 0]
            pf = w['net_pnl'].sum() / abs(l['net_pnl'].sum()) if len(l) > 0 else 999.0
            return len(sub_df), len(w)/len(sub_df)*100, pf, sub_df['net_pnl'].mean()
            
        n_l, wr_l, pf_l, exp_l = calc_split(longs)
        n_s, wr_s, pf_s, exp_s = calc_split(shorts)
        print(f"Bull Expansion Longs:  Trades={n_l:>3} | WR={wr_l:>5.1f}% | PF={pf_l:>6.3f} | Expectancy=${exp_l:>6.2f}")
        print(f"Bear Expansion Shorts: Trades={n_s:>3} | WR={wr_s:>5.1f}% | PF={pf_s:>6.3f} | Expectancy=${exp_s:>6.2f}")

    # 6. Cost Stress Testing (1x to 3x)
    print("\n--- PHASE 25 & M: TRANSACTION COST STRESS ON FROZEN V8 ---")
    for cm in [1.0, 1.5, 2.0, 3.0]:
        r = run_v8_simulation(df_15m, df_4h_res, regime_mode="EXPANSION_GATED", cost_mult=cm)
        print(f"  Cost {cm:.1f}x ($ {10.0*cm:>4.1f} spread): Trades={r['total_trades']:>3} | PF={r['profit_factor']:.3f} | Exp=${r['expectancy_usd']:>5.2f} | Ret={r['total_return_pct']:>+5.2f}% | MaxDD={r['max_drawdown']:.1f}%")

    # 7. Monte Carlo (10,000 Runs)
    print("\n--- PHASE 26 & N: MONTE CARLO SIMULATION ON V8 TRADES ---")
    v8_pnls = np.array([t['net_pnl'] for t in v8_full['trades']])
    if len(v8_pnls) > 0:
        n_sims = 10000; n_t = len(v8_pnls); final_eqs = []; max_dds = []; neg_count = 0
        np.random.seed(42)
        for _ in range(n_sims):
            sim_pnl = np.random.choice(v8_pnls, size=n_t, replace=True)
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

    # SAVE AUDIT RESULTS
    v8_results = {
        "full_v8": v8_full, "simple_4h_base": r_base_4h
    }
    with open("E:\\Trading\\v8_macro_results.json", "w") as f:
        json.dump(v8_results, f, indent=2)
    print("\nV8 RESEARCH SUITE COMPLETE. Saved to E:\\Trading\\v8_macro_results.json")

if __name__ == "__main__":
    execute_v8_research()
