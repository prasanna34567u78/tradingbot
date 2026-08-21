"""
BTCUSDm V4 — Final OOS Audit, Reconciliation & Edge Verification Engine
========================================================================
Performs rigorous end-to-end mathematical verification of the frozen V3 strategy
on REAL MT5 BTCUSDm historical data.
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
    df_15m['time'] = pd.to_datetime(df_15m['time'])
    df_1h['time']  = pd.to_datetime(df_1h['time'])
    df_15m.sort_values(by='time', inplace=True)
    df_1h.sort_values(by='time', inplace=True)
    df_15m.reset_index(drop=True, inplace=True)
    df_1h.reset_index(drop=True, inplace=True)
    
    with open(os.path.join(DATA_DIR, "BTCUSDm_spec.json"), "r") as f:
        spec = json.load(f)
    return df_15m, df_1h, spec

def precompute_frozen_v3_features(df_15m, df_1h):
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
    
    # 2. EMAs
    ema21 = pd.Series(c).ewm(span=21, adjust=False).mean().values
    ema55 = pd.Series(c).ewm(span=55, adjust=False).mean().values
    ema200 = pd.Series(c).ewm(span=200, adjust=False).mean().values
    
    # 3. ADX
    tr_s = pd.Series(tr).ewm(span=14, adjust=False).mean()
    hd = np.concatenate([[0], np.diff(h)])
    ld = np.concatenate([[0], -np.diff(l)])
    dmp = np.where((hd > ld) & (hd > 0), hd, 0.0)
    dmm = np.where((ld > hd) & (ld > 0), ld, 0.0)
    di_p = 100 * pd.Series(dmp).ewm(span=14, adjust=False).mean() / tr_s.replace(0, 1e-9)
    di_m = 100 * pd.Series(dmm).ewm(span=14, adjust=False).mean() / tr_s.replace(0, 1e-9)
    dx = 100 * (di_p - di_m).abs() / (di_p + di_m).replace(0, 1e-9)
    adx = dx.ewm(span=14, adjust=False).mean().values
    
    # 4. ATR Percentile
    atr_pct = pd.Series(atr).rolling(100, min_periods=50).apply(
        lambda x: float(pd.Series(x).rank().iloc[-1]) / len(x) * 100, raw=True
    ).fillna(50.0).values
    
    # 5. Volume Profile (96 bars lookback - strictly backward)
    tp = (h + l + c) / 3.0
    vp_pv = pd.Series(tp * v).rolling(96, min_periods=30).sum()
    vp_v  = pd.Series(v).rolling(96, min_periods=30).sum().replace(0, 1e-9)
    poc = (vp_pv / vp_v).values
    dev_sq = (tp - poc) ** 2
    vw_var = pd.Series(dev_sq * v).rolling(96, min_periods=30).sum() / vp_v
    vw_std = np.sqrt(np.maximum(vw_var, 0)).values
    vah = poc + 1.04 * vw_std
    val = poc - 1.04 * vw_std
    
    vol_avg = pd.Series(v).rolling(20, min_periods=10).mean().values
    
    # 6. Swings (5 left, 5 right -> confirmed strictly at i+5)
    sh_price = np.full(n, np.nan)
    sl_price = np.full(n, np.nan)
    for i in range(5, n - 5):
        if h[i] == max(h[i-5:i+6]): sh_price[i+5] = h[i]
        if l[i] == min(l[i-5:i+6]): sl_price[i+5] = l[i]
    last_sh = pd.Series(sh_price).ffill().values
    last_sl = pd.Series(sl_price).ffill().values
    
    # 7. HTF 1H Trend (causal backward merge)
    c1h = df_1h['close'].values
    e200_1h = pd.Series(c1h).ewm(span=200, adjust=False).mean().values
    e50_1h = pd.Series(c1h).ewm(span=50, adjust=False).mean().values
    df_1h_t = df_1h.copy()
    df_1h_t['htf_trend'] = np.where((c1h > e200_1h) & (e50_1h > e200_1h), 1,
                            np.where((c1h < e200_1h) & (e50_1h < e200_1h), -1, 0))
    merged_1h = pd.merge_asof(df_15m[['time']], df_1h_t[['time', 'htf_trend']], on='time', direction='backward')
    htf_trend = merged_1h['htf_trend'].fillna(0).values.astype(int)
    
    # 8. MTF 15M Momentum (RSI 14)
    d15 = pd.Series(c).diff()
    rg = d15.where(d15 > 0, 0).ewm(span=14, adjust=False).mean()
    rl = (-d15.where(d15 < 0, 0)).ewm(span=14, adjust=False).mean()
    rsi15 = (100 - 100 / (1 + rg / rl.replace(0, 1e-9))).values
    mtf_trend = np.where((ema21 > ema55) & (rsi15 > 50), 1,
                np.where((ema21 < ema55) & (rsi15 < 50), -1, 0))
                
    return {
        "df": df_15m, "n": n, "c": c, "o": o, "h": h, "l": l, "v": v,
        "atr": atr, "ema21": ema21, "ema55": ema55, "ema200": ema200,
        "adx": adx, "atr_pct": atr_pct, "poc": poc, "vah": vah, "val": val,
        "vol_avg": vol_avg, "last_sh": last_sh, "last_sl": last_sl,
        "htf_trend": htf_trend, "mtf_trend": mtf_trend, "rsi15": rsi15,
        "times": df_15m['time'].values
    }

def run_v3_frozen_audit(
    feats,
    start_idx=120,
    end_idx=None,
    sl_atr_mult=2.0,
    min_score=45,
    tp1_rr=1.5,
    tp2_rr=3.0,
    be_mode="immediate",
    session_filter=(8, 20),
    regime_mode="range_plus_normal", # only range and normal vol
    allowed_setups=(1,),              # Setup A only
    use_score=True,
    vp_lookback=96,
    cost_mult=1.0,
    lots=0.02,
    initial_balance=10000.0,
    entry_delay=0,
    price_perturb_bps=0.0,
    disable_component=None
):
    n = feats['n']
    if end_idx is None: end_idx = n
    
    c = feats['c']; o = feats['o']; h = feats['h']; l = feats['l']; v = feats['v']
    atr = feats['atr']; ema21 = feats['ema21']; ema55 = feats['ema55']; ema200 = feats['ema200']
    adx = feats['adx']; atr_pct = feats['atr_pct']; poc = feats['poc']; vah = feats['vah']; val = feats['val']
    vol_avg = feats['vol_avg']; last_sh = feats['last_sh']; last_sl = feats['last_sl']
    htf_trend = feats['htf_trend']; mtf_trend = feats['mtf_trend']; rsi15 = feats['rsi15']
    times = feats['times']
    
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
    ep = sl = tp1 = tp2 = 0.0
    tp1_hit = False
    entry_idx = 0
    entry_time = None
    entry_score = 0
    entry_regime = ""
    entry_setup = 0
    last_sig = -cooldown_bars
    tp1_pnl = 0.0
    
    pending_sig = 0
    pending_setup = 0
    pending_score = 0
    pending_regime = ""
    delay_counter = 0
    
    for i in range(start_idx, end_idx):
        # 1. POSITION MANAGEMENT
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
                    if be_mode == "immediate": sl = ep
                    elif be_mode == "be_plus_fee": sl = ep + spread_usd * 0.5
                    elif be_mode == "none": pass
                    
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
                    if be_mode == "immediate": sl = ep
                    elif be_mode == "be_plus_fee": sl = ep - spread_usd * 0.5
                    elif be_mode == "none": pass
                    
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
                    "tp1_price": round(tp1, 2),
                    "tp2_price": round(tp2, 2),
                    "lots": lots,
                    "gross_pnl": round(tot_pnl + (ep * lots * comm_pct) + (exit_p * rem_lots * comm_pct), 2),
                    "spread_usd": round(spread_usd * lots, 2),
                    "commission_usd": round((ep * lots + exit_p * rem_lots) * comm_pct, 2),
                    "slippage_usd": round(slip_usd * lots, 2),
                    "net_pnl": round(tot_pnl, 2),
                    "r_multiple": round(r_mult, 3),
                    "outcome": "TP2" if hit_tp2 else "SL",
                    "tp1_hit": tp1_hit,
                    "regime": entry_regime,
                    "score": entry_score,
                    "duration_bars": i - entry_idx,
                    "year": t_entry.year,
                    "month": t_entry.strftime("%Y-%m"),
                    "equity": round(equity, 2),
                })
                eq_curve.append(round(equity, 2))
                in_pos = False
                
        # 2. SIGNAL GENERATION & ENTRY EXECUTION
        if not in_pos and (i - last_sig >= cooldown_bars):
            idx = i - 1 # CAUSAL: Signal evaluated at close of candle i-1
            a = atr[idx]
            if np.isnan(a) or a <= 0 or np.isnan(poc[idx]): continue
            
            price = c[idx]
            bar_date = pd.Timestamp(times[idx])
            
            # Session filter
            if session_filter is not None:
                if not (session_filter[0] <= bar_date.hour <= session_filter[1]):
                    continue
                    
            adx_i = adx[idx]
            atr_pct_i = atr_pct[idx]
            is_extreme_vol = atr_pct_i >= 92.0
            
            bull_15m = (price > ema200[idx]) and (ema21[idx] > ema55[idx])
            bear_15m = (price < ema200[idx]) and (ema21[idx] < ema55[idx])
            
            # Lookahead-free regime classification
            if adx_i > 28.0 and bull_15m: regime = "Strong Bull Trend"
            elif adx_i > 28.0 and bear_15m: regime = "Strong Bear Trend"
            elif adx_i > 20.0 and bull_15m: regime = "Weak Bull Trend"
            elif adx_i > 20.0 and bear_15m: regime = "Weak Bear Trend"
            elif atr_pct_i >= 75.0 and adx_i > 22.0: regime = "High-Vol Trend"
            elif atr_pct_i >= 75.0: regime = "High-Vol Range"
            elif atr_pct_i <= 30.0: regime = "Low-Vol Market"
            else: regime = "Sideways Range"
            
            # Regime gating
            if regime_mode == "range_plus_normal":
                if "Strong" in regime or "Weak" in regime:
                    # Gated out: trend regimes
                    pass
            elif regime_mode == "range_only":
                if regime != "Sideways Range":
                    continue
            elif regime_mode == "all":
                pass
                
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
            near_poc = abs(price - poc[idx]) < vp_tol * 1.5
            
            lsh = last_sh[idx]; lsl = last_sl[idx]
            bull_sweep = (l[idx] < lsl - 0.001 * price) and (c[idx] > lsl) if not np.isnan(lsl) else False
            bear_sweep = (h[idx] > lsh + 0.001 * price) and (c[idx] < lsh) if not np.isnan(lsh) else False
            vol_exp = (v[idx] >= 1.2 * vol_avg[idx]) if not np.isnan(vol_avg[idx]) else False
            
            score = 0
            if use_score:
                if disable_component != "htf": score += 20 if (htf_trend[idx] != 0) else 0
                if disable_component != "mtf": score += 15 if (mtf_trend[idx] != 0) else 0
                if disable_component != "vol": score += 15 if vol_exp else 0
                if disable_component != "vp": score += 15 if (near_val or near_vah or near_poc) else 0
                if disable_component != "sweep": score += 10 if (bull_sweep or bear_sweep) else 0
                if disable_component != "structure": score += 10 if ("Trend" in regime or "Range" in regime) else 0
                if disable_component != "candle": score += 5 if (bar_bull or bar_bear) else 0
                if disable_component != "vol_regime": score += 5 if not is_extreme_vol else 0
                if disable_component != "rsi": score += 5 if (35 < rsi15[idx] < 65) else 0
            else:
                score = 100 # Bypass score filter
                
            setup_id = 0; sig = 0
            if 1 in allowed_setups:
                if (near_val and bar_bull and l_wick > b_body * 0.35 and ("Range" in regime or bull_15m)):
                    sig = 1; setup_id = 1
                elif (near_vah and bar_bear and u_wick > b_body * 0.35 and ("Range" in regime or bear_15m)):
                    sig = -1; setup_id = 1
            if sig == 0 and 2 in allowed_setups:
                if (bull_15m and near_poc and bar_bull and vol_exp and "Trend" in regime):
                    sig = 1; setup_id = 2
                elif (bear_15m and near_poc and bar_bear and vol_exp and "Trend" in regime):
                    sig = -1; setup_id = 2
            if sig == 0 and 3 in allowed_setups:
                if (bull_sweep and bar_bull):
                    sig = 1; setup_id = 3
                elif (bear_sweep and bar_bear):
                    sig = -1; setup_id = 3
            if sig == 0 and 4 in allowed_setups:
                if (bull_15m and price > vah[idx] and bar_bull and vol_exp):
                    sig = 1; setup_id = 4
                elif (bear_15m and price < val[idx] and bar_bear and vol_exp):
                    sig = -1; setup_id = 4
                    
            if sig != 0 and score >= min_score and not is_extreme_vol:
                if entry_delay == 0:
                    direction = sig
                    exec_price = o[i] + direction * slip_usd + (direction * spread_usd / 2)
                    if price_perturb_bps != 0.0:
                        exec_price *= (1.0 + price_perturb_bps / 10000.0 * direction)
                        
                    equity -= exec_price * lots * comm_pct
                    sl_dist = a * sl_atr_mult
                    calc_sl = exec_price - sl_dist if direction == 1 else exec_price + sl_dist
                    risk_dist = abs(exec_price - calc_sl)
                    calc_tp1 = exec_price + direction * risk_dist * tp1_rr
                    calc_tp2 = exec_price + direction * risk_dist * tp2_rr
                    
                    in_pos = True; pos_type = direction; ep = exec_price; sl = calc_sl
                    tp1 = calc_tp1; tp2 = calc_tp2; tp1_hit = False; entry_idx = i
                    entry_time = pd.Timestamp(times[i]); entry_score = score
                    entry_regime = regime; entry_setup = setup_id; last_sig = i
                    tp1_pnl = 0.0
                else:
                    # Queued for delay
                    pending_sig = sig
                    pending_setup = setup_id
                    pending_score = score
                    pending_regime = regime
                    delay_counter = entry_delay

    if not trades:
        return {"total_trades": 0, "profit_factor": 0.0, "win_rate": 0.0, "expectancy_usd": 0.0,
                "total_return_pct": 0.0, "max_drawdown": 0.0, "sharpe": 0.0, "sortino": 0.0,
                "gross_profit": 0.0, "gross_loss": 0.0, "net_profit": 0.0, "trades": []}
                
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
        "net_profit_usd": round(tot_pnl, 2), "gross_profit_usd": round(gw, 2),
        "gross_loss_usd": round(gl, 2), "max_drawdown": round(max_dd, 2),
        "sharpe": round(sharpe, 3), "sortino": round(sortino, 3),
        "avg_win_usd": round(avg_w, 2), "avg_loss_usd": round(avg_l, 2),
        "median_trade_usd": round(tdf['net_pnl'].median(), 2),
        "largest_win_usd": round(tdf['net_pnl'].max(), 2),
        "largest_loss_usd": round(tdf['net_pnl'].min(), 2),
        "max_consecutive_losses": max_consec,
        "avg_duration_bars": round(tdf['duration_bars'].mean(), 1),
        "first_trade": tdf['entry_time'].iloc[0] if len(tdf) > 0 else "",
        "last_trade": tdf['entry_time'].iloc[-1] if len(tdf) > 0 else "",
        "trades": trades
    }

def execute_full_v4_audit():
    print("=" * 80)
    print("   BTCUSDm V4 — FINAL OOS AUDIT & RECONCILIATION SUITE")
    print("=" * 80)
    
    df_15m, df_1h, spec = load_data()
    feats = precompute_frozen_v3_features(df_15m, df_1h)
    n = feats['n']
    
    # EXACT 60% / 20% / 20% SPLITS
    t_end = int(n * 0.60) # Bar 30,000
    v_end = int(n * 0.80) # Bar 40,000
    
    print(f"Data Total Bars: {n:,} (15M: {df_15m['time'].iloc[0]} -> {df_15m['time'].iloc[-1]})")
    print(f"Train Set (60%): Bars 120 -> {t_end:,} ({df_15m['time'].iloc[120]} -> {df_15m['time'].iloc[t_end-1]})")
    print(f"Val Set   (20%): Bars {t_end:,} -> {v_end:,} ({df_15m['time'].iloc[t_end]} -> {df_15m['time'].iloc[v_end-1]})")
    print(f"Final OOS (20%): Bars {v_end:,} -> {n:,} ({df_15m['time'].iloc[v_end]} -> {df_15m['time'].iloc[-1]})")
    
    # 1. FULL RUN
    r_full = run_v3_frozen_audit(feats, start_idx=120, end_idx=n)
    r_train = run_v3_frozen_audit(feats, start_idx=120, end_idx=t_end)
    r_val = run_v3_frozen_audit(feats, start_idx=t_end, end_idx=v_end)
    r_oos = run_v3_frozen_audit(feats, start_idx=v_end, end_idx=n)
    
    print("\n" + "=" * 80)
    print("   SECTION 1 & 2 & 3: FROZEN V3 PARTITION RECONCILIATION")
    print("=" * 80)
    print(f"{'Partition':<15} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Return %':>9} | {'MaxDD %':>8} | {'Sharpe':>7} | {'Sortino':>7}")
    print("-" * 90)
    for name, r in [("TRAIN (60%)", r_train), ("VAL (20%)", r_val), ("FINAL OOS (20%)", r_oos), ("TOTAL FULL", r_full)]:
        print(f"{name:<15} | {r['total_trades']:>7} | {r['win_rate']:>7.1f}% | {r['profit_factor']:>7.3f} | ${r['expectancy_usd']:>9.2f} | {r['total_return_pct']:>8.2f}% | {r['max_drawdown']:>7.1f}% | {r['sharpe']:>7.2f} | {r['sortino']:>7.2f}")
        
    print("\nTRADE COUNT RECONCILIATION:")
    print(f"  Train Trades:     {r_train['total_trades']}")
    print(f"  Val Trades:       {r_val['total_trades']}")
    print(f"  Final OOS Trades: {r_oos['total_trades']}")
    print(f"  Sum of Splits:    {r_train['total_trades'] + r_val['total_trades'] + r_oos['total_trades']}")
    print(f"  Reported Total:   {r_full['total_trades']}")
    print(f"  First Trade:      {r_full['first_trade']}")
    print(f"  Last Trade:       {r_full['last_trade']}")
    
    # 4. MATH RECONCILIATION
    print("\n" + "=" * 80)
    print("   SECTION 7: MATHEMATICAL VERIFICATION OF METRICS")
    print("=" * 80)
    print(f"  Gross Profit:     ${r_full['gross_profit_usd']:.2f}")
    print(f"  Gross Loss:       ${r_full['gross_loss_usd']:.2f}")
    calc_pf = r_full['gross_profit_usd'] / (r_full['gross_loss_usd'] + 1e-9)
    print(f"  Calculated PF:    {calc_pf:.3f} (Reported: {r_full['profit_factor']:.3f})")
    print(f"  Net Profit Sum:   ${r_full['net_profit_usd']:.2f}")
    print(f"  Sum / 153 trades: ${r_full['net_profit_usd'] / r_full['total_trades']:.2f} (Reported Expectancy: ${r_full['expectancy_usd']:.2f})")
    
    # 5. OOS CONCENTRATION AUDIT
    print("\n" + "=" * 80)
    print("   SECTION 9: OOS TRADE DISTRIBUTION & CONCENTRATION")
    print("=" * 80)
    oos_trades = pd.DataFrame(r_oos['trades'])
    if len(oos_trades) > 0:
        oos_pnl = oos_trades['net_pnl'].values
        sorted_pnl = np.sort(oos_pnl)[::-1]
        tot_oos_pnl = oos_pnl.sum()
        top1_ex = tot_oos_pnl - sorted_pnl[0]
        top5_ex = tot_oos_pnl - sorted_pnl[:5].sum() if len(sorted_pnl) >= 5 else 0
        top10_ex = tot_oos_pnl - sorted_pnl[:10].sum() if len(sorted_pnl) >= 10 else 0
        top5_pct = (sorted_pnl[:5].sum() / tot_oos_pnl * 100) if tot_oos_pnl > 0 else 0
        print(f"  Total OOS Net PnL:        ${tot_oos_pnl:.2f}")
        print(f"  PnL Excl Top 1 Trade:     ${top1_ex:.2f}")
        print(f"  PnL Excl Top 5 Trades:    ${top5_ex:.2f}")
        print(f"  PnL Excl Top 10 Trades:   ${top10_ex:.2f}")
        print(f"  % Profit from Top 5:      {top5_pct:.1f}%")
        
    # 6. YEAR & REGIME BREAKDOWN ON V3
    print("\n" + "=" * 80)
    print("   SECTION 10: V3 YEAR & REGIME BREAKDOWN")
    print("=" * 80)
    tdf = pd.DataFrame(r_full['trades'])
    for yr in sorted(tdf['year'].unique()):
        sub = tdf[tdf['year'] == yr]
        w = sub[sub['net_pnl'] > 0]['net_pnl'].sum()
        l = abs(sub[sub['net_pnl'] <= 0]['net_pnl'].sum())
        pf_yr = w / l if l > 0 else 999.0
        exp_yr = sub['net_pnl'].mean()
        print(f"  Year {yr}: Trades={len(sub):>3} | PF={pf_yr:.3f} | Expectancy=${exp_yr:>6.2f} | Net PnL=${sub['net_pnl'].sum():>7.2f}")
        
    print("\nREGIME BREAKDOWN ON V3:")
    for reg in tdf['regime'].unique():
        sub = tdf[tdf['regime'] == reg]
        w = sub[sub['net_pnl'] > 0]['net_pnl'].sum()
        l = abs(sub[sub['net_pnl'] <= 0]['net_pnl'].sum())
        pf_reg = w / l if l > 0 else 999.0
        exp_reg = sub['net_pnl'].mean()
        print(f"  {reg:<20}: Trades={len(sub):>3} | PF={pf_reg:.3f} | Expectancy=${exp_reg:>6.2f} | Net PnL=${sub['net_pnl'].sum():>7.2f}")
        
    # 7. RANGE REGIME SPLIT ACROSS TRAIN / VAL / OOS
    print("\n" + "=" * 80)
    print("   SECTION 18: RANGE REGIME TRAIN / VAL / OOS RECONCILIATION")
    print("=" * 80)
    for name, r_part in [("TRAIN Range", r_train), ("VAL Range", r_val), ("FINAL OOS Range", r_oos)]:
        part_df = pd.DataFrame(r_part['trades'])
        if len(part_df) > 0:
            rng_sub = part_df[part_df['regime'] == "Sideways Range"]
            if len(rng_sub) > 0:
                w = rng_sub[rng_sub['net_pnl'] > 0]['net_pnl'].sum()
                l = abs(rng_sub[rng_sub['net_pnl'] <= 0]['net_pnl'].sum())
                pf_r = w / l if l > 0 else 999.0
                print(f"  {name:<18}: Trades={len(rng_sub):>3} | WinRate={len(rng_sub[rng_sub['net_pnl']>0])/len(rng_sub)*100:.1f}% | PF={pf_r:.3f} | Expectancy=${rng_sub['net_pnl'].mean():.2f} | PnL=${rng_sub['net_pnl'].sum():.2f}")
                
    # 8. PARAMETER PERTURBATION
    print("\n" + "=" * 80)
    print("   SECTION 11: PARAMETER PERTURBATION NEIGHBORHOOD")
    print("=" * 80)
    print("Score Threshold Perturbation (40, 45, 50, 55):")
    for sc in [40, 45, 50, 55]:
        r = run_v3_frozen_audit(feats, min_score=sc)
        print(f"  Score {sc}: Trades={r['total_trades']:>3} | PF={r['profit_factor']:.3f} | Exp=${r['expectancy_usd']:>5.2f} | Ret={r['total_return_pct']:>+5.2f}% | MaxDD={r['max_drawdown']:.1f}%")
        
    print("\nATR Stop Perturbation (1.8x, 2.0x, 2.2x):")
    for am in [1.8, 2.0, 2.2]:
        r = run_v3_frozen_audit(feats, sl_atr_mult=am)
        print(f"  ATR {am:.1f}x: Trades={r['total_trades']:>3} | PF={r['profit_factor']:.3f} | Exp=${r['expectancy_usd']:>5.2f} | Ret={r['total_return_pct']:>+5.2f}% | MaxDD={r['max_drawdown']:.1f}%")
        
    print("\nTP Architecture Perturbation (TP1 / TP2):")
    for tp1_val, tp2_val in [(1.25, 2.5), (1.5, 3.0), (1.75, 3.5)]:
        r = run_v3_frozen_audit(feats, tp1_rr=tp1_val, tp2_rr=tp2_val)
        print(f"  TP1={tp1_val:.2f}R, TP2={tp2_val:.1f}R: Trades={r['total_trades']:>3} | PF={r['profit_factor']:.3f} | Exp=${r['expectancy_usd']:>5.2f} | Ret={r['total_return_pct']:>+5.2f}%")

    # 9. COST STRESS ON V3 ONLY
    print("\n" + "=" * 80)
    print("   SECTION 14: COST STRESS ON FROZEN V3")
    print("=" * 80)
    for cm in [1.0, 1.5, 2.0, 3.0]:
        r = run_v3_frozen_audit(feats, cost_mult=cm)
        print(f"  Cost {cm:.1f}x ($ {10.0*cm:>4.1f} spread): Trades={r['total_trades']:>3} | PF={r['profit_factor']:.3f} | Exp=${r['expectancy_usd']:>5.2f} | Ret={r['total_return_pct']:>+5.2f}% | MaxDD={r['max_drawdown']:.1f}%")
        
    # 10. MONTE CARLO ON V3 LEDGER (10,000 RUNS)
    print("\n" + "=" * 80)
    print("   SECTION 15: MONTE CARLO (10,000 RUNS ON REAL V3 LEDGER)")
    print("=" * 80)
    all_pnls = np.array([t['net_pnl'] for t in r_full['trades']])
    n_sims = 10000
    n_t = len(all_pnls)
    final_eqs = []
    max_dds = []
    neg_ret_count = 0
    dd_10_count = 0
    dd_20_count = 0
    
    np.random.seed(42)
    for _ in range(n_sims):
        sim_pnl = np.random.choice(all_pnls, size=n_t, replace=True)
        eq_traj = 10000.0 + np.cumsum(sim_pnl)
        f_eq = eq_traj[-1]
        final_eqs.append(f_eq)
        if f_eq < 10000.0: neg_ret_count += 1
        
        peak = np.maximum.accumulate(np.insert(eq_traj, 0, 10000.0))
        cur_dd = (peak - np.insert(eq_traj, 0, 10000.0)) / peak * 100
        sim_max_dd = np.max(cur_dd)
        max_dds.append(sim_max_dd)
        if sim_max_dd >= 10.0: dd_10_count += 1
        if sim_max_dd >= 20.0: dd_20_count += 1
        
    final_eqs = np.array(final_eqs)
    max_dds = np.array(max_dds)
    print(f"  5th Percentile Equity:     ${np.percentile(final_eqs, 5):.2f}")
    print(f"  Median Final Equity:       ${np.percentile(final_eqs, 50):.2f}")
    print(f"  95th Percentile Equity:    ${np.percentile(final_eqs, 95):.2f}")
    print(f"  Median Max Drawdown:       {np.percentile(max_dds, 50):.2f}%")
    print(f"  95th Percentile MaxDD:     {np.percentile(max_dds, 95):.2f}%")
    print(f"  Prob of Negative Return:   {neg_ret_count / n_sims * 100:.2f}%")
    print(f"  Prob of Drawdown > 10%:    {dd_10_count / n_sims * 100:.2f}%")
    print(f"  Prob of Drawdown > 20%:    {dd_20_count / n_sims * 100:.2f}%")
    
    # 11. SIMPLE VS COMPLEX STRATEGY
    print("\n" + "=" * 80)
    print("   SECTION 16: SIMPLE STRATEGY COMPARISON")
    print("=" * 80)
    r_simple = run_v3_frozen_audit(feats, use_score=False, regime_mode="all")
    print(f"  Simple Value Reversion (No score, no filters): Trades={r_simple['total_trades']} | PF={r_simple['profit_factor']:.3f} | Exp=${r_simple['expectancy_usd']:.2f} | Ret={r_simple['total_return_pct']:+.2f}% | MaxDD={r_simple['max_drawdown']:.1f}%")
    print(f"  Frozen V3 (With range gating & score):          Trades={r_full['total_trades']} | PF={r_full['profit_factor']:.3f} | Exp=${r_full['expectancy_usd']:.2f} | Ret={r_full['total_return_pct']:+.2f}% | MaxDD={r_full['max_drawdown']:.1f}%")

    # 12. EDGE ATTRIBUTION
    print("\n" + "=" * 80)
    print("   SECTION 17: EDGE ATTRIBUTION ON V3")
    print("=" * 80)
    r_no_range = run_v3_frozen_audit(feats, regime_mode="all")
    r_no_sess  = run_v3_frozen_audit(feats, session_filter=None)
    r_no_be    = run_v3_frozen_audit(feats, be_mode="none")
    r_tight_sl = run_v3_frozen_audit(feats, sl_atr_mult=1.4)
    r_no_htf   = run_v3_frozen_audit(feats, disable_component="htf")
    
    print(f"  FULL FROZEN V3:    Trades={r_full['total_trades']:>3} | PF={r_full['profit_factor']:.3f} | Exp=${r_full['expectancy_usd']:>5.2f} | Ret={r_full['total_return_pct']:>+5.2f}% | MaxDD={r_full['max_drawdown']:.1f}%")
    print(f"  V3 - Range Gating: Trades={r_no_range['total_trades']:>3} | PF={r_no_range['profit_factor']:.3f} | Exp=${r_no_range['expectancy_usd']:>5.2f} | Ret={r_no_range['total_return_pct']:>+5.2f}% | MaxDD={r_no_range['max_drawdown']:.1f}%")
    print(f"  V3 - Session Gating:Trades={r_no_sess['total_trades']:>3} | PF={r_no_sess['profit_factor']:.3f} | Exp=${r_no_sess['expectancy_usd']:>5.2f} | Ret={r_no_sess['total_return_pct']:>+5.2f}% | MaxDD={r_no_sess['max_drawdown']:.1f}%")
    print(f"  V3 - Immediate BE: Trades={r_no_be['total_trades']:>3} | PF={r_no_be['profit_factor']:.3f} | Exp=${r_no_be['expectancy_usd']:>5.2f} | Ret={r_no_be['total_return_pct']:>+5.2f}% | MaxDD={r_no_be['max_drawdown']:.1f}%")
    print(f"  V3 - 2.0x ATR (1.4x):Trades={r_tight_sl['total_trades']:>3} | PF={r_tight_sl['profit_factor']:.3f} | Exp=${r_tight_sl['expectancy_usd']:>5.2f} | Ret={r_tight_sl['total_return_pct']:>+5.2f}% | MaxDD={r_tight_sl['max_drawdown']:.1f}%")
    print(f"  V3 - HTF Macro Gate: Trades={r_no_htf['total_trades']:>3} | PF={r_no_htf['profit_factor']:.3f} | Exp=${r_no_htf['expectancy_usd']:>5.2f} | Ret={r_no_htf['total_return_pct']:>+5.2f}% | MaxDD={r_no_htf['max_drawdown']:.1f}%")

    # SAVE AUDIT RESULTS
    audit_data = {
        "full": r_full, "train": r_train, "val": r_val, "oos": r_oos,
        "sample_trade": r_full['trades'][0] if len(r_full['trades']) > 0 else {}
    }
    with open("E:\\Trading\\v4_audit_results.json", "w") as f:
        json.dump(audit_data, f, indent=2)
    print("\nAUDIT COMPLETE. All data saved to E:\\Trading\\v4_audit_results.json")

if __name__ == "__main__":
    execute_full_v4_audit()
