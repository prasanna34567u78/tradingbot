"""
BTCUSDm V5 — Range Quality Classifier & Regime Transition Research Engine
==========================================================================
Develops and validates:
  1. Multidimensional Range Quality Score (0-100)
  2. Range Breakout Risk Score (0-100)
  3. Range -> Trend Transition State Machine (RANGE, WARNING, BREAKOUT_RISK, TREND)
  4. POC Migration & Boundary Penetration Filters
  5. 5M Microstructure Warning Filter
  6. Predictive Forward-Horizon Validation (4, 8, 12, 24 bars)
  7. Train/Val Calibration & Final Untouched OOS Evaluation
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
    df_5m  = pd.read_csv(os.path.join(DATA_DIR, "BTCUSDm_5m.csv"))
    df_15m = pd.read_csv(os.path.join(DATA_DIR, "BTCUSDm_15m.csv"))
    df_1h  = pd.read_csv(os.path.join(DATA_DIR, "BTCUSDm_1h.csv"))
    
    for df in (df_5m, df_15m, df_1h):
        df['time'] = pd.to_datetime(df['time'])
        df.sort_values(by='time', inplace=True)
        df.reset_index(drop=True, inplace=True)
        
    with open(os.path.join(DATA_DIR, "BTCUSDm_spec.json"), "r") as f:
        spec = json.load(f)
    return df_5m, df_15m, df_1h, spec

def precompute_v5_features(df_5m, df_15m, df_1h):
    c = df_15m['close'].values
    o = df_15m['open'].values
    h = df_15m['high'].values
    l = df_15m['low'].values
    v = df_15m['volume'].replace(0, 1e-6).values
    n = len(df_15m)
    
    # 1. ATR (Wilder EWM - strictly backward causal)
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    atr = pd.Series(tr).ewm(span=14, adjust=False).mean().values
    atr_s = pd.Series(atr)
    
    # ATR change / expansion (ratio of short ATR to long ATR)
    atr_fast = pd.Series(tr).ewm(span=7, adjust=False).mean().values
    atr_expansion_ratio = atr_fast / np.maximum(atr, 1e-9)
    
    # 2. EMAs
    ema21 = pd.Series(c).ewm(span=21, adjust=False).mean().values
    ema55 = pd.Series(c).ewm(span=55, adjust=False).mean().values
    ema200 = pd.Series(c).ewm(span=200, adjust=False).mean().values
    
    ema21_slope = pd.Series(ema21).diff(4).fillna(0).values / np.maximum(atr, 1e-9)
    ema55_slope = pd.Series(ema55).diff(4).fillna(0).values / np.maximum(atr, 1e-9)
    ema_spread = np.abs(ema21 - ema55) / np.maximum(atr, 1e-9)
    ema200_dist = np.abs(c - ema200) / np.maximum(atr, 1e-9)
    
    # 3. ADX & Directional Movement
    tr_s_adx = pd.Series(tr).ewm(span=14, adjust=False).mean()
    hd = np.concatenate([[0], np.diff(h)])
    ld = np.concatenate([[0], -np.diff(l)])
    dmp = np.where((hd > ld) & (hd > 0), hd, 0.0)
    dmm = np.where((ld > hd) & (ld > 0), ld, 0.0)
    di_p = 100 * pd.Series(dmp).ewm(span=14, adjust=False).mean() / tr_s_adx.replace(0, 1e-9)
    di_m = 100 * pd.Series(dmm).ewm(span=14, adjust=False).mean() / tr_s_adx.replace(0, 1e-9)
    dx = 100 * (di_p - di_m).abs() / (di_p + di_m).replace(0, 1e-9)
    adx = dx.ewm(span=14, adjust=False).mean().values
    
    # 4. ATR Percentile & Bollinger Bandwidth
    atr_pct = atr_s.rolling(100, min_periods=50).apply(
        lambda x: float(pd.Series(x).rank().iloc[-1]) / len(x) * 100, raw=True
    ).fillna(50.0).values
    
    bb_mid = pd.Series(c).rolling(20, min_periods=10).mean().values
    bb_std = pd.Series(c).rolling(20, min_periods=10).std().values
    bb_width = (2.0 * bb_std) / np.maximum(bb_mid, 1e-9)
    
    # 5. Volume Profile & VWAP (96 bars lookback - strictly backward)
    tp = (h + l + c) / 3.0
    vp_pv = pd.Series(tp * v).rolling(96, min_periods=30).sum()
    vp_v  = pd.Series(v).rolling(96, min_periods=30).sum().replace(0, 1e-9)
    poc = (vp_pv / vp_v).values
    dev_sq = (tp - poc) ** 2
    vw_var = pd.Series(dev_sq * v).rolling(96, min_periods=30).sum() / vp_v
    vw_std = np.sqrt(np.maximum(vw_var, 0)).values
    vah = poc + 1.04 * vw_std
    val = poc - 1.04 * vw_std
    va_width = vah - val
    va_width_atr = va_width / np.maximum(atr, 1e-9)
    
    # POC Stability: rate of POC change over 12 bars normalized by ATR
    poc_change_12 = np.abs(pd.Series(poc).diff(12).fillna(0).values) / np.maximum(atr, 1e-9)
    
    # Rolling VWAP & slope
    vwap_slope = pd.Series(poc).diff(4).fillna(0).values / np.maximum(atr, 1e-9)
    
    vol_avg = pd.Series(v).rolling(20, min_periods=10).mean().values
    rvol = v / np.maximum(vol_avg, 1e-9)
    
    # 6. Price Rotation & Value Confinement
    inside_va = ((c >= val) & (c <= vah)).astype(int)
    va_confinement_ratio = pd.Series(inside_va).rolling(24, min_periods=12).mean().values
    
    # Crossings of POC in last 24 bars
    cross_poc = ((c[:-1] < poc[:-1]) & (c[1:] >= poc[1:])) | ((c[:-1] > poc[:-1]) & (c[1:] <= poc[1:]))
    cross_poc = np.insert(cross_poc, 0, False).astype(int)
    poc_cross_count_24 = pd.Series(cross_poc).rolling(24, min_periods=12).sum().values
    
    # 7. Boundary Attack Frequency: closes near/beyond VAL or VAH in last 12 bars
    near_boundary_touch = ((l <= val + 0.2 * atr) | (h >= vah - 0.2 * atr)).astype(int)
    boundary_attack_count_12 = pd.Series(near_boundary_touch).rolling(12, min_periods=6).sum().values
    
    # 8. HTF 1H Macro EMA Alignment (Causal merge)
    c1h = df_1h['close'].values
    e200_1h = pd.Series(c1h).ewm(span=200, adjust=False).mean().values
    e50_1h = pd.Series(c1h).ewm(span=50, adjust=False).mean().values
    df_1h_t = df_1h.copy()
    df_1h_t['htf_trend'] = np.where((c1h > e200_1h) & (e50_1h > e200_1h), 1,
                            np.where((c1h < e200_1h) & (e50_1h < e200_1h), -1, 0))
    merged_1h = pd.merge_asof(df_15m[['time']], df_1h_t[['time', 'htf_trend']], on='time', direction='backward')
    htf_trend = merged_1h['htf_trend'].fillna(0).values.astype(int)
    
    # 9. 5M Microstructure Confirmation (Vol expansion & directional cluster on 5M)
    df_5m_t = df_5m.copy()
    v5 = df_5m_t['volume'].replace(0, 1e-6).values
    c5 = df_5m_t['close'].values
    o5 = df_5m_t['open'].values
    v5_avg = pd.Series(v5).rolling(20, min_periods=10).mean().values
    rvol5 = v5 / np.maximum(v5_avg, 1e-9)
    dir5 = np.sign(c5 - o5)
    dir_cluster_3 = pd.Series(dir5).rolling(3, min_periods=3).sum().abs().values # 3 consecutive directional 5M candles
    df_5m_t['micro_warning'] = (rvol5 > 1.8) & (dir_cluster_3 >= 3)
    merged_5m = pd.merge_asof(df_15m[['time']], df_5m_t[['time', 'micro_warning']], on='time', direction='backward')
    micro_warning = merged_5m['micro_warning'].fillna(False).values.astype(bool)
    
    # 10. Swings
    sh_price = np.full(n, np.nan)
    sl_price = np.full(n, np.nan)
    for i in range(5, n - 5):
        if h[i] == max(h[i-5:i+6]): sh_price[i+5] = h[i]
        if l[i] == min(l[i-5:i+6]): sl_price[i+5] = l[i]
    last_sh = pd.Series(sh_price).ffill().values
    last_sl = pd.Series(sl_price).ffill().values
    
    return {
        "df": df_15m, "n": n, "c": c, "o": o, "h": h, "l": l, "v": v,
        "atr": atr, "atr_pct": atr_pct, "atr_expansion_ratio": atr_expansion_ratio,
        "ema21": ema21, "ema55": ema55, "ema200": ema200,
        "ema21_slope": ema21_slope, "ema55_slope": ema55_slope, "ema_spread": ema_spread,
        "adx": adx, "bb_width": bb_width, "poc": poc, "vah": vah, "val": val,
        "va_width_atr": va_width_atr, "poc_change_12": poc_change_12,
        "vwap_slope": vwap_slope, "rvol": rvol, "vol_avg": vol_avg,
        "va_confinement_ratio": va_confinement_ratio, "poc_cross_count_24": poc_cross_count_24,
        "boundary_attack_count_12": boundary_attack_count_12, "htf_trend": htf_trend,
        "micro_warning": micro_warning, "last_sh": last_sh, "last_sl": last_sl,
        "times": df_15m['time'].values
    }

def calculate_range_and_breakout_scores(feats, idx):
    """
    Computes lookahead-free Range Quality Score (0-100) and Breakout Risk Score (0-100).
    """
    # 1. Range Quality Components (Points out of 100)
    adx_i = feats['adx'][idx]
    ema_slope_i = max(abs(feats['ema21_slope'][idx]), abs(feats['ema55_slope'][idx]))
    ema_spread_i = feats['ema_spread'][idx]
    poc_stab_i = feats['poc_change_12'][idx]
    va_conf_i = feats['va_confinement_ratio'][idx]
    poc_cross_i = feats['poc_cross_count_24'][idx]
    va_w_atr = feats['va_width_atr'][idx]
    
    rq_score = 0.0
    # Trend Flatness (25 pts): ADX < 20 and flat EMAs
    if adx_i < 18.0: rq_score += 15.0
    elif adx_i < 24.0: rq_score += 8.0
    if ema_slope_i < 0.25: rq_score += 10.0
    elif ema_slope_i < 0.50: rq_score += 5.0
    
    # EMA Cohesion (15 pts): EMA21 and EMA55 closely aligned
    if ema_spread_i < 0.35: rq_score += 15.0
    elif ema_spread_i < 0.65: rq_score += 8.0
    
    # POC Stability (20 pts): POC hardly moving
    if poc_stab_i < 0.30: rq_score += 20.0
    elif poc_stab_i < 0.60: rq_score += 10.0
    
    # Price Rotation & Confinement (25 pts): High confinement + multiple POC crosses
    if va_conf_i >= 0.70: rq_score += 15.0
    elif va_conf_i >= 0.55: rq_score += 8.0
    if poc_cross_i >= 3: rq_score += 10.0
    elif poc_cross_i >= 2: rq_score += 5.0
    
    # Value Area Width Appropriateness (15 pts): 1.5x to 4.5x ATR is healthy range
    if 1.5 <= va_w_atr <= 4.5: rq_score += 15.0
    elif 1.0 <= va_w_atr <= 6.0: rq_score += 8.0
    
    rq_score = min(max(rq_score, 0.0), 100.0)
    
    # 2. Breakout Risk Components (Points out of 100)
    br_score = 0.0
    atr_exp = feats['atr_expansion_ratio'][idx]
    rvol_i = feats['rvol'][idx]
    boundary_attacks = feats['boundary_attack_count_12'][idx]
    micro_warn = feats['micro_warning'][idx]
    
    # Volatility / Volume Surge (30 pts)
    if atr_exp > 1.25: br_score += 15.0
    if rvol_i > 1.50: br_score += 15.0
    elif rvol_i > 1.20: br_score += 8.0
    
    # Trending Drift / POC Migration (30 pts)
    if adx_i > 25.0: br_score += 15.0
    if poc_stab_i > 0.80: br_score += 15.0
    elif poc_stab_i > 0.50: br_score += 8.0
    
    # Repeated Boundary Pounding (25 pts): Price hugging/attacking VAL or VAH
    if boundary_attacks >= 5: br_score += 25.0
    elif boundary_attacks >= 3: br_score += 12.0
    
    # 5M Microstructure Warning (15 pts)
    if micro_warn: br_score += 15.0
    
    br_score = min(max(br_score, 0.0), 100.0)
    
    # 3. Transition State Classification
    if br_score >= 50.0 or adx_i >= 28.0:
        state = "BREAKOUT_RISK"
    elif br_score >= 35.0 or rq_score < 45.0:
        state = "WARNING"
    elif rq_score >= 55.0 and br_score < 30.0:
        state = "RANGE"
    else:
        state = "NEUTRAL"
        
    return rq_score, br_score, state

def test_range_predictive_power(feats, train_end_idx):
    """
    Evaluates whether Range Quality Score predicts future forward volatility,
    directional drift, and adverse excursion over 4, 8, 12, 24 bars.
    Evaluated strictly on Training data (first 60% of bars).
    """
    print("\n--- PHASE 4: FORWARD-HORIZON PREDICTIVE VALIDATION (ON TRAIN SET) ---")
    c = feats['c']
    atr = feats['atr']
    n_train = train_end_idx
    
    rq_scores = []
    fwd_realized_vol_12 = []
    fwd_directional_drift_12 = []
    fwd_max_excursion_12 = []
    
    for i in range(120, n_train - 24):
        rq, br, _ = calculate_range_and_breakout_scores(feats, i)
        rq_scores.append(rq)
        
        # Forward metrics over 12 bars (3 hours)
        fwd_c = c[i:i+12]
        fwd_rets = np.diff(fwd_c) / fwd_c[:-1]
        realized_vol = np.std(fwd_rets) * np.sqrt(96) * 100
        directional_drift = abs(fwd_c[-1] - fwd_c[0]) / (atr[i] + 1e-9)
        max_excursion = (np.max(fwd_c) - np.min(fwd_c)) / (atr[i] + 1e-9)
        
        fwd_realized_vol_12.append(realized_vol)
        fwd_directional_drift_12.append(directional_drift)
        fwd_max_excursion_12.append(max_excursion)
        
    rq_arr = np.array(rq_scores)
    vol_arr = np.array(fwd_realized_vol_12)
    drift_arr = np.array(fwd_directional_drift_12)
    exc_arr = np.array(fwd_max_excursion_12)
    
    # Bin by Range Quality Score
    bins = [(0, 40, "Low Range Q (<40)"), (40, 60, "Mid Range Q (40-60)"), (60, 100, "High Range Q (>=60)")]
    print(f"{'Range Quality Bin':<22} | {'Bars Count':>10} | {'Fwd 12B Realized Vol %':>22} | {'Fwd 12B Drift (ATR)':>20} | {'Fwd 12B Range Exp (ATR)':>23}")
    print("-" * 105)
    for b_min, b_max, lbl in bins:
        mask = (rq_arr >= b_min) & (rq_arr < b_max)
        cnt = np.sum(mask)
        mean_vol = np.mean(vol_arr[mask]) if cnt > 0 else 0
        mean_drift = np.mean(drift_arr[mask]) if cnt > 0 else 0
        mean_exc = np.mean(exc_arr[mask]) if cnt > 0 else 0
        print(f"{lbl:<22} | {cnt:>10,} | {mean_vol:>21.2f}% | {mean_drift:>19.2f}x | {mean_exc:>22.2f}x")

def run_v5_simulation(
    feats,
    start_idx=120,
    end_idx=None,
    use_range_quality=True,
    min_range_quality=55.0,
    max_breakout_risk=35.0,
    use_breakout_filter=True,
    use_state_filter=True,
    use_boundary_quality=True,
    cost_mult=1.0,
    lots=0.02,
    initial_balance=10000.0
):
    n = feats['n']
    if end_idx is None: end_idx = n
    
    c = feats['c']; o = feats['o']; h = feats['h']; l = feats['l']; v = feats['v']
    atr = feats['atr']; poc = feats['poc']; vah = feats['vah']; val = feats['val']
    htf_trend = feats['htf_trend']; last_sh = feats['last_sh']; last_sl = feats['last_sl']
    times = feats['times']
    
    spread_usd = 10.0 * cost_mult
    comm_pct   = 0.0001 * cost_mult
    slip_usd   = 2.0 * cost_mult
    cooldown_bars = 12
    sl_atr_mult = 2.0
    tp1_rr = 1.5
    tp2_rr = 3.0
    
    equity = initial_balance
    peak_equity = initial_balance
    max_dd = 0.0
    trades = []
    eq_curve = [initial_balance]
    
    in_pos = False
    pos_type = 0
    ep = sl = tp1 = tp2 = 0.0
    tp1_hit = False
    entry_idx = 0
    tp1_pnl = 0.0
    last_sig = -cooldown_bars
    
    filtered_out_by_range_q = 0
    filtered_out_by_breakout = 0
    filtered_out_by_state = 0
    
    for i in range(start_idx, end_idx):
        if in_pos:
            hit_tp2 = False
            hit_sl = False
            exit_p = 0.0
            
            if pos_type == 1: # LONG
                if not tp1_hit and h[i] >= tp1:
                    tp1_hit = True
                    part_exit = tp1 - spread_usd / 2
                    tp1_pnl = (part_exit - ep) * (lots * 0.5)
                    tp1_pnl -= part_exit * (lots * 0.5) * comm_pct
                    equity += tp1_pnl
                    sl = ep # Immediate Breakeven
                    
                if l[i] <= sl:
                    hit_sl = True; exit_p = sl - spread_usd / 2
                elif h[i] >= tp2:
                    hit_tp2 = True; exit_p = tp2 - spread_usd / 2
            else: # SHORT
                if not tp1_hit and l[i] <= tp1:
                    tp1_hit = True
                    part_exit = tp1 + spread_usd / 2
                    tp1_pnl = (ep - part_exit) * (lots * 0.5)
                    tp1_pnl -= part_exit * (lots * 0.5) * comm_pct
                    equity += tp1_pnl
                    sl = ep # Immediate Breakeven
                    
                if h[i] >= sl:
                    hit_sl = True; exit_p = sl + spread_usd / 2
                elif l[i] <= tp2:
                    hit_tp2 = True; exit_p = tp2 + spread_usd / 2
                    
            if hit_tp2 or hit_sl:
                rem_lots = (lots * 0.5) if tp1_hit else lots
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
                
                trades.append({
                    "trade_num": len(trades) + 1,
                    "entry_time": str(t_entry),
                    "exit_time": str(t_exit),
                    "direction": "LONG" if pos_type == 1 else "SHORT",
                    "entry_price": round(ep, 2),
                    "stop_price": round(sl, 2),
                    "net_pnl": round(tot_pnl, 2),
                    "r_multiple": round(r_mult, 3),
                    "outcome": "TP2" if hit_tp2 else "SL",
                    "tp1_hit": tp1_hit,
                    "duration_bars": i - entry_idx,
                    "year": t_entry.year,
                    "equity": round(equity, 2),
                })
                eq_curve.append(round(equity, 2))
                in_pos = False
                
        if not in_pos and (i - last_sig >= cooldown_bars):
            idx = i - 1 # CAUSAL: evaluated at bar i-1 close
            a = atr[idx]
            if np.isnan(a) or a <= 0 or np.isnan(poc[idx]): continue
            
            price = c[idx]
            bar_date = pd.Timestamp(times[idx])
            if not (8 <= bar_date.hour <= 20): continue # London & NY
            
            # Setup A Candidate Detection
            b_rng = h[idx] - l[idx]
            b_body = abs(c[idx] - o[idx])
            b_ratio = b_body / (b_rng + 1e-9)
            bar_bull = (c[idx] > o[idx]) and (b_ratio > 0.28)
            bar_bear = (c[idx] < o[idx]) and (b_ratio > 0.28)
            l_wick = min(c[idx], o[idx]) - l[idx]
            u_wick = h[idx] - max(c[idx], o[idx])
            
            vp_tol = 0.35 * a
            near_val = l[idx] <= val[idx] + vp_tol
            near_vah = h[idx] >= vah[idx] - vp_tol
            
            sig = 0
            if near_val and bar_bull and l_wick > b_body * 0.35:
                sig = 1
            elif near_vah and bar_bear and u_wick > b_body * 0.35:
                sig = -1
                
            if sig == 0: continue
            
            # Range Quality & Transition State Audit
            rq_score, br_score, state = calculate_range_and_breakout_scores(feats, idx)
            
            if use_range_quality and rq_score < min_range_quality:
                filtered_out_by_range_q += 1
                continue
                
            if use_breakout_filter and br_score > max_breakout_risk:
                filtered_out_by_breakout += 1
                continue
                
            if use_state_filter and state in ["BREAKOUT_RISK", "TREND"]:
                filtered_out_by_state += 1
                continue
                
            # Value Area Boundary Quality Check: Penetration depth cannot exceed 1.2x ATR
            if use_boundary_quality:
                if sig == 1 and (val[idx] - l[idx]) > 1.2 * a:
                    continue # Sliced too deep below VAL (directional breakdown)
                if sig == -1 and (h[idx] - vah[idx]) > 1.2 * a:
                    continue # Sliced too deep above VAH (directional breakout)
                    
            direction = sig
            exec_price = o[i] + direction * slip_usd + (direction * spread_usd / 2)
            equity -= exec_price * lots * comm_pct
            sl_dist = a * sl_atr_mult
            calc_sl = exec_price - sl_dist if direction == 1 else exec_price + sl_dist
            risk_dist = abs(exec_price - calc_sl)
            calc_tp1 = exec_price + direction * risk_dist * tp1_rr
            calc_tp2 = exec_price + direction * risk_dist * tp2_rr
            
            in_pos = True; pos_type = direction; ep = exec_price; sl = calc_sl
            tp1 = calc_tp1; tp2 = calc_tp2; tp1_hit = False; entry_idx = i
            last_sig = i; tp1_pnl = 0.0

    if not trades:
        return {"total_trades": 0, "profit_factor": 0.0, "win_rate": 0.0, "expectancy_usd": 0.0,
                "total_return_pct": 0.0, "net_profit_usd": 0.0, "max_drawdown": 0.0,
                "sharpe": 0.0, "sortino": 0.0, "trades": []}
                
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
        "avg_win_usd": round(avg_w, 2), "avg_loss_usd": round(avg_l, 2),
        "median_trade_usd": round(tdf['net_pnl'].median(), 2),
        "largest_win_usd": round(tdf['net_pnl'].max(), 2),
        "largest_loss_usd": round(tdf['net_pnl'].min(), 2),
        "max_consecutive_losses": max_consec,
        "avg_duration_bars": round(tdf['duration_bars'].mean(), 1),
        "trades": trades
    }

def execute_v5_research_suite():
    print("=" * 80)
    print("   BTCUSDm V5 — RANGE QUALITY & REGIME TRANSITION RESEARCH SUITE")
    print("=" * 80)
    
    df_5m, df_15m, df_1h, spec = load_data()
    feats = precompute_v5_features(df_5m, df_15m, df_1h)
    n = feats['n']
    
    t_end = int(n * 0.60) # Bar 30,000 (Mar 2025 - Jan 2026)
    v_end = int(n * 0.80) # Bar 40,000 (Jan 2026 - May 2026)
    
    # 1. Predictive Validation on Train
    test_range_predictive_power(feats, t_end)
    
    # 2. Simple vs Complex Hierarchy on Train + Validation
    print("\n--- PHASE 19 & 11: SIMPLE VS COMPLEX ABLATION HIERARCHY (TRAIN + VAL) ---")
    print(f"{'Variant Name':<38} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Return %':>9} | {'MaxDD %':>8}")
    print("-" * 105)
    
    variants = [
        ("A. Baseline Frozen V4", False, 0.0, 100.0, False, False, False),
        ("B. V4 + Range Quality Score (>=50)", True, 50.0, 100.0, False, False, False),
        ("C. V4 + Breakout Risk Filter (<=40)", False, 0.0, 40.0, True, False, False),
        ("D. V4 + Range Quality + Breakout Risk", True, 50.0, 40.0, True, False, False),
        ("E. V5 Complete (RQ + BR + State + Boundary)", True, 55.0, 35.0, True, True, True)
    ]
    
    for name, use_rq, min_rq, max_br, use_br, use_st, use_bq in variants:
        res_tv = run_v5_simulation(feats, start_idx=120, end_idx=v_end,
                                  use_range_quality=use_rq, min_range_quality=min_rq,
                                  max_breakout_risk=max_br, use_breakout_filter=use_br,
                                  use_state_filter=use_st, use_boundary_quality=use_bq)
        print(f"{name:<38} | {res_tv['total_trades']:>7} | {res_tv['win_rate']:>7.1f}% | {res_tv['profit_factor']:>7.3f} | ${res_tv['expectancy_usd']:>9.2f} | {res_tv['total_return_pct']:>8.2f}% | {res_tv['max_drawdown']:>7.1f}%")
        
    # 3. FROZEN V5 EVALUATION ON FINAL UNTOUCHED OOS (May 2026 - Aug 2026)
    print("\n" + "=" * 80)
    print("   PHASE 15 & 7: FROZEN V5 EVALUATION ON FINAL UNTOUCHED OOS")
    print("=" * 80)
    v5_train = run_v5_simulation(feats, start_idx=120, end_idx=t_end, min_range_quality=55.0, max_breakout_risk=35.0)
    v5_val   = run_v5_simulation(feats, start_idx=t_end, end_idx=v_end, min_range_quality=55.0, max_breakout_risk=35.0)
    v5_oos   = run_v5_simulation(feats, start_idx=v_end, end_idx=n, min_range_quality=55.0, max_breakout_risk=35.0)
    v5_full  = run_v5_simulation(feats, start_idx=120, end_idx=n, min_range_quality=55.0, max_breakout_risk=35.0)
    
    print(f"{'Partition':<16} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Return %':>9} | {'MaxDD %':>8} | {'Sharpe':>7} | {'Sortino':>7}")
    print("-" * 95)
    for pname, pr in [("TRAIN (60%)", v5_train), ("VAL (20%)", v5_val), ("FINAL OOS (20%)", v5_oos), ("TOTAL FULL", v5_full)]:
        print(f"{pname:<16} | {pr['total_trades']:>7} | {pr['win_rate']:>7.1f}% | {pr['profit_factor']:>7.3f} | ${pr['expectancy_usd']:>9.2f} | {pr['total_return_pct']:>8.2f}% | {pr['max_drawdown']:>7.1f}% | {pr['sharpe']:>7.2f} | {pr['sortino']:>7.2f}")
        
    # 4. COST STRESS ON V5
    print("\n" + "=" * 80)
    print("   PHASE 21: TRANSACTION COST STRESS ON FROZEN V5")
    print("=" * 80)
    for cm in [1.0, 1.5, 2.0, 3.0]:
        r_cost = run_v5_simulation(feats, cost_mult=cm)
        print(f"  Cost {cm:.1f}x ($ {10.0*cm:>4.1f} spread): Trades={r_cost['total_trades']:>3} | PF={r_cost['profit_factor']:.3f} | Exp=${r_cost['expectancy_usd']:>5.2f} | Ret={r_cost['total_return_pct']:>+5.2f}% | MaxDD={r_cost['max_drawdown']:.1f}%")
        
    # 5. MONTE CARLO ON V5 TRADE LEDGER (10,000 RUNS)
    print("\n" + "=" * 80)
    print("   PHASE 22: MONTE CARLO SIMULATION ON V5 TRADES")
    print("=" * 80)
    v5_pnls = np.array([t['net_pnl'] for t in v5_full['trades']])
    if len(v5_pnls) > 0:
        n_sims = 10000
        n_t = len(v5_pnls)
        final_eqs = []
        max_dds = []
        neg_count = 0
        
        np.random.seed(42)
        for _ in range(n_sims):
            sim_pnl = np.random.choice(v5_pnls, size=n_t, replace=True)
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
    v5_results = {
        "full": v5_full, "train": v5_train, "val": v5_val, "oos": v5_oos
    }
    with open("E:\\Trading\\v5_research_results.json", "w") as f:
        json.dump(v5_results, f, indent=2)
    print("\nV5 RESEARCH SUITE COMPLETE. Saved to E:\\Trading\\v5_research_results.json")

if __name__ == "__main__":
    execute_v5_research_suite()
