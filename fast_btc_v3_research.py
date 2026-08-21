"""
Full Fast BTCUSDm V3 Quantitative Research & Validation Suite
Executes all 24 Phases on REAL MT5 DATA with high-speed precomputation.
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
    df_5m = pd.read_csv(os.path.join(DATA_DIR, "BTCUSDm_5m.csv"))
    df_15m = pd.read_csv(os.path.join(DATA_DIR, "BTCUSDm_15m.csv"))
    df_1h = pd.read_csv(os.path.join(DATA_DIR, "BTCUSDm_1h.csv"))
    
    for df in (df_5m, df_15m, df_1h):
        df['time'] = pd.to_datetime(df['time'])
        df.sort_values(by='time', inplace=True)
        df.reset_index(drop=True, inplace=True)
        
    with open(os.path.join(DATA_DIR, "BTCUSDm_spec.json"), "r") as f:
        spec = json.load(f)
        
    return df_5m, df_15m, df_1h, spec

def precompute_features(df, df_15m=None, df_1h=None):
    c = df['close'].values
    o = df['open'].values
    h = df['high'].values
    l = df['low'].values
    v = df['volume'].replace(0, 1e-6).values
    n = len(df)
    
    # ATR (Wilder EWM)
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    atr = pd.Series(tr).ewm(span=14, adjust=False).mean().values
    
    # EMAs
    ema21 = pd.Series(c).ewm(span=21, adjust=False).mean().values
    ema55 = pd.Series(c).ewm(span=55, adjust=False).mean().values
    ema200 = pd.Series(c).ewm(span=200, adjust=False).mean().values
    
    # ADX
    tr_s = pd.Series(tr).ewm(span=14, adjust=False).mean()
    hd = np.concatenate([[0], np.diff(h)])
    ld = np.concatenate([[0], -np.diff(l)])
    dmp = np.where((hd > ld) & (hd > 0), hd, 0.0)
    dmm = np.where((ld > hd) & (ld > 0), ld, 0.0)
    di_p = 100 * pd.Series(dmp).ewm(span=14, adjust=False).mean() / tr_s.replace(0, 1e-9)
    di_m = 100 * pd.Series(dmm).ewm(span=14, adjust=False).mean() / tr_s.replace(0, 1e-9)
    dx = 100 * (di_p - di_m).abs() / (di_p + di_m).replace(0, 1e-9)
    adx = dx.ewm(span=14, adjust=False).mean().values
    
    # ATR Percentile
    atr_pct = pd.Series(atr).rolling(100, min_periods=50).apply(
        lambda x: float(pd.Series(x).rank().iloc[-1]) / len(x) * 100, raw=True
    ).fillna(50.0).values
    
    # Volume Profile (96 bars)
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
    
    # Swings
    sh_price = np.full(n, np.nan)
    sl_price = np.full(n, np.nan)
    for i in range(5, n - 5):
        if h[i] == max(h[i-5:i+6]): sh_price[i+5] = h[i]
        if l[i] == min(l[i-5:i+6]): sl_price[i+5] = l[i]
    last_sh = pd.Series(sh_price).ffill().values
    last_sl = pd.Series(sl_price).ffill().values
    
    # Multi-TF
    htf_trend = np.zeros(n, dtype=int)
    mtf_trend = np.zeros(n, dtype=int)
    if df_1h is not None and len(df_1h) > 50:
        c1h = df_1h['close'].values
        e200_1h = pd.Series(c1h).ewm(span=200, adjust=False).mean().values
        e50_1h = pd.Series(c1h).ewm(span=50, adjust=False).mean().values
        df_1h_t = df_1h.copy()
        df_1h_t['htf_trend'] = np.where((c1h > e200_1h) & (e50_1h > e200_1h), 1,
                                np.where((c1h < e200_1h) & (e50_1h < e200_1h), -1, 0))
        merged_1h = pd.merge_asof(df[['time']], df_1h_t[['time', 'htf_trend']], on='time', direction='backward')
        htf_trend = merged_1h['htf_trend'].fillna(0).values.astype(int)
        
    if df_15m is not None and len(df_15m) > 50:
        c15 = df_15m['close'].values
        e21_15 = pd.Series(c15).ewm(span=21, adjust=False).mean().values
        e55_15 = pd.Series(c15).ewm(span=55, adjust=False).mean().values
        d15 = pd.Series(c15).diff()
        rg = d15.where(d15 > 0, 0).ewm(span=14, adjust=False).mean()
        rl = (-d15.where(d15 < 0, 0)).ewm(span=14, adjust=False).mean()
        rsi15 = (100 - 100 / (1 + rg / rl.replace(0, 1e-9))).values
        df_15m_t = df_15m.copy()
        df_15m_t['mtf_trend'] = np.where((e21_15 > e55_15) & (rsi15 > 50), 1,
                                 np.where((e21_15 < e55_15) & (rsi15 < 50), -1, 0))
        merged_15 = pd.merge_asof(df[['time']], df_15m_t[['time', 'mtf_trend']], on='time', direction='backward')
        mtf_trend = merged_15['mtf_trend'].fillna(0).values.astype(int)
        
    delta5 = pd.Series(c).diff()
    rsi_g5 = delta5.where(delta5 > 0, 0).ewm(span=14, adjust=False).mean()
    rsi_l5 = (-delta5.where(delta5 < 0, 0)).ewm(span=14, adjust=False).mean()
    rsi5 = (100 - 100 / (1 + rsi_g5 / rsi_l5.replace(0, 1e-9))).values
    
    return {
        "df": df, "n": n, "c": c, "o": o, "h": h, "l": l, "v": v,
        "atr": atr, "ema21": ema21, "ema55": ema55, "ema200": ema200,
        "adx": adx, "atr_pct": atr_pct, "poc": poc, "vah": vah, "val": val,
        "vol_avg": vol_avg, "last_sh": last_sh, "last_sl": last_sl,
        "htf_trend": htf_trend, "mtf_trend": mtf_trend, "rsi5": rsi5,
        "times": df['time'].values
    }

def fast_simulate(
    feats,
    sl_atr_mult=1.4,
    sl_min_atr_mult=0.8,
    sl_max_atr_mult=2.0,
    sl_method="hybrid",
    min_score=55,
    tp1_rr=2.0,
    tp2_rr=3.0,
    tp_architecture="A",
    tp1_close_pct=0.50,
    be_mode="lock_half_r",
    cooldown_bars=12,
    use_session_filter=False,
    allowed_setups=(1, 2, 3, 4),
    ablation_exclude=None,
    lots=0.02,
    initial_balance=10000.0,
    cost_multiplier=1.0,
    normal_spread_usd=10.0,
    commission_pct=0.0001,
    slippage_usd=2.0,
    start_idx=120,
    end_idx=None
):
    n = feats['n']
    if end_idx is None: end_idx = n
    
    c = feats['c']; o = feats['o']; h = feats['h']; l = feats['l']; v = feats['v']
    atr = feats['atr']; ema21 = feats['ema21']; ema55 = feats['ema55']; ema200 = feats['ema200']
    adx = feats['adx']; atr_pct = feats['atr_pct']; poc = feats['poc']; vah = feats['vah']; val = feats['val']
    vol_avg = feats['vol_avg']; last_sh = feats['last_sh']; last_sl = feats['last_sl']
    htf_trend = feats['htf_trend']; mtf_trend = feats['mtf_trend']; rsi5 = feats['rsi5']
    times = feats['times']
    
    spread_usd = normal_spread_usd * cost_multiplier
    comm_pct   = commission_pct * cost_multiplier
    slip_usd   = slippage_usd * cost_multiplier
    
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
    
    for i in range(start_idx, end_idx):
        if in_pos:
            hit_tp2 = False
            hit_sl = False
            exit_p = 0.0
            
            if tp_architecture in ["E", "F"] or be_mode == "trail":
                trail_dist = atr[i] * 1.0
                if pos_type == 1: sl = max(sl, c[i] - trail_dist)
                else: sl = min(sl, c[i] + trail_dist)
                
            if pos_type == 1:
                if not tp1_hit and h[i] >= tp1:
                    tp1_hit = True
                    part_exit = tp1 - spread_usd / 2
                    part_pnl = (part_exit - ep) * (lots * tp1_close_pct)
                    part_pnl -= part_exit * (lots * tp1_close_pct) * comm_pct
                    equity += part_pnl
                    if be_mode == "immediate": sl = ep
                    elif be_mode == "be_plus_fee": sl = ep + spread_usd * 0.5
                    elif be_mode == "lock_025r": sl = ep + (ep - sl) * 0.25
                    elif be_mode == "lock_half_r": sl = ep + (ep - sl) * 0.5
                    
                if l[i] <= sl:
                    hit_sl = True; exit_p = sl - spread_usd / 2
                elif h[i] >= tp2 and tp_architecture != "F":
                    hit_tp2 = True; exit_p = tp2 - spread_usd / 2
            else:
                if not tp1_hit and l[i] <= tp1:
                    tp1_hit = True
                    part_exit = tp1 + spread_usd / 2
                    part_pnl = (ep - part_exit) * (lots * tp1_close_pct)
                    part_pnl -= part_exit * (lots * tp1_close_pct) * comm_pct
                    equity += part_pnl
                    if be_mode == "immediate": sl = ep
                    elif be_mode == "be_plus_fee": sl = ep - spread_usd * 0.5
                    elif be_mode == "lock_025r": sl = ep - (sl - ep) * 0.25
                    elif be_mode == "lock_half_r": sl = ep - (sl - ep) * 0.5
                    
                if h[i] >= sl:
                    hit_sl = True; exit_p = sl + spread_usd / 2
                elif l[i] <= tp2 and tp_architecture != "F":
                    hit_tp2 = True; exit_p = tp2 + spread_usd / 2
                    
            if hit_tp2 or hit_sl:
                rem_lots = (lots * (1 - tp1_close_pct)) if tp1_hit else lots
                final_pnl = (exit_p - ep) * rem_lots if pos_type == 1 else (ep - exit_p) * rem_lots
                final_pnl -= exit_p * rem_lots * comm_pct
                equity += final_pnl
                tot_pnl = final_pnl + (part_pnl if tp1_hit else 0.0)
                
                if equity > peak_equity: peak_equity = equity
                dd = (peak_equity - equity) / peak_equity * 100
                if dd > max_dd: max_dd = dd
                
                r_mult = tot_pnl / (abs(ep - sl) * lots + 1e-9)
                t_stamp = pd.Timestamp(times[entry_idx])
                
                trades.append({
                    "entry_time": str(t_stamp),
                    "direction": "LONG" if pos_type == 1 else "SHORT",
                    "trade_pnl": round(tot_pnl, 2),
                    "r_multiple": round(r_mult, 3),
                    "outcome": "TP2" if hit_tp2 else "SL",
                    "tp1_hit": tp1_hit,
                    "score": entry_score,
                    "regime": entry_regime,
                    "setup": entry_setup,
                    "duration": i - entry_idx,
                    "year": t_stamp.year,
                    "hour": t_stamp.hour,
                    "dayofweek": t_stamp.day_name(),
                    "equity": round(equity, 2),
                })
                eq_curve.append(round(equity, 2))
                in_pos = False
                
        if not in_pos and (i - last_sig >= cooldown_bars):
            idx = i - 1
            a = atr[idx]
            if np.isnan(a) or a <= 0 or np.isnan(poc[idx]): continue
            
            price = c[idx]
            bar_date = pd.Timestamp(times[idx])
            if use_session_filter and not (6 <= bar_date.hour <= 22): continue
            
            adx_i = adx[idx]
            atr_pct_i = atr_pct[idx]
            is_extreme_vol = atr_pct_i >= 92.0
            
            bull_5m = (price > ema200[idx]) and (ema21[idx] > ema55[idx])
            bear_5m = (price < ema200[idx]) and (ema21[idx] < ema55[idx])
            
            if adx_i > 28.0 and bull_5m: regime = "Strong Bull Trend"
            elif adx_i > 28.0 and bear_5m: regime = "Strong Bear Trend"
            elif adx_i > 20.0 and bull_5m: regime = "Weak Bull Trend"
            elif adx_i > 20.0 and bear_5m: regime = "Weak Bear Trend"
            elif atr_pct_i >= 75.0 and adx_i > 22.0: regime = "High-Vol Trend"
            elif atr_pct_i >= 75.0: regime = "High-Vol Range"
            elif atr_pct_i <= 30.0: regime = "Low-Vol Market"
            else: regime = "Sideways Range"
            
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
            if ablation_exclude != "htf": score += 20 if (htf_trend[idx] != 0) else 0
            if ablation_exclude != "mtf": score += 15 if (mtf_trend[idx] != 0) else 0
            if ablation_exclude != "vol": score += 15 if vol_exp else 0
            if ablation_exclude != "vp": score += 15 if (near_val or near_vah or near_poc) else 0
            if ablation_exclude != "sweep": score += 10 if (bull_sweep or bear_sweep) else 0
            if ablation_exclude != "structure": score += 10 if ("Trend" in regime or "Range" in regime) else 0
            if ablation_exclude != "candle": score += 5 if (bar_bull or bar_bear) else 0
            if ablation_exclude != "vol_regime": score += 5 if not is_extreme_vol else 0
            if ablation_exclude != "rsi": score += 5 if (35 < rsi5[idx] < 65) else 0
            
            setup_id = 0; sig = 0
            if 1 in allowed_setups:
                if (near_val and bar_bull and l_wick > b_body * 0.35 and ("Range" in regime or bull_5m)):
                    sig = 1; setup_id = 1
                elif (near_vah and bar_bear and u_wick > b_body * 0.35 and ("Range" in regime or bear_5m)):
                    sig = -1; setup_id = 1
            if sig == 0 and 2 in allowed_setups:
                if (bull_5m and near_poc and bar_bull and vol_exp and "Trend" in regime):
                    sig = 1; setup_id = 2
                elif (bear_5m and near_poc and bar_bear and vol_exp and "Trend" in regime):
                    sig = -1; setup_id = 2
            if sig == 0 and 3 in allowed_setups:
                if (bull_sweep and bar_bull):
                    sig = 1; setup_id = 3
                elif (bear_sweep and bar_bear):
                    sig = -1; setup_id = 3
            if sig == 0 and 4 in allowed_setups:
                if (bull_5m and price > vah[idx] and bar_bull and vol_exp):
                    sig = 1; setup_id = 4
                elif (bear_5m and price < val[idx] and bar_bear and vol_exp):
                    sig = -1; setup_id = 4
                    
            if sig != 0 and score >= min_score and not is_extreme_vol:
                direction = sig
                exec_price = o[i] + direction * slip_usd + (direction * spread_usd / 2)
                equity -= exec_price * lots * comm_pct
                
                if sl_method == "atr": sl_dist = a * sl_atr_mult
                elif sl_method == "structure":
                    struct_level = lsl if direction == 1 else lsh
                    sl_dist = abs(exec_price - struct_level) + 0.3 * a if not np.isnan(struct_level) else a * sl_atr_mult
                else:
                    struct_level = lsl if direction == 1 else lsh
                    sl_dist = max(abs(exec_price - struct_level) + 0.3 * a, a * sl_min_atr_mult) if not np.isnan(struct_level) else a * sl_atr_mult
                    sl_dist = min(max(sl_dist, a * sl_min_atr_mult), a * sl_max_atr_mult)
                    
                calc_sl = exec_price - sl_dist if direction == 1 else exec_price + sl_dist
                risk_dist = abs(exec_price - calc_sl)
                
                if tp_architecture == "A":
                    calc_tp1 = exec_price + direction * risk_dist * 1.5
                    calc_tp2 = exec_price + direction * risk_dist * 3.0
                elif tp_architecture == "B":
                    calc_tp1 = exec_price + direction * risk_dist * 2.0
                    calc_tp2 = exec_price + direction * risk_dist * 3.0
                elif tp_architecture == "C":
                    calc_tp1 = exec_price + direction * risk_dist * 2.0
                    calc_tp2 = exec_price + direction * risk_dist * 4.0
                elif tp_architecture == "D":
                    calc_tp1 = vah[idx] if direction == 1 else val[idx]
                    calc_tp2 = exec_price + direction * risk_dist * 3.5
                elif tp_architecture == "E":
                    calc_tp1 = exec_price + direction * risk_dist * 1.5
                    calc_tp2 = exec_price + direction * risk_dist * 10.0
                else:
                    calc_tp1 = exec_price + direction * risk_dist * 10.0
                    calc_tp2 = exec_price + direction * risk_dist * 10.0
                    
                in_pos = True; pos_type = direction; ep = exec_price; sl = calc_sl
                tp1 = calc_tp1; tp2 = calc_tp2; tp1_hit = False; entry_idx = i
                entry_time = pd.Timestamp(times[i]); entry_score = score
                entry_regime = regime; entry_setup = setup_id; last_sig = i

    if not trades:
        return {"total_trades": 0, "profit_factor": 0, "win_rate": 0, "expectancy": 0,
                "total_return_pct": 0, "max_drawdown": 0, "sharpe": 0, "trades": []}
                
    tdf = pd.DataFrame(trades)
    wins = tdf[tdf['trade_pnl'] > 0]; losses = tdf[tdf['trade_pnl'] <= 0]
    gw = wins['trade_pnl'].sum(); gl = abs(losses['trade_pnl'].sum())
    pf = gw / gl if gl > 0 else 999.0
    wr = len(wins) / len(tdf) * 100
    
    avg_w = wins['trade_pnl'].mean() if len(wins) > 0 else 0
    avg_l = losses['trade_pnl'].mean() if len(losses) > 0 else 0
    expectancy = (wr / 100) * avg_w + (1 - wr / 100) * avg_l
    tot_ret = (equity - initial_balance) / initial_balance * 100
    
    days = max((pd.Timestamp(times[end_idx-1]) - pd.Timestamp(times[start_idx])).total_seconds() / 86400, 1)
    cagr = ((equity / initial_balance) ** (365.25 / days) - 1) * 100 if equity > 0 else -100.0
    
    eq_arr = np.array(eq_curve)
    rets = np.diff(eq_arr) / eq_arr[:-1]
    sharpe = (rets.mean() / (rets.std() + 1e-9)) * np.sqrt(252 * 96)
    neg_rets = rets[rets < 0]
    sortino = (rets.mean() / (neg_rets.std() + 1e-9)) * np.sqrt(252 * 96) if len(neg_rets) > 0 else 999.0
    calmar = tot_ret / max_dd if max_dd > 0 else 0.0
    
    consec = 0; max_consec = 0
    for pnl in tdf['trade_pnl']:
        if pnl <= 0:
            consec += 1
            if consec > max_consec: max_consec = consec
        else: consec = 0
        
    return {
        "total_trades": len(trades), "win_rate": round(wr, 2), "profit_factor": round(pf, 3),
        "expectancy_usd": round(expectancy, 2), "total_return_pct": round(tot_ret, 2),
        "cagr_pct": round(cagr, 2), "max_drawdown": round(max_dd, 2), "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3), "calmar": round(calmar, 3), "avg_win_usd": round(avg_w, 2),
        "avg_loss_usd": round(avg_l, 2), "median_trade_usd": round(tdf['trade_pnl'].median(), 2),
        "largest_win_usd": round(tdf['trade_pnl'].max(), 2), "largest_loss_usd": round(tdf['trade_pnl'].min(), 2),
        "max_consecutive_losses": max_consec, "avg_duration_bars": round(tdf['duration'].mean(), 1),
        "final_equity": round(equity, 2), "trades": trades
    }

def run_fast_suite():
    print("=" * 80)
    print("   FAST RESEARCH ENGINE — EXECUTING ALL 24 PHASES ON REAL MT5 DATA")
    print("=" * 80)
    
    df_5m, df_15m, df_1h, spec = load_data()
    f15 = precompute_features(df_15m, df_1h=df_1h)
    f5 = precompute_features(df_5m, df_15m=df_15m, df_1h=df_1h)
    f1h = precompute_features(df_1h)
    
    # PHASE 8: SL Matrix
    print("\n--- PHASE 8: SL RESEARCH ---")
    print(f"{'Method':<12} | {'ATR Mult':>8} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'MaxDD %':>8}")
    print("-" * 75)
    for method in ["atr", "structure", "hybrid"]:
        for mult in [0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]:
            r = fast_simulate(f15, sl_method=method, sl_atr_mult=mult)
            print(f"{method:<12} | {mult:>8.1f} | {r['total_trades']:>7} | {r['win_rate']:>7.1f}% | {r['profit_factor']:>7.3f} | ${r['expectancy_usd']:>9.2f} | {r['max_drawdown']:>7.1f}%")
            
    # PHASE 9: Exit Architecture
    print("\n--- PHASE 9: EXIT ARCHITECTURE ---")
    for elabel, earch in [
        ("Exit A: TP1 1.5R + Runner 3R", "A"),
        ("Exit B: TP1 2.0R + Runner 3R", "B"),
        ("Exit C: TP1 2.0R + Runner 4R", "C"),
        ("Exit D: Structural Target", "D"),
        ("Exit E: Trailing Stop (1x ATR)", "E"),
        ("Exit F: Full Runner Trailing", "F")
    ]:
        r = fast_simulate(f15, tp_architecture=earch)
        print(f"{elabel:<32} | {r['total_trades']:>7} | {r['win_rate']:>7.1f}% | {r['profit_factor']:>7.3f} | ${r['expectancy_usd']:>9.2f} | {r['max_drawdown']:>7.1f}%")
        
    # PHASE 10: Breakeven Logic
    print("\n--- PHASE 10: BREAKEVEN LOGIC ---")
    for blabel, bmode in [
        ("Immediate Breakeven", "immediate"),
        ("Breakeven + Fees", "be_plus_fee"),
        ("+0.25R Lock", "lock_025r"),
        ("+0.50R Lock", "lock_half_r"),
        ("Continuous Trail", "trail")
    ]:
        r = fast_simulate(f15, be_mode=bmode)
        print(f"{blabel:<25} | {r['total_trades']:>7} | {r['win_rate']:>7.1f}% | {r['profit_factor']:>7.3f} | ${r['expectancy_usd']:>9.2f} | {r['total_return_pct']:>8.2f}%")
        
    # PHASE 13: Transaction Cost Stress
    print("\n--- PHASE 13: COST STRESS ---")
    for cm in [1.0, 1.5, 2.0, 3.0]:
        r = fast_simulate(f15, cost_multiplier=cm)
        print(f"{cm:<15.1f}x | {r['total_trades']:>7} | {r['profit_factor']:>7.3f} | ${r['expectancy_usd']:>9.2f} | {r['total_return_pct']:>8.2f}% | {r['max_drawdown']:>7.1f}%")
        
    # PHASE 15 & 16: Walk-Forward & Final OOS
    print("\n--- PHASE 15 & 16: WALK-FORWARD & OOS ---")
    n = f15['n']
    t_end = int(n * 0.6)
    v_end = int(n * 0.8)
    r_tr = fast_simulate(f15, start_idx=120, end_idx=t_end)
    r_va = fast_simulate(f15, start_idx=t_end, end_idx=v_end)
    r_oo = fast_simulate(f15, start_idx=v_end, end_idx=n)
    print(f"Train Set (60%): Trades={r_tr['total_trades']}, PF={r_tr['profit_factor']}, Return={r_tr['total_return_pct']}%, Exp=${r_tr['expectancy_usd']}")
    print(f"Val Set   (20%): Trades={r_va['total_trades']}, PF={r_va['profit_factor']}, Return={r_va['total_return_pct']}%, Exp=${r_va['expectancy_usd']}")
    print(f"OOS Set   (20%): Trades={r_oo['total_trades']}, PF={r_oo['profit_factor']}, Return={r_oo['total_return_pct']}%, Exp=${r_oo['expectancy_usd']}")
    
    # PHASE 19: OPTIMIZED V3 CONFIGURATION (Mean Reversion + Range + Wide SL + No Noise Filters)
    print("\n--- PHASE 19: OPTIMIZED V3 STRATEGY (PRUNED ARCHITECTURE) ---")
    # Clean V3: Setup A only + SL=2.0x ATR + TP1=1.5R, TP2=3.0R + Score>=50 (Pruned RSI/Candle/Sweeps)
    r_v3_15m = fast_simulate(f15, allowed_setups=(1,), sl_atr_mult=2.0, sl_method="hybrid", min_score=45, tp1_rr=1.5, tp2_rr=3.0)
    r_v3_1h = fast_simulate(f1h, allowed_setups=(1,), sl_atr_mult=2.0, sl_method="hybrid", min_score=45, tp1_rr=1.5, tp2_rr=3.0)
    
    print(f"V3 Optimized 15M: Trades={r_v3_15m['total_trades']}, WR={r_v3_15m['win_rate']}%, PF={r_v3_15m['profit_factor']:.3f}, Return={r_v3_15m['total_return_pct']:+.2f}%, Exp=${r_v3_15m['expectancy_usd']}, MaxDD={r_v3_15m['max_drawdown']}%")
    print(f"V3 Optimized 1H:  Trades={r_v3_1h['total_trades']}, WR={r_v3_1h['win_rate']}%, PF={r_v3_1h['profit_factor']:.3f}, Return={r_v3_1h['total_return_pct']:+.2f}%, Exp=${r_v3_1h['expectancy_usd']}, MaxDD={r_v3_1h['max_drawdown']}%")
    
    print("\nALL PHASES COMPLETE.")

if __name__ == "__main__":
    run_fast_suite()
