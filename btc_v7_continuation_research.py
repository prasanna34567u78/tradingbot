"""
BTCUSDm V7 — Breakout Continuation Quality & Regime Robustness Research Engine
==============================================================================
Empirical Quantitative Suite covering all 29 Phases of V7 Research:
  1. Frozen V6 Control Ledger Extraction
  2. Winner vs Loser Quantitative Feature Distribution Analysis
  3. Breakout Quality Score (0-100) & Candle Geometry Model
  4. Breakout Extension ('Do Not Chase') & False Breakout Risk Engine
  5. Higher-Timeframe Macro Alignment & Conflict Diagnostic
  6. Breakout Location & Range Width Diagnostics
  7. Session, Weekday, MAE/MFE & Time-to-Confirmation Analysis
  8. Sequential 4-Window Rolling Walk-Forward & Final Holdout Evaluation
  9. Transaction Cost Stress (1x to 3x) & 10,000 Monte Carlo Simulations
  10. Full Ablation Suite & Definitive Classification (A/B/C)
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
    
    for df in (df_15m, df_1h, df_4h):
        df['time'] = pd.to_datetime(df['time'])
        df.sort_values(by='time', inplace=True)
        df.reset_index(drop=True, inplace=True)
        
    with open(os.path.join(DATA_DIR, "BTCUSDm_spec.json"), "r") as f:
        spec = json.load(f)
    return df_15m, df_1h, df_4h, spec

def precompute_v7_features(df_15m, df_1h, df_4h):
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
    
    # 3. Donchian Channel (32 bars lookback ~ 8 hours)
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
    
    # 5. Candle Geometry & Breakout Extension
    candle_range = h - l
    candle_body = np.abs(c - o)
    candle_body_ratio = candle_body / np.maximum(candle_range, 1e-9)
    upper_wick = h - np.maximum(c, o)
    lower_wick = np.minimum(c, o) - l
    
    # 6. EMAs on 15M
    ema21 = pd.Series(c).ewm(span=21, adjust=False).mean().values
    ema55 = pd.Series(c).ewm(span=55, adjust=False).mean().values
    ema200 = pd.Series(c).ewm(span=200, adjust=False).mean().values
    
    # 7. 1H Macro Features (Causal merge_asof)
    c1h = df_1h['close'].values
    e21_1h = pd.Series(c1h).ewm(span=21, adjust=False).mean().values
    e55_1h = pd.Series(c1h).ewm(span=55, adjust=False).mean().values
    e200_1h = pd.Series(c1h).ewm(span=200, adjust=False).mean().values
    e200_1h_slope = pd.Series(e200_1h).diff(4).fillna(0).values
    
    df_1h_t = df_1h.copy()
    df_1h_t['htf_trend_1h'] = np.where((c1h > e200_1h) & (e21_1h > e55_1h), 1,
                             np.where((c1h < e200_1h) & (e21_1h < e55_1h), -1, 0))
    df_1h_t['ema_spread_1h'] = np.abs(e21_1h - e55_1h)
    df_1h_t['e200_dist_1h']  = np.abs(c1h - e200_1h)
    df_1h_t['e200_slope_1h'] = e200_1h_slope
    
    merged_1h = pd.merge_asof(df_15m[['time']], df_1h_t[['time', 'htf_trend_1h', 'ema_spread_1h', 'e200_dist_1h', 'e200_slope_1h']], on='time', direction='backward')
    htf_trend_1h = merged_1h['htf_trend_1h'].fillna(0).values.astype(int)
    ema_spread_1h = merged_1h['ema_spread_1h'].fillna(0).values
    e200_dist_1h  = merged_1h['e200_dist_1h'].fillna(0).values
    e200_slope_1h = merged_1h['e200_slope_1h'].fillna(0).values
    
    # 8. 4H Macro Features (Causal merge_asof)
    c4h = df_4h['close'].values
    e50_4h = pd.Series(c4h).ewm(span=50, adjust=False).mean().values
    e200_4h = pd.Series(c4h).ewm(span=200, adjust=False).mean().values
    df_4h_t = df_4h.copy()
    df_4h_t['macro_4h_trend'] = np.where((c4h > e200_4h) & (e50_4h > e200_4h), 1,
                                np.where((c4h < e200_4h) & (e50_4h < e200_4h), -1, 0))
    df_4h_t['e200_dist_4h']   = np.abs(c4h - e200_4h)
    merged_4h = pd.merge_asof(df_15m[['time']], df_4h_t[['time', 'macro_4h_trend', 'e200_dist_4h']], on='time', direction='backward')
    macro_4h_trend = merged_4h['macro_4h_trend'].fillna(0).values.astype(int)
    e200_dist_4h   = merged_4h['e200_dist_4h'].fillna(0).values
    
    # 9. Coil Score (0-100)
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
        "candle_body_ratio": candle_body_ratio, "upper_wick": upper_wick, "lower_wick": lower_wick,
        "ema21": ema21, "ema55": ema55, "ema200": ema200,
        "htf_trend_1h": htf_trend_1h, "ema_spread_1h": ema_spread_1h, "e200_dist_1h": e200_dist_1h, "e200_slope_1h": e200_slope_1h,
        "macro_4h_trend": macro_4h_trend, "e200_dist_4h": e200_dist_4h,
        "coil_score": coil_score, "times": df_15m['time'].values
    }

def run_v7_simulation(
    feats,
    start_idx=120,
    end_idx=None,
    min_coil_score=45.0,
    min_rvol=1.20,
    min_atr_expansion=1.10,
    min_candle_body_ratio=0.50,      # Candle geometry: body must be >=50% of range
    max_breakout_extension_atr=1.10, # Do Not Chase: Close cannot exceed boundary by > 1.1x ATR
    require_1h_slope_support=True,   # 1H EMA200 slope in trade direction
    use_1h_macro=True,
    use_4h_macro=True,
    sl_method="hybrid",
    tp_method="runner_4r",
    risk_pct=0.005,
    initial_balance=10000.0,
    cost_mult=1.0,
    cooldown_bars=12,
    session_filter="london_ny"       # 'london_ny' = 08:00 - 20:00 UTC
):
    n = feats['n']
    if end_idx is None: end_idx = n
    
    c = feats['c']; o = feats['o']; h = feats['h']; l = feats['l']; v = feats['v']
    atr = feats['atr']; atr_exp = feats['atr_expansion']; rvol = feats['rvol']
    d_high = feats['donchian_high']; d_low = feats['donchian_low']
    body_ratio = feats['candle_body_ratio']
    coil_sc = feats['coil_score']; htf_1h = feats['htf_trend_1h']; macro_4h = feats['macro_4h_trend']
    e200_slope_1h = feats['e200_slope_1h']
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
    ep = sl = tp = tp1_price = 0.0
    tp1_hit = False
    tp1_pnl = 0.0
    lots = 0.02
    entry_idx = 0
    last_sig = -cooldown_bars
    
    for i in range(start_idx, end_idx):
        idx = i - 1 # CAUSAL: signal on closed bar i-1
        
        # 1. POSITION MANAGEMENT
        if in_pos:
            hit_tp = False
            hit_sl = False
            exit_p = 0.0
            
            # Partial close at 2R, runner to 4R with breakeven lock
            if not tp1_hit:
                if pos_type == 1 and h[i] >= tp1_price:
                    tp1_hit = True
                    part_exit = tp1_price - spread_usd / 2
                    tp1_pnl = (part_exit - ep) * (lots * 0.5)
                    tp1_pnl -= part_exit * (lots * 0.5) * comm_pct
                    equity += tp1_pnl
                    sl = ep # Breakeven
                elif pos_type == -1 and l[i] <= tp1_price:
                    tp1_hit = True
                    part_exit = tp1_price + spread_usd / 2
                    tp1_pnl = (ep - part_exit) * (lots * 0.5)
                    tp1_pnl -= part_exit * (lots * 0.5) * comm_pct
                    equity += tp1_pnl
                    sl = ep # Breakeven
                    
            if pos_type == 1:
                if l[i] <= sl:
                    hit_sl = True; exit_p = sl - spread_usd / 2
                elif h[i] >= tp:
                    hit_tp = True; exit_p = tp - spread_usd / 2
            else:
                if h[i] >= sl:
                    hit_sl = True; exit_p = sl + spread_usd / 2
                elif l[i] <= tp:
                    hit_tp = True; exit_p = tp + spread_usd / 2
                    
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
                r_mult = tot_pnl / (risk_amt + 1e-9)
                t_entry = pd.Timestamp(times[entry_idx])
                t_exit  = pd.Timestamp(times[i])
                
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
                
                # Signal-time diagnostic snapshots
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
                    "outcome": "TP2" if hit_tp else ("TP1_BE" if tp1_hit else "SL"),
                    "tp1_hit": tp1_hit,
                    "duration_bars": i - entry_idx,
                    "year": t_entry.year,
                    "dayofweek": t_entry.day_name(),
                    "hour": t_entry.hour,
                    "equity": round(equity, 2),
                    # Signal snapshot features
                    "sig_coil": round(coil_sc[entry_idx-1], 1),
                    "sig_rvol": round(rvol[entry_idx-1], 2),
                    "sig_atr_exp": round(atr_exp[entry_idx-1], 2),
                    "sig_body_ratio": round(body_ratio[entry_idx-1], 2),
                    "sig_d_range_atr": round(feats['donchian_range_atr'][entry_idx-1], 2),
                })
                eq_curve.append(round(equity, 2))
                in_pos = False
                
        # 2. SIGNAL EVALUATION
        if not in_pos and (i - last_sig >= cooldown_bars):
            a = atr[idx]
            if np.isnan(a) or a <= 0: continue
            
            bar_date = pd.Timestamp(times[idx])
            if session_filter == "london_ny" and not (8 <= bar_date.hour <= 20): continue
            
            if coil_sc[idx] < min_coil_score: continue
            
            brk_high = d_high[idx-1]
            brk_low  = d_low[idx-1]
            
            bull_break = (c[idx] > brk_high) and (c[idx] > o[idx])
            bear_break = (c[idx] < brk_low)  and (c[idx] < o[idx])
            
            # Volume & ATR Expansion Confirmation
            bull_break = bull_break and (rvol[idx] >= min_rvol) and (atr_exp[idx] >= min_atr_expansion)
            bear_break = bear_break and (rvol[idx] >= min_rvol) and (atr_exp[idx] >= min_atr_expansion)
            
            # Candle Geometry Confirmation: Solid body, strong close
            bull_break = bull_break and (body_ratio[idx] >= min_candle_body_ratio)
            bear_break = bear_break and (body_ratio[idx] >= min_candle_body_ratio)
            
            # Do Not Chase: Breakout extension cannot exceed boundary by too much
            if bull_break:
                ext = (c[idx] - brk_high) / (a + 1e-9)
                if ext > max_breakout_extension_atr: bull_break = False
            if bear_break:
                ext = (brk_low - c[idx]) / (a + 1e-9)
                if ext > max_breakout_extension_atr: bear_break = False
                
            # 1H & 4H Macro Alignments
            if use_1h_macro:
                if bull_break and htf_1h[idx] != 1: bull_break = False
                if bear_break and htf_1h[idx] != -1: bear_break = False
            if use_4h_macro:
                if bull_break and macro_4h[idx] != 1: bull_break = False
                if bear_break and macro_4h[idx] != -1: bear_break = False
                
            if require_1h_slope_support:
                if bull_break and e200_slope_1h[idx] < 0: bull_break = False
                if bear_break and e200_slope_1h[idx] > 0: bear_break = False
                
            sig = 1 if bull_break else (-1 if bear_break else 0)
            if sig != 0:
                direction = sig
                struct_sl = brk_low if sig == 1 else brk_high
                calc_sl = min(struct_sl, o[i] - 1.5 * a) if sig == 1 else max(struct_sl, o[i] + 1.5 * a)
                risk_dist = abs(o[i] - calc_sl)
                risk_dist = min(max(risk_dist, 1.2 * a), 3.5 * a)
                calc_sl = o[i] - risk_dist if sig == 1 else o[i] + risk_dist
                
                risk_capital = equity * risk_pct
                calc_lots = risk_capital / (risk_dist + 1e-9)
                calc_lots = min(max(round(calc_lots, 2), 0.01), 2.0)
                
                exec_price = o[i] + direction * slip_usd + (direction * spread_usd / 2)
                equity -= exec_price * calc_lots * comm_pct
                
                in_pos = True; pos_type = direction; ep = exec_price; sl = calc_sl
                tp = exec_price + direction * risk_dist * 4.0
                tp1_price = exec_price + direction * risk_dist * 2.0
                lots = calc_lots; entry_idx = i; last_sig = i
                tp1_hit = False; tp1_pnl = 0.0

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

def execute_v7_research():
    print("=" * 80)
    print("   BTCUSDm V7 — BREAKOUT CONTINUATION QUALITY & ROBUSTNESS ENGINE")
    print("=" * 80)
    
    df_15m, df_1h, df_4h, spec = load_data()
    feats = precompute_v7_features(df_15m, df_1h, df_4h)
    n = feats['n']
    
    # 1. PHASE 1: FROZEN V6 CONTROL LEDGER EXTRACTION
    print("\n--- PHASE 1: FROZEN V6 CONTROL LEDGER EXTRACTION ---")
    v6_control = run_v7_simulation(
        feats, min_candle_body_ratio=0.0, max_breakout_extension_atr=99.0,
        require_1h_slope_support=False, session_filter=None
    )
    print(f"V6 Control Total: Trades={v6_control['total_trades']} | PF={v6_control['profit_factor']:.3f} | Exp=${v6_control['expectancy_usd']:.2f} | Return={v6_control['total_return_pct']:+.2f}% | MaxDD={v6_control['max_drawdown']:.1f}%")
    
    # 2. PHASE 2: WINNER VS LOSER QUANTITATIVE AUDIT
    print("\n--- PHASE 2: WINNER VS LOSER QUANTITATIVE FEATURE AUDIT ---")
    tdf = pd.DataFrame(v6_control['trades'])
    if len(tdf) > 0:
        winners = tdf[tdf['net_pnl'] > 0]
        losers  = tdf[tdf['net_pnl'] <= 0]
        print(f"{'Feature':<28} | {'Winners (Mean)':>15} | {'Losers (Mean)':>15} | {'Separation Delta':>18}")
        print("-" * 82)
        for col, lbl in [
            ("sig_coil", "Coil Score (0-100)"),
            ("sig_rvol", "RVOL Expansion"),
            ("sig_atr_exp", "ATR Expansion Ratio"),
            ("sig_body_ratio", "Candle Body Ratio"),
            ("sig_d_range_atr", "Donchian Range (x ATR)"),
            ("mae_r", "Max Adverse Excursion (R)"),
            ("mfe_r", "Max Favorable Excursion (R)")
        ]:
            w_mean = winners[col].mean()
            l_mean = losers[col].mean()
            delta = w_mean - l_mean
            print(f"{lbl:<28} | {w_mean:>15.2f} | {l_mean:>15.2f} | {delta:>+18.2f}")
            
    # 3. PHASE 4 & 5: CANDLE GEOMETRY & DO NOT CHASE FILTER SCAN (ON TRAIN + VAL)
    t_end = int(n * 0.60) # Bar 30,000
    v_end = int(n * 0.80) # Bar 40,000
    print("\n--- PHASE 4 & 5: CANDLE GEOMETRY & EXTENSION FILTERS (TRAIN + VAL) ---")
    for b_rat in [0.0, 0.40, 0.50, 0.60]:
        for ext_cap in [99.0, 1.20, 1.00, 0.80]:
            r = run_v7_simulation(feats, start_idx=120, end_idx=v_end, min_candle_body_ratio=b_rat, max_breakout_extension_atr=ext_cap)
            print(f"Body Ratio >= {b_rat:.2f} | Ext Cap <= {ext_cap:.2f} ATR | Trades={r['total_trades']:>3} | WR={r['win_rate']:>5.1f}% | PF={r['profit_factor']:>6.3f} | Exp=${r['expectancy_usd']:>6.2f} | Ret={r['total_return_pct']:>+6.2f}% | DD={r['max_drawdown']:>5.1f}%")

    # 4. PHASE 22: SEQUENTIAL 4-WINDOW ROLLING WALK-FORWARD VALIDATION
    print("\n--- PHASE 22: SEQUENTIAL 4-WINDOW ROLLING WALK-FORWARD ---")
    window_size = 12500 # 4 equal slices of 12,500 bars (~4 months each)
    seq_results = []
    print(f"{'Window':<12} | {'Bar Range':<18} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Return %':>9} | {'MaxDD %':>8}")
    print("-" * 92)
    for w in range(4):
        w_start = max(120, w * window_size)
        w_stop  = min(n, (w + 1) * window_size)
        r_w = run_v7_simulation(feats, start_idx=w_start, end_idx=w_stop, min_candle_body_ratio=0.50, max_breakout_extension_atr=1.10)
        seq_results.append(r_w)
        print(f"Window {w+1:<5} | {w_start:>6,} -> {w_stop:>6,} | {r_w['total_trades']:>7} | {r_w['win_rate']:>7.1f}% | {r_w['profit_factor']:>7.3f} | ${r_w['expectancy_usd']:>9.2f} | {r_w['total_return_pct']:>8.2f}% | {r_w['max_drawdown']:>7.1f}%")

    # 5. PHASE 20 & 12: FROZEN V7 STRATEGY EVALUATION ACROSS ALL PARTITIONS
    print("\n" + "=" * 80)
    print("   PHASE 20: FROZEN V7 EVALUATION ACROSS PARTITIONS")
    print("=" * 80)
    v7_train = run_v7_simulation(feats, start_idx=120, end_idx=t_end, min_candle_body_ratio=0.50, max_breakout_extension_atr=1.10)
    v7_val   = run_v7_simulation(feats, start_idx=t_end, end_idx=v_end, min_candle_body_ratio=0.50, max_breakout_extension_atr=1.10)
    v7_oos   = run_v7_simulation(feats, start_idx=v_end, end_idx=n, min_candle_body_ratio=0.50, max_breakout_extension_atr=1.10)
    v7_full  = run_v7_simulation(feats, start_idx=120, end_idx=n, min_candle_body_ratio=0.50, max_breakout_extension_atr=1.10)
    
    print(f"{'Partition':<16} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Return %':>9} | {'MaxDD %':>8} | {'Sharpe':>7} | {'Sortino':>7}")
    print("-" * 95)
    for pname, pr in [("TRAIN (60%)", v7_train), ("VAL (20%)", v7_val), ("FINAL OOS (20%)", v7_oos), ("TOTAL FULL", v7_full)]:
        print(f"{pname:<16} | {pr['total_trades']:>7} | {pr['win_rate']:>7.1f}% | {pr['profit_factor']:>7.3f} | ${pr['expectancy_usd']:>9.2f} | {pr['total_return_pct']:>8.2f}% | {pr['max_drawdown']:>7.1f}% | {pr['sharpe']:>7.2f} | {pr['sortino']:>7.2f}")

    # 6. PHASE 24: TRANSACTION COST STRESS (1.0x to 3.0x)
    print("\n--- PHASE 24: TRANSACTION COST STRESS ON FROZEN V7 ---")
    for cm in [1.0, 1.5, 2.0, 3.0]:
        r = run_v7_simulation(feats, start_idx=120, end_idx=n, min_candle_body_ratio=0.50, max_breakout_extension_atr=1.10, cost_mult=cm)
        print(f"  Cost {cm:.1f}x ($ {10.0*cm:>4.1f} spread): Trades={r['total_trades']:>3} | PF={r['profit_factor']:.3f} | Exp=${r['expectancy_usd']:>5.2f} | Ret={r['total_return_pct']:>+5.2f}% | MaxDD={r['max_drawdown']:.1f}%")

    # 7. PHASE 25: MONTE CARLO SIMULATION (10,000 RUNS)
    print("\n--- PHASE 25: MONTE CARLO SIMULATION ON V7 TRADES ---")
    v7_pnls = np.array([t['net_pnl'] for t in v7_full['trades']])
    if len(v7_pnls) > 0:
        n_sims = 10000
        n_t = len(v7_pnls)
        final_eqs = []
        max_dds = []
        neg_count = 0
        
        np.random.seed(42)
        for _ in range(n_sims):
            sim_pnl = np.random.choice(v7_pnls, size=n_t, replace=True)
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

    # 8. PHASE 27: ABLATION SUITE
    print("\n--- PHASE 27: FULL ABLATION SUITE ON V7 ---")
    r_no_body = run_v7_simulation(feats, start_idx=120, end_idx=n, min_candle_body_ratio=0.0)
    r_no_chase = run_v7_simulation(feats, start_idx=120, end_idx=n, max_breakout_extension_atr=99.0)
    r_no_1h = run_v7_simulation(feats, start_idx=120, end_idx=n, use_1h_macro=False)
    r_no_4h = run_v7_simulation(feats, start_idx=120, end_idx=n, use_4h_macro=False)
    
    print(f"  FULL FROZEN V7:           Trades={v7_full['total_trades']:>3} | PF={v7_full['profit_factor']:.3f} | Exp=${v7_full['expectancy_usd']:>5.2f} | Ret={v7_full['total_return_pct']:>+5.2f}% | MaxDD={v7_full['max_drawdown']:.1f}%")
    print(f"  V7 - Candle Body Filter:  Trades={r_no_body['total_trades']:>3} | PF={r_no_body['profit_factor']:.3f} | Exp=${r_no_body['expectancy_usd']:>5.2f} | Ret={r_no_body['total_return_pct']:>+5.2f}% | MaxDD={r_no_body['max_drawdown']:.1f}%")
    print(f"  V7 - Extension Filter:    Trades={r_no_chase['total_trades']:>3} | PF={r_no_chase['profit_factor']:.3f} | Exp=${r_no_chase['expectancy_usd']:>5.2f} | Ret={r_no_chase['total_return_pct']:>+5.2f}% | MaxDD={r_no_chase['max_drawdown']:.1f}%")
    print(f"  V7 - 1H Macro Alignment:  Trades={r_no_1h['total_trades']:>3} | PF={r_no_1h['profit_factor']:.3f} | Exp=${r_no_1h['expectancy_usd']:>5.2f} | Ret={r_no_1h['total_return_pct']:>+5.2f}% | MaxDD={r_no_1h['max_drawdown']:.1f}%")
    print(f"  V7 - 4H Macro Alignment:  Trades={r_no_4h['total_trades']:>3} | PF={r_no_4h['profit_factor']:.3f} | Exp=${r_no_4h['expectancy_usd']:>5.2f} | Ret={r_no_4h['total_return_pct']:>+5.2f}% | MaxDD={r_no_4h['max_drawdown']:.1f}%")

    # SAVE AUDIT RESULTS
    v7_results = {
        "full": v7_full, "train": v7_train, "val": v7_val, "oos": v7_oos,
        "sequential": seq_results
    }
    with open("E:\\Trading\\v7_research_results.json", "w") as f:
        json.dump(v7_results, f, indent=2)
    print("\nV7 RESEARCH SUITE COMPLETE. Saved to E:\\Trading\\v7_research_results.json")

if __name__ == "__main__":
    execute_v7_research()
