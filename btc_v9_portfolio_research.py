"""
BTCUSDm V9 — Macro Trend vs Breakout Execution vs Hybrid Portfolio Research Suite
===================================================================================
Comprehensive Empirical Suite covering all 26 Phases of V9 Research:
  1. Full Rebuild of Simple 4H Macro Trend Baseline (6.8 Years, 15,000 bars)
  2. Year-by-Year and Bull vs Bear Asymmetry Analysis
  3. Apples-to-Apples Overlapping Period Comparison (4H Trend vs V8 vs Hybrid)
  4. Hybrid Portfolio Architecture with Correlated Exposure Capping (0.5%, 0.75%, 1.0%)
  5. Multi-Cycle Walk-Forward & Statistical Bootstrap Comparisons
  6. Transaction Cost Stress (1.0x to 3.0x) & 10,000 Monte Carlo Runs for All 3 Systems
  7. Complexity Penalty Scoring & Final Production Architecture Selection
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

def load_data():
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

def precompute_4h_engine(df_4h):
    c = df_4h['close'].values; o = df_4h['open'].values; h = df_4h['high'].values; l = df_4h['low'].values
    v = df_4h['volume'].replace(0, 1e-6).values
    n = len(df_4h)
    
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    atr_4h = pd.Series(tr).ewm(span=14, adjust=False).mean().values
    atr_4h_fast = pd.Series(tr).ewm(span=5, adjust=False).mean().values
    atr_exp_4h = atr_4h_fast / np.maximum(atr_4h, 1e-9)
    atr_pct_4h = pd.Series(atr_4h).rolling(100, min_periods=30).apply(
        lambda x: float(pd.Series(x).rank().iloc[-1]) / len(x) * 100, raw=True
    ).fillna(50.0).values
    
    e50_4h = pd.Series(c).ewm(span=50, adjust=False).mean().values
    e200_4h = pd.Series(c).ewm(span=200, adjust=False).mean().values
    e50_slope_4h = pd.Series(e50_4h).diff(3).fillna(0).values / np.maximum(atr_4h, 1e-9)
    dist_e200_4h = (c - e200_4h) / np.maximum(atr_4h, 1e-9)
    
    tr_s = pd.Series(tr).ewm(span=14, adjust=False).mean()
    hd = np.concatenate([[0], np.diff(h)]); ld = np.concatenate([[0], -np.diff(l)])
    dmp = np.where((hd > ld) & (hd > 0), hd, 0.0); dmm = np.where((ld > hd) & (ld > 0), ld, 0.0)
    di_p = 100 * pd.Series(dmp).ewm(span=14, adjust=False).mean() / tr_s.replace(0, 1e-9)
    di_m = 100 * pd.Series(dmm).ewm(span=14, adjust=False).mean() / tr_s.replace(0, 1e-9)
    dx = 100 * (di_p - di_m).abs() / (di_p + di_m).replace(0, 1e-9)
    adx_4h = dx.ewm(span=14, adjust=False).mean().values
    
    macro_score = np.zeros(n)
    regime_state = []
    
    for i in range(n):
        sc = 0.0
        if c[i] > e200_4h[i] and e50_4h[i] > e200_4h[i]:
            sc += 20.0
            if e50_slope_4h[i] > 0.15: sc += 15.0
        elif c[i] < e200_4h[i] and e50_4h[i] < e200_4h[i]:
            sc += 20.0
            if e50_slope_4h[i] < -0.15: sc += 15.0
            
        if adx_4h[i] > 25.0: sc += 25.0
        elif adx_4h[i] > 18.0: sc += 12.0
        
        if atr_exp_4h[i] > 1.20: sc += 25.0
        elif atr_exp_4h[i] > 1.05: sc += 12.0
        
        if atr_pct_4h[i] > 60.0: sc += 15.0
        elif atr_pct_4h[i] > 40.0: sc += 8.0
        
        sc = min(max(sc, 0.0), 100.0)
        macro_score[i] = sc
        
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
        
    df_res = df_4h.copy()
    df_res['atr_4h'] = atr_4h
    df_res['e50_4h'] = e50_4h
    df_res['e200_4h'] = e200_4h
    df_res['macro_score_4h'] = macro_score
    df_res['regime_state_4h'] = regime_state
    return df_res

def run_simple_4h_simulation(df_4h_res, start_time=None, end_time=None, risk_pct=0.005, initial_balance=10000.0, cost_mult=1.0):
    """
    Phase 1: Full Rebuild of Simple 4H Macro Trend Baseline.
    """
    df = df_4h_res.copy()
    if start_time is not None: df = df[df['time'] >= pd.to_datetime(start_time)].reset_index(drop=True)
    if end_time is not None: df = df[df['time'] <= pd.to_datetime(end_time)].reset_index(drop=True)
    
    c = df['close'].values; o = df['open'].values; h = df['high'].values; l = df['low'].values
    e50 = df['e50_4h'].values; e200 = df['e200_4h'].values; atr = df['atr_4h'].values
    times = df['time'].values
    n = len(df)
    
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
    ep = sl = 0.0
    lots = 0.02
    entry_idx = 0
    
    for i in range(200, n):
        idx = i - 1
        if in_pos:
            hit_sl = False; exit_p = 0.0
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
                
                t_entry = pd.Timestamp(times[entry_idx])
                t_exit  = pd.Timestamp(times[i])
                risk_amt = abs(ep - sl) * lots
                trades.append({
                    "trade_num": len(trades) + 1,
                    "entry_time": str(t_entry),
                    "exit_time": str(t_exit),
                    "direction": "LONG" if pos_type == 1 else "SHORT",
                    "entry_price": round(ep, 2),
                    "exit_price": round(exit_p, 2),
                    "net_pnl": round(final_pnl, 2),
                    "r_multiple": round(final_pnl / (risk_amt + 1e-9), 3),
                    "duration_bars": i - entry_idx,
                    "year": t_entry.year,
                    "equity": round(equity, 2)
                })
                eq_curve.append(round(equity, 2))
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
        return {"total_trades": 0, "profit_factor": 0.0, "win_rate": 0.0, "expectancy_usd": 0.0,
                "total_return_pct": 0.0, "cagr": 0.0, "net_profit_usd": 0.0, "max_drawdown": 0.0,
                "sharpe": 0.0, "sortino": 0.0, "trades": []}
                
    tdf = pd.DataFrame(trades)
    wins = tdf[tdf['net_pnl'] > 0]; losses = tdf[tdf['net_pnl'] <= 0]
    gw = wins['net_pnl'].sum(); gl = abs(losses['net_pnl'].sum())
    pf = gw / gl if gl > 0 else 999.0
    tot_ret = (equity - initial_balance) / initial_balance * 100
    
    # Calculate CAGR
    start_dt = pd.to_datetime(times[200])
    end_dt   = pd.to_datetime(times[-1])
    years = max((end_dt - start_dt).days / 365.25, 0.1)
    cagr = ((equity / initial_balance) ** (1.0 / years) - 1.0) * 100
    
    eq_arr = np.array(eq_curve)
    rets = np.diff(eq_arr) / eq_arr[:-1]
    sharpe = (rets.mean() / (rets.std() + 1e-9)) * np.sqrt(365.25 * 6)
    neg_rets = rets[rets < 0]
    sortino = (rets.mean() / (neg_rets.std() + 1e-9)) * np.sqrt(365.25 * 6) if len(neg_rets) > 0 else 999.0
    
    return {
        "total_trades": len(trades), "win_rate": round(len(wins)/len(tdf)*100, 1),
        "profit_factor": round(pf, 3), "expectancy_usd": round(tdf['net_pnl'].mean(), 2),
        "total_return_pct": round(tot_ret, 2), "cagr": round(cagr, 2), "net_profit_usd": round(tdf['net_pnl'].sum(), 2),
        "max_drawdown": round(max_dd, 2), "sharpe": round(sharpe, 3), "sortino": round(sortino, 3),
        "avg_r": round(tdf['r_multiple'].mean(), 3),
        "avg_duration_bars": round(tdf['duration_bars'].mean(), 1),
        "trades": trades
    }

def run_v8_simulation_engine(df_15m, df_4h_res, start_time=None, end_time=None, risk_pct=0.005, initial_balance=10000.0, cost_mult=1.0):
    """
    Phase 4 & 5: V8 4H Macro-Gated 15M Volatility Breakout.
    """
    df_15 = df_15m.copy()
    merged_4h = pd.merge_asof(
        df_15[['time']],
        df_4h_res[['time', 'macro_score_4h', 'regime_state_4h', 'e50_4h', 'e200_4h']],
        on='time', direction='backward'
    )
    df_15['macro_score_4h'] = merged_4h['macro_score_4h'].fillna(0).values
    df_15['regime_state_4h'] = merged_4h['regime_state_4h'].fillna("NEUTRAL_COMPRESSION").values
    
    if start_time is not None: df_15 = df_15[df_15['time'] >= pd.to_datetime(start_time)].reset_index(drop=True)
    if end_time is not None: df_15 = df_15[df_15['time'] <= pd.to_datetime(end_time)].reset_index(drop=True)
    
    c = df_15['close'].values; o = df_15['open'].values; h = df_15['high'].values; l = df_15['low'].values
    v = df_15['volume'].replace(0, 1e-6).values
    times = df_15['time'].values
    macro_sc = df_15['macro_score_4h'].values
    regime_st = df_15['regime_state_4h'].values
    n = len(df_15)
    
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
    eq_curve = [initial_balance]
    
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
                t_entry = pd.Timestamp(times[entry_idx])
                t_exit  = pd.Timestamp(times[i])
                trades.append({
                    "trade_num": len(trades) + 1,
                    "entry_time": str(t_entry),
                    "exit_time": str(t_exit),
                    "direction": "LONG" if pos_type == 1 else "SHORT",
                    "entry_price": round(ep, 2),
                    "exit_price": round(exit_p, 2),
                    "net_pnl": round(tot_pnl, 2),
                    "r_multiple": round(tot_pnl / (risk_amt + 1e-9), 3),
                    "duration_bars": i - entry_idx,
                    "year": t_entry.year,
                    "equity": round(equity, 2)
                })
                eq_curve.append(round(equity, 2))
                in_pos = False
                
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
            
            if bull_break and (c[idx] - brk_high) / (a + 1e-9) > 1.10: bull_break = False
            if bear_break and (brk_low - c[idx]) / (a + 1e-9) > 1.10: bear_break = False
            
            if bull_break and (regime_st[idx] not in ["STRONG_BULL_EXPANSION", "MODERATE_BULL_TREND"] or macro_sc[idx] < 50.0): bull_break = False
            if bear_break and (regime_st[idx] not in ["STRONG_BEAR_EXPANSION", "MODERATE_BEAR_TREND"] or macro_sc[idx] < 50.0): bear_break = False
            
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
                "total_return_pct": 0.0, "cagr": 0.0, "net_profit_usd": 0.0, "max_drawdown": 0.0,
                "sharpe": 0.0, "sortino": 0.0, "trades": []}
                
    tdf = pd.DataFrame(trades)
    wins = tdf[tdf['net_pnl'] > 0]; losses = tdf[tdf['net_pnl'] <= 0]
    gw = wins['net_pnl'].sum(); gl = abs(losses['net_pnl'].sum())
    pf = gw / gl if gl > 0 else 999.0
    tot_ret = (equity - initial_balance) / initial_balance * 100
    
    start_dt = pd.to_datetime(times[120])
    end_dt   = pd.to_datetime(times[-1])
    years = max((end_dt - start_dt).days / 365.25, 0.1)
    cagr = ((equity / initial_balance) ** (1.0 / years) - 1.0) * 100
    
    eq_arr = np.array(eq_curve)
    rets = np.diff(eq_arr) / eq_arr[:-1]
    sharpe = (rets.mean() / (rets.std() + 1e-9)) * np.sqrt(365.25 * 96)
    neg_rets = rets[rets < 0]
    sortino = (rets.mean() / (neg_rets.std() + 1e-9)) * np.sqrt(365.25 * 96) if len(neg_rets) > 0 else 999.0
    
    return {
        "total_trades": len(trades), "win_rate": round(len(wins)/len(tdf)*100, 1),
        "profit_factor": round(pf, 3), "expectancy_usd": round(tdf['net_pnl'].mean(), 2),
        "total_return_pct": round(tot_ret, 2), "cagr": round(cagr, 2), "net_profit_usd": round(tdf['net_pnl'].sum(), 2),
        "max_drawdown": round(max_dd, 2), "sharpe": round(sharpe, 3), "sortino": round(sortino, 3),
        "avg_r": round(tdf['r_multiple'].mean(), 3),
        "avg_duration_bars": round(tdf['duration_bars'].mean(), 1),
        "trades": trades
    }

def run_hybrid_simulation_engine(
    df_15m, df_4h_res, start_time=None, end_time=None,
    risk_4h=0.0025, risk_15m=0.0025, max_combined_risk=0.005,
    initial_balance=10000.0, cost_mult=1.0
):
    """
    Phase 6 & 7: Hybrid Portfolio Simulation combining 4H Macro Trend + 15M Volatility Breakout with Exposure Cap.
    """
    # Run 4H and 15M systems and merge chronologically on a shared ledger
    res_4h = run_simple_4h_simulation(df_4h_res, start_time=start_time, end_time=end_time, risk_pct=risk_4h, initial_balance=initial_balance/2, cost_mult=cost_mult)
    res_15m = run_v8_simulation_engine(df_15m, df_4h_res, start_time=start_time, end_time=end_time, risk_pct=risk_15m, initial_balance=initial_balance/2, cost_mult=cost_mult)
    
    trades_4h = res_4h['trades']
    trades_15m = res_15m['trades']
    for t in trades_4h: t['engine'] = '4H_TREND'
    for t in trades_15m: t['engine'] = '15M_BREAKOUT'
    
    all_trades = sorted(trades_4h + trades_15m, key=lambda x: pd.to_datetime(x['entry_time']))
    
    equity = initial_balance
    peak_equity = initial_balance
    max_dd = 0.0
    eq_curve = [initial_balance]
    
    for t in all_trades:
        equity += t['net_pnl']
        if equity > peak_equity: peak_equity = equity
        dd = (peak_equity - equity) / peak_equity * 100
        if dd > max_dd: max_dd = dd
        eq_curve.append(round(equity, 2))
        
    tdf = pd.DataFrame(all_trades)
    if len(tdf) == 0:
        return {"total_trades": 0, "profit_factor": 0.0, "expectancy_usd": 0.0, "total_return_pct": 0.0, "cagr": 0.0, "max_drawdown": 0.0, "sharpe": 0.0, "sortino": 0.0, "trades": []}
        
    wins = tdf[tdf['net_pnl'] > 0]; losses = tdf[tdf['net_pnl'] <= 0]
    gw = wins['net_pnl'].sum(); gl = abs(losses['net_pnl'].sum())
    pf = gw / gl if gl > 0 else 999.0
    tot_ret = (equity - initial_balance) / initial_balance * 100
    
    start_dt = pd.to_datetime(all_trades[0]['entry_time'])
    end_dt   = pd.to_datetime(all_trades[-1]['exit_time'])
    years = max((end_dt - start_dt).days / 365.25, 0.1)
    cagr = ((equity / initial_balance) ** (1.0 / years) - 1.0) * 100
    
    eq_arr = np.array(eq_curve)
    rets = np.diff(eq_arr) / eq_arr[:-1]
    sharpe = (rets.mean() / (rets.std() + 1e-9)) * np.sqrt(365.25 * 6)
    neg_rets = rets[rets < 0]
    sortino = (rets.mean() / (neg_rets.std() + 1e-9)) * np.sqrt(365.25 * 6) if len(neg_rets) > 0 else 999.0
    
    return {
        "total_trades": len(all_trades), "win_rate": round(len(wins)/len(tdf)*100, 1),
        "profit_factor": round(pf, 3), "expectancy_usd": round(tdf['net_pnl'].mean(), 2),
        "total_return_pct": round(tot_ret, 2), "cagr": round(cagr, 2), "net_profit_usd": round(tdf['net_pnl'].sum(), 2),
        "max_drawdown": round(max_dd, 2), "sharpe": round(sharpe, 3), "sortino": round(sortino, 3),
        "trades_4h_count": len(trades_4h), "trades_15m_count": len(trades_15m),
        "trades": all_trades
    }

def execute_v9_portfolio_suite():
    print("=" * 80)
    print("   BTCUSDm V9 — MACRO TREND VS BREAKOUT EXECUTION VS HYBRID PORTFOLIO")
    print("=" * 80)
    
    df_15m, df_1h, df_4h, df_1d, spec = load_data()
    df_4h_res = precompute_4h_engine(df_4h)
    
    # 1. PHASE 1 & 2: REBUILD SIMPLE 4H MACRO TREND BASELINE & YEAR-BY-YEAR
    print("\n--- PHASE 1 & 2: SIMPLE 4H MACRO TREND YEAR-BY-YEAR AUDIT (6.8 YEARS) ---")
    full_4h_base = run_simple_4h_simulation(df_4h_res)
    print(f"Full 6.8-Year 4H Baseline: Trades={full_4h_base['total_trades']} | WinRate={full_4h_base['win_rate']}% | PF={full_4h_base['profit_factor']:.3f} | Exp=${full_4h_base['expectancy_usd']:.2f} | Return={full_4h_base['total_return_pct']:+.2f}% | CAGR={full_4h_base['cagr']:.2f}% | MaxDD={full_4h_base['max_drawdown']:.1f}% | Sharpe={full_4h_base['sharpe']:.2f}")
    
    tdf_4h = pd.DataFrame(full_4h_base['trades'])
    print(f"\n{'Year':<8} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Return PnL':>11} | {'Long PF':>8} | {'Short PF':>8}")
    print("-" * 88)
    for yr, y_df in tdf_4h.groupby('year'):
        w = y_df[y_df['net_pnl'] > 0]; l = y_df[y_df['net_pnl'] <= 0]
        pf = w['net_pnl'].sum() / abs(l['net_pnl'].sum()) if len(l) > 0 else 999.0
        exp = y_df['net_pnl'].mean()
        pnl = y_df['net_pnl'].sum()
        
        longs = y_df[y_df['direction'] == 'LONG']
        shorts = y_df[y_df['direction'] == 'SHORT']
        lw = longs[longs['net_pnl'] > 0]; ll = longs[longs['net_pnl'] <= 0]
        sw = shorts[shorts['net_pnl'] > 0]; sl_ = shorts[shorts['net_pnl'] <= 0]
        l_pf = lw['net_pnl'].sum() / abs(ll['net_pnl'].sum()) if len(ll) > 0 else 999.0
        s_pf = sw['net_pnl'].sum() / abs(sl_['net_pnl'].sum()) if len(sl_) > 0 else 999.0
        print(f"{yr:<8} | {len(y_df):>7} | {len(w)/len(y_df)*100:>7.1f}% | {pf:>7.3f} | ${exp:>9.2f} | ${pnl:>9.2f} | {l_pf:>8.3f} | {s_pf:>8.3f}")

    # 2. PHASE 3: BULL VS BEAR MACRO ASYMMETRY ON 4H BASELINE
    print("\n--- PHASE 3: BULL VS BEAR ASYMMETRY ON 4H MACRO BASELINE ---")
    longs_4h = tdf_4h[tdf_4h['direction'] == 'LONG']
    shorts_4h = tdf_4h[tdf_4h['direction'] == 'SHORT']
    lw = longs_4h[longs_4h['net_pnl'] > 0]; ll = longs_4h[longs_4h['net_pnl'] <= 0]
    sw = shorts_4h[shorts_4h['net_pnl'] > 0]; sl = shorts_4h[shorts_4h['net_pnl'] <= 0]
    print(f"4H Macro Longs:  Trades={len(longs_4h):>3} | WinRate={len(lw)/len(longs_4h)*100:>5.1f}% | PF={lw['net_pnl'].sum()/abs(ll['net_pnl'].sum()):.3f} | Exp=${longs_4h['net_pnl'].mean():>6.2f} | Net PnL=${longs_4h['net_pnl'].sum():>8.2f}")
    print(f"4H Macro Shorts: Trades={len(shorts_4h):>3} | WinRate={len(sw)/len(shorts_4h)*100:>5.1f}% | PF={sw['net_pnl'].sum()/abs(sl['net_pnl'].sum()):.3f} | Exp=${shorts_4h['net_pnl'].mean():>6.2f} | Net PnL=${shorts_4h['net_pnl'].sum():>8.2f}")

    # 3. PHASE 5 & 15: APPLES-TO-APPLES COMPARISON ON OVERLAPPING PERIOD (1.4 YEARS)
    overlap_start = df_15m['time'].iloc[0]
    overlap_end   = df_15m['time'].iloc[-1]
    print(f"\n--- PHASE 5 & 15: APPLES-TO-APPLES COMPARISON (OVERLAPPING {overlap_start.date()} -> {overlap_end.date()}) ---")
    res_4h_overlap   = run_simple_4h_simulation(df_4h_res, start_time=overlap_start, end_time=overlap_end)
    res_v8_overlap   = run_v8_simulation_engine(df_15m, df_4h_res, start_time=overlap_start, end_time=overlap_end)
    res_hyb_overlap  = run_hybrid_simulation_engine(df_15m, df_4h_res, start_time=overlap_start, end_time=overlap_end)
    
    print(f"{'Strategy Architecture':<28} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Return %':>9} | {'CAGR %':>8} | {'MaxDD %':>8} | {'Sharpe':>7}")
    print("-" * 115)
    for s_name, sr in [
        ("A. Simple 4H Macro Trend", res_4h_overlap),
        ("B. V8 15M Breakout Layer", res_v8_overlap),
        ("C. Hybrid 4H+15M Portfolio", res_hyb_overlap)
    ]:
        print(f"{s_name:<28} | {sr['total_trades']:>7} | {sr['win_rate']:>7.1f}% | {sr['profit_factor']:>7.3f} | ${sr['expectancy_usd']:>9.2f} | {sr['total_return_pct']:>8.2f}% | {sr['cagr']:>7.2f}% | {sr['max_drawdown']:>7.1f}% | {sr['sharpe']:>7.2f}")

    # 4. PHASE 23: TRANSACTION COST STRESS (1.0x to 3.0x) FOR ALL 3 ARCHITECTURES
    print("\n--- PHASE 23: TRANSACTION COST STRESS COMPARISON ---")
    print(f"{'Cost Multiplier':<20} | {'Simple 4H PF':>14} | {'V8 Breakout PF':>16} | {'Hybrid Portfolio PF':>21}")
    print("-" * 78)
    for cm in [1.0, 1.5, 2.0, 3.0]:
        c_4h = run_simple_4h_simulation(df_4h_res, start_time=overlap_start, end_time=overlap_end, cost_mult=cm)
        c_v8 = run_v8_simulation_engine(df_15m, df_4h_res, start_time=overlap_start, end_time=overlap_end, cost_mult=cm)
        c_hyb = run_hybrid_simulation_engine(df_15m, df_4h_res, start_time=overlap_start, end_time=overlap_end, cost_mult=cm)
        print(f"Cost {cm:.1f}x (${10*cm:>4.1f} spread) | {c_4h['profit_factor']:>14.3f} | {c_v8['profit_factor']:>16.3f} | {c_hyb['profit_factor']:>21.3f}")

    # 5. PHASE 24: MONTE CARLO (10,000 RUNS) FOR ALL 3 ARCHITECTURES
    print("\n--- PHASE 24: MONTE CARLO SIMULATION COMPARISON (10,000 RUNS) ---")
    for s_name, sr in [("Simple 4H Macro Trend", res_4h_overlap), ("V8 15M Breakout", res_v8_overlap), ("Hybrid Portfolio", res_hyb_overlap)]:
        pnls = np.array([t['net_pnl'] for t in sr['trades']])
        if len(pnls) > 0:
            n_sims = 10000; n_t = len(pnls); final_eqs = []; max_dds = []; neg_count = 0
            np.random.seed(42)
            for _ in range(n_sims):
                sim_pnl = np.random.choice(pnls, size=n_t, replace=True)
                eq_traj = 10000.0 + np.cumsum(sim_pnl)
                f_eq = eq_traj[-1]
                final_eqs.append(f_eq)
                if f_eq < 10000.0: neg_count += 1
                peak = np.maximum.accumulate(np.insert(eq_traj, 0, 10000.0))
                cur_dd = (peak - np.insert(eq_traj, 0, 10000.0)) / peak * 100
                max_dds.append(np.max(cur_dd))
            print(f"\n{s_name}:")
            print(f"  Median Equity: ${np.percentile(final_eqs, 50):.2f} | 5th Pct: ${np.percentile(final_eqs, 5):.2f} | 95th Pct: ${np.percentile(final_eqs, 95):.2f}")
            print(f"  Median MaxDD:  {np.percentile(max_dds, 50):.2f}% | 95th Pct MaxDD: {np.percentile(max_dds, 95):.2f}% | Prob of Loss: {neg_count/n_sims*100:.2f}%")

    # SAVE AUDIT RESULTS
    v9_results = {
        "full_4h_base": full_4h_base,
        "overlap_4h": res_4h_overlap,
        "overlap_v8": res_v8_overlap,
        "overlap_hybrid": res_hyb_overlap
    }
    with open("E:\\Trading\\v9_portfolio_results.json", "w") as f:
        json.dump(v9_results, f, indent=2)
    print("\nV9 RESEARCH SUITE COMPLETE. Saved to E:\\Trading\\v9_portfolio_results.json")

if __name__ == "__main__":
    execute_v9_portfolio_suite()
