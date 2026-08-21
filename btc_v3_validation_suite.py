"""
BTCUSDm V3 Quantitative Research, Diagnostics & Optimization Suite
Phases 1 to 24 on REAL MT5 Data
==================================================================
Strictly uses real historical candles from Exness MT5.
Lookahead-bias-free: causal indicators, next-open execution.
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
sys.path.insert(0, "E:\\Trading")

DATA_DIR = "E:\\Trading\\data"

def load_data(tf_name):
    path = os.path.join(DATA_DIR, f"BTCUSDm_{tf_name}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Data file not found: {path}")
    df = pd.read_csv(path)
    df['time'] = pd.to_datetime(df['time'])
    df.sort_values(by='time', inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

def load_spec():
    path = os.path.join(DATA_DIR, "BTCUSDm_spec.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {
        "symbol": "BTCUSDm", "digits": 2, "point": 0.01, "spread_points": 1000,
        "contract_size": 1.0, "volume_min": 0.01, "tick_value": 1.01729
    }

# =====================================================================
# PHASE 1: RAW DATA AUDIT
# =====================================================================
def run_phase_1_audit(df_5m, df_15m, df_1h, spec):
    print("\n" + "="*80)
    print("  PHASE 1 — RAW-DATA QUALITY & BROKER SPECIFICATION REPORT")
    print("="*80)
    
    audit = {}
    for name, df in [("5M", df_5m), ("15M", df_15m), ("1H", df_1h)]:
        n = len(df)
        t_min = df['time'].min()
        t_max = df['time'].max()
        
        # Missing / gaps
        expected_delta = {"5M": pd.Timedelta(minutes=5), "15M": pd.Timedelta(minutes=15), "1H": pd.Timedelta(hours=1)}[name]
        deltas = df['time'].diff()
        gaps = deltas[deltas > expected_delta]
        
        # Duplicates
        duplicates = df['time'].duplicated().sum()
        
        # Abnormal prices
        inv_hl = (df['high'] < df['low']).sum()
        zero_p = (df['close'] <= 0).sum()
        pct_change = (df['close'].pct_change().abs())
        spikes = (pct_change > 0.10).sum()
        
        # Volume
        zero_vol = (df['volume'] <= 0).sum()
        vol_spikes = (df['volume'] > 50 * df['volume'].median()).sum()
        
        # Weekend behavior
        weekends = df[df['time'].dt.dayofweek >= 5]
        weekend_pct = len(weekends) / n * 100
        
        audit[name] = {
            "bars": n,
            "start": str(t_min),
            "end": str(t_max),
            "calendar_span_days": round((t_max - t_min).total_seconds() / 86400, 1),
            "gaps_count": len(gaps),
            "max_gap_hours": round(gaps.max().total_seconds() / 3600, 1) if len(gaps) > 0 else 0,
            "duplicates": int(duplicates),
            "invalid_high_low": int(inv_hl),
            "zero_prices": int(zero_p),
            "price_spikes_gt10pct": int(spikes),
            "zero_volume_bars": int(zero_vol),
            "vol_spikes_gt50x": int(vol_spikes),
            "weekend_bars": len(weekends),
            "weekend_pct": round(weekend_pct, 1),
        }
        
        print(f"\nTimeframe {name}:")
        print(f"  Bars: {n:,} | Span: {audit[name]['calendar_span_days']} days ({t_min} -> {t_max})")
        print(f"  Missing candle gaps: {len(gaps):,} (Max gap: {audit[name]['max_gap_hours']} hrs)")
        print(f"  Duplicates: {duplicates} | Inverted H/L: {inv_hl} | Zero Prices: {zero_p}")
        print(f"  Price spikes >10%: {spikes} | Zero volume bars: {zero_vol}")
        print(f"  Weekend bars: {len(weekends):,} ({weekend_pct:.1f}% of total — 24/7 crypto availability)")
    
    # Contract specs
    point = spec.get("point", 0.01)
    spread_pts = spec.get("spread_points", 1000)
    spread_usd = spread_pts * point
    avg_btc_price = df_5m['close'].iloc[-1]
    spread_pct = (spread_usd / avg_btc_price) * 100
    
    print("\nSymbol Contract Specifications (Exness BTCUSDm):")
    print(f"  Contract Size:       {spec.get('contract_size', 1.0)} BTC per lot")
    print(f"  Point Size:          ${point}")
    print(f"  Live Spread:         {spread_pts} points = ${spread_usd:.2f} per BTC ({spread_pct:.3f}% of price)")
    print(f"  Min Volume:          {spec.get('volume_min', 0.01)} lots ({spec.get('volume_min', 0.01)} BTC)")
    print(f"  Tick Value:          ${spec.get('tick_value', 1.017):.4f} per tick")
    print(f"  Server Time Offset:  UTC+0 / UTC+2 broker timestamp")
    
    audit['spec'] = spec
    audit['spread_usd'] = spread_usd
    audit['spread_pct'] = spread_pct
    return audit


# =====================================================================
# CORE CAUSAL STRATEGY IMPLEMENTATION (Lookahead-Free)
# =====================================================================
def run_strategy_simulation(
    df_primary, df_15m=None, df_1h=None,
    sl_atr_mult=1.4,
    sl_min_atr_mult=0.8,
    sl_max_atr_mult=2.0,
    sl_method="hybrid",      # "atr", "structure", "hybrid"
    min_score=55,
    tp1_rr=2.0,
    tp2_rr=3.0,
    tp_architecture="A",     # "A": TP1 1.5R + runner 3R, "B": TP1 2R + runner 3R, "C": TP1 2R + runner 4R, "D": structure target, "E": trailing, "F": full runner
    tp1_close_pct=0.50,
    be_mode="lock_half_r",   # "immediate", "be_plus_fee", "lock_025r", "lock_half_r", "trail", "none"
    cooldown_bars=12,
    use_session_filter=False,
    allowed_setups=(1, 2, 3, 4), # 1=SetupA (reversion), 2=SetupB (trend cont), 3=SetupC (sweep), 4=SetupD (breakout)
    ablation_exclude=None,   # component name to exclude from scoring
    lots=0.02,
    initial_balance=10000.0,
    cost_multiplier=1.0,
    normal_spread_usd=10.0,
    commission_pct=0.0001,
    slippage_usd=2.0,
    date_mask=None,
):
    """
    Lookahead-free event-driven backtest simulation engine.
    Execution strictly at NEXT bar open.
    """
    df = df_primary.copy().reset_index(drop=True)
    if date_mask is not None:
        df = df[date_mask].copy().reset_index(drop=True)
        
    n = len(df)
    if n < 200:
        return {"total_trades": 0, "profit_factor": 0, "win_rate": 0, "trades": []}
        
    # Transaction costs
    spread_usd = normal_spread_usd * cost_multiplier
    comm_pct   = commission_pct * cost_multiplier
    slip_usd   = slippage_usd * cost_multiplier
    
    # 1. Indicators (causal, right-aligned)
    c = df['close'].values
    o = df['open'].values
    h = df['high'].values
    l = df['low'].values
    v = df['volume'].replace(0, 1e-6).values
    
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
    
    # Rolling Volume Profile (96 bars)
    tp = (h + l + c) / 3.0
    vp_pv = pd.Series(tp * v).rolling(96, min_periods=30).sum()
    vp_v  = pd.Series(v).rolling(96, min_periods=30).sum().replace(0, 1e-9)
    poc = (vp_pv / vp_v).values
    dev_sq = (tp - poc) ** 2
    vw_var = pd.Series(dev_sq * v).rolling(96, min_periods=30).sum() / vp_v
    vw_std = np.sqrt(np.maximum(vw_var, 0)).values
    vah = poc + 1.04 * vw_std
    val = poc - 1.04 * vw_std
    poc_slope = np.concatenate([[0]*5, np.diff(poc, n=5)])
    
    # 20-bar avg volume
    vol_avg = pd.Series(v).rolling(20, min_periods=10).mean().values
    
    # Swings (confirmed at i+5)
    sh_price = np.full(n, np.nan)
    sl_price = np.full(n, np.nan)
    for i in range(5, n - 5):
        if h[i] == max(h[i-5:i+6]):
            sh_price[i+5] = h[i]
        if l[i] == min(l[i-5:i+6]):
            sl_price[i+5] = l[i]
    last_sh = pd.Series(sh_price).ffill().values
    last_sl = pd.Series(sl_price).ffill().values
    
    # Multi-TF Alignment
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
        
    # RSI on primary
    delta5 = pd.Series(c).diff()
    rsi_g5 = delta5.where(delta5 > 0, 0).ewm(span=14, adjust=False).mean()
    rsi_l5 = (-delta5.where(delta5 < 0, 0)).ewm(span=14, adjust=False).mean()
    rsi5 = (100 - 100 / (1 + rsi_g5 / rsi_l5.replace(0, 1e-9))).values
    
    # Simulation state
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
    
    times = df['time'].values
    
    for i in range(120, n):
        # 1. Position Management
        if in_pos:
            hit_tp2 = False
            hit_sl = False
            exit_p = 0.0
            
            # Trailing stop update if mode is trailing
            if tp_architecture in ["E", "F"] or be_mode == "trail":
                trail_dist = atr[i] * 1.0
                if pos_type == 1:
                    sl = max(sl, c[i] - trail_dist)
                else:
                    sl = min(sl, c[i] + trail_dist)
                    
            if pos_type == 1: # Long
                if not tp1_hit and h[i] >= tp1:
                    tp1_hit = True
                    part_exit = tp1 - spread_usd / 2
                    part_pnl = (part_exit - ep) * (lots * tp1_close_pct)
                    part_pnl -= part_exit * (lots * tp1_close_pct) * comm_pct
                    equity += part_pnl
                    
                    # Breakeven adjustment
                    if be_mode == "immediate":
                        sl = ep
                    elif be_mode == "be_plus_fee":
                        sl = ep + spread_usd * 0.5
                    elif be_mode == "lock_025r":
                        sl = ep + (ep - sl) * 0.25
                    elif be_mode == "lock_half_r":
                        sl = ep + (ep - sl) * 0.5
                        
                # Conservative resolution: check SL first if both crossed in same bar
                if l[i] <= sl:
                    hit_sl = True
                    exit_p = sl - spread_usd / 2
                elif h[i] >= tp2 and tp_architecture != "F":
                    hit_tp2 = True
                    exit_p = tp2 - spread_usd / 2
                    
            else: # Short
                if not tp1_hit and l[i] <= tp1:
                    tp1_hit = True
                    part_exit = tp1 + spread_usd / 2
                    part_pnl = (ep - part_exit) * (lots * tp1_close_pct)
                    part_pnl -= part_exit * (lots * tp1_close_pct) * comm_pct
                    equity += part_pnl
                    
                    if be_mode == "immediate":
                        sl = ep
                    elif be_mode == "be_plus_fee":
                        sl = ep - spread_usd * 0.5
                    elif be_mode == "lock_025r":
                        sl = ep - (sl - ep) * 0.25
                    elif be_mode == "lock_half_r":
                        sl = ep - (sl - ep) * 0.5
                        
                if h[i] >= sl:
                    hit_sl = True
                    exit_p = sl + spread_usd / 2
                elif l[i] <= tp2 and tp_architecture != "F":
                    hit_tp2 = True
                    exit_p = tp2 + spread_usd / 2
                    
            if hit_tp2 or hit_sl:
                rem_lots = (lots * (1 - tp1_close_pct)) if tp1_hit else lots
                if pos_type == 1:
                    final_pnl = (exit_p - ep) * rem_lots
                else:
                    final_pnl = (ep - exit_p) * rem_lots
                final_pnl -= exit_p * rem_lots * comm_pct
                
                equity += final_pnl
                tot_trade_pnl = final_pnl + (part_pnl if tp1_hit else 0.0)
                
                if equity > peak_equity: peak_equity = equity
                dd = (peak_equity - equity) / peak_equity * 100
                if dd > max_dd: max_dd = dd
                
                duration = i - entry_idx
                r_multiple = tot_trade_pnl / (abs(ep - sl) * lots + 1e-9)
                
                trades.append({
                    "entry_time": str(entry_time),
                    "exit_time": str(pd.Timestamp(times[i])),
                    "direction": "LONG" if pos_type == 1 else "SHORT",
                    "entry_price": round(ep, 2),
                    "exit_price": round(exit_p, 2),
                    "trade_pnl": round(tot_trade_pnl, 2),
                    "r_multiple": round(r_multiple, 3),
                    "outcome": "TP2" if hit_tp2 else "SL",
                    "tp1_hit": tp1_hit,
                    "score": entry_score,
                    "regime": entry_regime,
                    "setup": entry_setup,
                    "duration_bars": duration,
                    "year": pd.Timestamp(entry_time).year,
                    "hour": pd.Timestamp(entry_time).hour,
                    "dayofweek": pd.Timestamp(entry_time).day_name(),
                    "equity": round(equity, 2),
                })
                eq_curve.append(round(equity, 2))
                in_pos = False
                
        # 2. Signal Generation (Evaluated on Bar i-1, Executed at Bar i Open)
        if not in_pos and (i - last_sig >= cooldown_bars):
            # Look at previous bar (i-1) features
            idx = i - 1
            a = atr[idx]
            if np.isnan(a) or a <= 0 or np.isnan(poc[idx]):
                continue
                
            price = c[idx]
            bar_date = pd.Timestamp(times[idx])
            
            # Session filter
            if use_session_filter:
                if not (6 <= bar_date.hour <= 22):
                    continue
                    
            adx_i = adx[idx]
            atr_pct_i = atr_pct[idx]
            is_extreme_vol = atr_pct_i >= 92.0
            
            bull_5m = (price > ema200[idx]) and (ema21[idx] > ema55[idx])
            bear_5m = (price < ema200[idx]) and (ema21[idx] < ema55[idx])
            
            # 8 Regime Classification
            if adx_i > 28.0 and bull_5m: regime = "Strong Bull Trend"
            elif adx_i > 28.0 and bear_5m: regime = "Strong Bear Trend"
            elif adx_i > 20.0 and bull_5m: regime = "Weak Bull Trend"
            elif adx_i > 20.0 and bear_5m: regime = "Weak Bear Trend"
            elif atr_pct_i >= 75.0 and adx_i > 22.0: regime = "High-Vol Trend"
            elif atr_pct_i >= 75.0: regime = "High-Vol Range"
            elif atr_pct_i <= 30.0: regime = "Low-Vol Market"
            else: regime = "Sideways Range"
            
            # Candle shape
            b_rng = h[idx] - l[idx]
            b_body = abs(c[idx] - o[idx])
            b_ratio = b_body / (b_rng + 1e-9)
            bar_bull = (c[idx] > o[idx]) and (b_ratio > 0.28)
            bar_bear = (c[idx] < o[idx]) and (b_ratio > 0.28)
            l_wick = min(c[idx], o[idx]) - l[idx]
            u_wick = h[idx] - max(c[idx], o[idx])
            
            # VP Proximity
            vp_tol = 0.35 * a
            near_val = l[idx] <= val[idx] + vp_tol
            near_vah = h[idx] >= vah[idx] - vp_tol
            near_poc = abs(price - poc[idx]) < vp_tol * 1.5
            
            # Swings / Sweeps
            lsh = last_sh[idx]
            lsl = last_sl[idx]
            bull_sweep = (l[idx] < lsl - 0.001 * price) and (c[idx] > lsl) if not np.isnan(lsl) else False
            bear_sweep = (h[idx] > lsh + 0.001 * price) and (c[idx] < lsh) if not np.isnan(lsh) else False
            
            # Vol expansion
            vol_exp = (v[idx] >= 1.2 * vol_avg[idx]) if not np.isnan(vol_avg[idx]) else False
            
            # Score Calculation (Ablation support)
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
            
            # Setup definitions
            setup_id = 0
            sig = 0
            
            # Setup A: Value Area Reversion (VAL rejection for Long, VAH rejection for Short)
            if 1 in allowed_setups:
                if (near_val and bar_bull and l_wick > b_body * 0.35 and ("Range" in regime or bull_5m)):
                    sig = 1; setup_id = 1
                elif (near_vah and bar_bear and u_wick > b_body * 0.35 and ("Range" in regime or bear_5m)):
                    sig = -1; setup_id = 1
                    
            # Setup B: Trend Continuation (POC retest with trend)
            if sig == 0 and 2 in allowed_setups:
                if (bull_5m and near_poc and bar_bull and vol_exp and "Trend" in regime):
                    sig = 1; setup_id = 2
                elif (bear_5m and near_poc and bar_bear and vol_exp and "Trend" in regime):
                    sig = -1; setup_id = 2
                    
            # Setup C: Liquidity Sweep + Reversal
            if sig == 0 and 3 in allowed_setups:
                if (bull_sweep and bar_bull):
                    sig = 1; setup_id = 3
                elif (bear_sweep and bar_bear):
                    sig = -1; setup_id = 3
                    
            # Setup D: Breakout + Retest
            if sig == 0 and 4 in allowed_setups:
                if (bull_5m and price > vah[idx] and bar_bull and vol_exp):
                    sig = 1; setup_id = 4
                elif (bear_5m and price < val[idx] and bar_bear and vol_exp):
                    sig = -1; setup_id = 4
                    
            # Check score gating
            if sig != 0 and score >= min_score and not is_extreme_vol:
                # EXECUTE AT CURRENT BAR OPEN (i) + SPREAD/SLIPPAGE
                direction = sig
                exec_price = o[i] + direction * slip_usd + (direction * spread_usd / 2)
                
                # Commission
                commission = exec_price * lots * comm_pct
                equity -= commission
                
                # Stop loss calculation based on method
                if sl_method == "atr":
                    sl_dist = a * sl_atr_mult
                elif sl_method == "structure":
                    struct_level = lsl if direction == 1 else lsh
                    if not np.isnan(struct_level):
                        sl_dist = abs(exec_price - struct_level) + 0.3 * a
                    else:
                        sl_dist = a * sl_atr_mult
                else: # Hybrid
                    struct_level = lsl if direction == 1 else lsh
                    if not np.isnan(struct_level):
                        s_dist = abs(exec_price - struct_level) + 0.3 * a
                        sl_dist = max(s_dist, a * sl_min_atr_mult)
                    else:
                        sl_dist = a * sl_atr_mult
                    sl_dist = min(max(sl_dist, a * sl_min_atr_mult), a * sl_max_atr_mult)
                    
                calc_sl = exec_price - sl_dist if direction == 1 else exec_price + sl_dist
                
                # Take profit calculation based on architecture
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
                elif tp_architecture == "D": # Structure target
                    calc_tp1 = vah[idx] if direction == 1 else val[idx]
                    calc_tp2 = exec_price + direction * risk_dist * 3.5
                elif tp_architecture == "E": # Trailing stop
                    calc_tp1 = exec_price + direction * risk_dist * 1.5
                    calc_tp2 = exec_price + direction * risk_dist * 10.0 # open ended
                else: # F: Full runner
                    calc_tp1 = exec_price + direction * risk_dist * 10.0
                    calc_tp2 = exec_price + direction * risk_dist * 10.0
                    
                in_pos = True
                pos_type = direction
                ep = exec_price
                sl = calc_sl
                tp1 = calc_tp1
                tp2 = calc_tp2
                tp1_hit = False
                entry_idx = i
                entry_time = pd.Timestamp(times[i])
                entry_score = score
                entry_regime = regime
                entry_setup = setup_id
                last_sig = i

    # Compile metrics
    if not trades:
        return {"total_trades": 0, "profit_factor": 0, "win_rate": 0, "expectancy": 0,
                "total_return_pct": 0, "max_drawdown": 0, "sharpe": 0, "trades": []}
                
    tdf = pd.DataFrame(trades)
    wins = tdf[tdf['trade_pnl'] > 0]
    losses = tdf[tdf['trade_pnl'] <= 0]
    
    gw = wins['trade_pnl'].sum()
    gl = abs(losses['trade_pnl'].sum())
    pf = gw / gl if gl > 0 else 999.0
    wr = len(wins) / len(tdf) * 100
    
    avg_w = wins['trade_pnl'].mean() if len(wins) > 0 else 0
    avg_l = losses['trade_pnl'].mean() if len(losses) > 0 else 0
    expectancy = (wr / 100) * avg_w + (1 - wr / 100) * avg_l
    
    tot_ret = (equity - initial_balance) / initial_balance * 100
    days = max((df['time'].iloc[-1] - df['time'].iloc[0]).total_seconds() / 86400, 1)
    cagr = ((equity / initial_balance) ** (365.25 / days) - 1) * 100 if equity > 0 else -100.0
    
    eq_arr = np.array(eq_curve)
    rets = np.diff(eq_arr) / eq_arr[:-1]
    sharpe = (rets.mean() / (rets.std() + 1e-9)) * np.sqrt(252 * 288)
    neg_rets = rets[rets < 0]
    sortino = (rets.mean() / (neg_rets.std() + 1e-9)) * np.sqrt(252 * 288) if len(neg_rets) > 0 else 999.0
    calmar = tot_ret / max_dd if max_dd > 0 else 0.0
    
    # Max consecutive losses
    consec = 0
    max_consec = 0
    for pnl in tdf['trade_pnl']:
        if pnl <= 0:
            consec += 1
            if consec > max_consec: max_consec = consec
        else:
            consec = 0
            
    return {
        "total_trades": len(trades),
        "win_rate": round(wr, 2),
        "profit_factor": round(pf, 3),
        "expectancy_usd": round(expectancy, 2),
        "total_return_pct": round(tot_ret, 2),
        "cagr_pct": round(cagr, 2),
        "max_drawdown": round(max_dd, 2),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "calmar": round(calmar, 3),
        "avg_win_usd": round(avg_w, 2),
        "avg_loss_usd": round(avg_l, 2),
        "median_trade_usd": round(tdf['trade_pnl'].median(), 2),
        "largest_win_usd": round(tdf['trade_pnl'].max(), 2),
        "largest_loss_usd": round(tdf['trade_pnl'].min(), 2),
        "max_consecutive_losses": max_consec,
        "avg_duration_bars": round(tdf['duration_bars'].mean(), 1),
        "final_equity": round(equity, 2),
        "trades": trades,
    }


# =====================================================================
# RESEARCH SUITE RUNNER (PHASES 2 TO 24)
# =====================================================================
def run_all_research_phases():
    print("=" * 80)
    print("   BTCUSDm QUANTITATIVE RESEARCH & VALIDATION SUITE (REAL MT5 DATA)")
    print("=" * 80)
    
    df_5m = load_data("5m")
    df_15m = load_data("15m")
    df_1h = load_data("1h")
    spec = load_spec()
    
    # PHASE 1: Audit
    p1 = run_phase_1_audit(df_5m, df_15m, df_1h, spec)
    
    # PHASE 2: Baseline V2 Evaluation (Unaltered)
    print("\n" + "="*80)
    print("  PHASE 2 — BASELINE V2 UNALTERED EVALUATION (REAL MT5 DATA)")
    print("="*80)
    
    b_5m = run_strategy_simulation(df_5m, df_15m, df_1h, sl_atr_mult=1.4, min_score=55, tp1_rr=2.0, tp2_rr=3.0)
    b_15m = run_strategy_simulation(df_15m, df_1h=df_1h, sl_atr_mult=1.4, min_score=55, tp1_rr=2.0, tp2_rr=3.0)
    b_1h = run_strategy_simulation(df_1h, sl_atr_mult=1.4, min_score=55, tp1_rr=2.0, tp2_rr=3.0)
    
    print("\nBaseline V2 Performance on Real MT5 BTCUSDm Data:")
    print(f"{'Timeframe':<10} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Return %':>9} | {'CAGR %':>8} | {'MaxDD %':>8} | {'Sharpe':>7} | {'Sortino':>8}")
    print("-" * 95)
    for name, res in [("5M", b_5m), ("15M", b_15m), ("1H", b_1h)]:
        r_sign = "+" if res.get('total_return_pct', 0) >= 0 else ""
        print(f"{name:<10} | {res['total_trades']:>7} | {res['win_rate']:>7.1f}% | {res['profit_factor']:>7.3f} | ${res['expectancy_usd']:>9.2f} | {r_sign}{res['total_return_pct']:>8.2f}% | {res['cagr_pct']:>7.1f}% | {res['max_drawdown']:>7.1f}% | {res['sharpe']:>7.2f} | {res['sortino']:>8.2f}")
        
    print("\nDetailed 5M Baseline Trade Statistics:")
    print(f"  Avg Win: ${b_5m['avg_win_usd']} | Avg Loss: ${b_5m['avg_loss_usd']} | Median Trade: ${b_5m['median_trade_usd']}")
    print(f"  Largest Win: ${b_5m['largest_win_usd']} | Largest Loss: ${b_5m['largest_loss_usd']}")
    print(f"  Max Consecutive Losses: {b_5m['max_consecutive_losses']} | Avg Duration: {b_5m['avg_duration_bars']} bars")
    
    # PHASE 3: Year-by-Year Analysis (Using 15M / 5M data)
    print("\n" + "="*80)
    print("  PHASE 3 — YEAR-BY-YEAR PERFORMANCE BREAKDOWN")
    print("="*80)
    tdf_15m = pd.DataFrame(b_15m['trades']) if b_15m['trades'] else pd.DataFrame()
    if not tdf_15m.empty:
        years = sorted(tdf_15m['year'].unique())
        print(f"{'Year':<8} | {'Trades':>7} | {'PF':>7} | {'Win Rate':>8} | {'Expectancy':>11} | {'Return $':>10} | {'Long PF':>8} | {'Short PF':>9}")
        print("-" * 85)
        for y in years:
            ydf = tdf_15m[tdf_15m['year'] == y]
            w = ydf[ydf['trade_pnl'] > 0]['trade_pnl'].sum()
            l = abs(ydf[ydf['trade_pnl'] <= 0]['trade_pnl'].sum())
            ypf = w / l if l > 0 else 999.0
            
            # Long / Short PF
            l_df = ydf[ydf['direction'] == 'LONG']
            s_df = ydf[ydf['direction'] == 'SHORT']
            l_pf = (l_df[l_df['trade_pnl'] > 0]['trade_pnl'].sum() / abs(l_df[l_df['trade_pnl'] <= 0]['trade_pnl'].sum())) if len(l_df[l_df['trade_pnl'] <= 0]) > 0 else 0
            s_pf = (s_df[s_df['trade_pnl'] > 0]['trade_pnl'].sum() / abs(s_df[s_df['trade_pnl'] <= 0]['trade_pnl'].sum())) if len(s_df[s_df['trade_pnl'] <= 0]) > 0 else 0
            
            wr = len(ydf[ydf['trade_pnl'] > 0]) / len(ydf) * 100
            exp = ydf['trade_pnl'].mean()
            tot_p = ydf['trade_pnl'].sum()
            print(f"{y:<8} | {len(ydf):>7} | {ypf:>7.3f} | {wr:>7.1f}% | ${exp:>9.2f} | ${tot_p:>9.2f} | {l_pf:>8.2f} | {s_pf:>9.2f}")
            
    # PHASE 4: Market Regime Analysis (8 Regimes)
    print("\n" + "="*80)
    print("  PHASE 4 — MARKET REGIME PERFORMANCE ANALYSIS")
    print("="*80)
    if not tdf_15m.empty:
        print(f"{'Market Regime':<22} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Total PnL':>10}")
        print("-" * 75)
        for reg in tdf_15m['regime'].unique():
            rdf = tdf_15m[tdf_15m['regime'] == reg]
            w = rdf[rdf['trade_pnl'] > 0]['trade_pnl'].sum()
            l = abs(rdf[rdf['trade_pnl'] <= 0]['trade_pnl'].sum())
            rpf = w / l if l > 0 else 999.0
            rwr = len(rdf[rdf['trade_pnl'] > 0]) / len(rdf) * 100
            rexp = rdf['trade_pnl'].mean()
            rtot = rdf['trade_pnl'].sum()
            print(f"{reg:<22} | {len(rdf):>7} | {rwr:>7.1f}% | {rpf:>7.3f} | ${rexp:>9.2f} | ${rtot:>9.2f}")
            
    # PHASE 5: Setup-Level Analysis (A, B, C, D)
    print("\n" + "="*80)
    print("  PHASE 5 — SETUP-LEVEL INDEPENDENT PERFORMANCE")
    print("="*80)
    setup_names = {
        1: "Setup A (Value Mean Reversion)",
        2: "Setup B (Trend Continuation)",
        3: "Setup C (Liquidity Sweep)",
        4: "Setup D (Breakout Retest)"
    }
    print(f"{'Setup':<32} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Avg R':>7} | {'Median R':>9}")
    print("-" * 88)
    for sid, sname in setup_names.items():
        res_s = run_strategy_simulation(df_15m, df_1h=df_1h, allowed_setups=(sid,))
        stdf = pd.DataFrame(res_s['trades']) if res_s['trades'] else pd.DataFrame()
        if not stdf.empty:
            avg_r = stdf['r_multiple'].mean()
            med_r = stdf['r_multiple'].median()
            print(f"{sname:<32} | {res_s['total_trades']:>7} | {res_s['win_rate']:>7.1f}% | {res_s['profit_factor']:>7.3f} | ${res_s['expectancy_usd']:>9.2f} | {avg_r:>7.2f} | {med_r:>9.2f}")
        else:
            print(f"{sname:<32} |       0 |     0.0% |   0.000 |      $0.00 |    0.00 |      0.00")
            
    # PHASE 6: Component Ablation Analysis
    print("\n" + "="*80)
    print("  PHASE 6 — ENTRY SCORE COMPONENT ABLATION")
    print("="*80)
    base_res = run_strategy_simulation(df_15m, df_1h=df_1h)
    ablation_items = [
        ("FULL SCORE (9 Components)", None),
        ("FULL - RSI", "rsi"),
        ("FULL - Candle Quality", "candle"),
        ("FULL - Volume Expansion", "vol"),
        ("FULL - Liquidity Sweeps", "sweep"),
        ("FULL - Market Structure", "structure"),
        ("FULL - HTF Macro Trend", "htf"),
        ("FULL - MTF Momentum", "mtf"),
        ("FULL - Volatility Regime", "vol_regime"),
        ("FULL - VP Value Zones", "vp"),
    ]
    print(f"{'Configuration':<28} | {'Trades':>7} | {'PF':>7} | {'Expectancy':>11} | {'Return %':>9} | {'MaxDD %':>8} | {'Delta PF':>8}")
    print("-" * 88)
    base_pf = base_res['profit_factor']
    for label, excl in ablation_items:
        ares = run_strategy_simulation(df_15m, df_1h=df_1h, ablation_exclude=excl)
        delta_pf = ares['profit_factor'] - base_pf if excl is not None else 0.0
        d_sign = "+" if delta_pf >= 0 else ""
        print(f"{label:<28} | {ares['total_trades']:>7} | {ares['profit_factor']:>7.3f} | ${ares['expectancy_usd']:>9.2f} | {ares['total_return_pct']:>8.2f}% | {ares['max_drawdown']:>7.1f}% | {d_sign}{delta_pf:>7.3f}")
        
    # PHASE 7: Score Threshold Curve
    print("\n" + "="*80)
    print("  PHASE 7 — SCORE THRESHOLD SENSITIVITY CURVE")
    print("="*80)
    print(f"{'Threshold':<10} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Return %':>9} | {'MaxDD %':>8}")
    print("-" * 72)
    thresholds = [45, 50, 55, 60, 65, 70, 75, 80]
    for th in thresholds:
        tres = run_strategy_simulation(df_15m, df_1h=df_1h, min_score=th)
        print(f"{th:<10} | {tres['total_trades']:>7} | {tres['win_rate']:>7.1f}% | {tres['profit_factor']:>7.3f} | ${tres['expectancy_usd']:>9.2f} | {tres['total_return_pct']:>8.2f}% | {tres['max_drawdown']:>7.1f}%")
        
    # PHASE 8: Stop Loss Research
    print("\n" + "="*80)
    print("  PHASE 8 — STOP LOSS RESEARCH (ATR vs STRUCTURE vs HYBRID)")
    print("="*80)
    print(f"{'SL Method':<12} | {'ATR Mult':>8} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'MaxDD %':>8}")
    print("-" * 75)
    for method in ["atr", "structure", "hybrid"]:
        for mult in [0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]:
            sres = run_strategy_simulation(df_15m, df_1h=df_1h, sl_method=method, sl_atr_mult=mult)
            print(f"{method:<12} | {mult:>8.1f} | {sres['total_trades']:>7} | {sres['win_rate']:>7.1f}% | {sres['profit_factor']:>7.3f} | ${sres['expectancy_usd']:>9.2f} | {sres['max_drawdown']:>7.1f}%")
            
    # PHASE 9: Exit Architecture Research
    print("\n" + "="*80)
    print("  PHASE 9 — EXIT ARCHITECTURE RESEARCH")
    print("="*80)
    exits = [
        ("Exit A: TP1 1.5R + Runner 3R", "A"),
        ("Exit B: TP1 2.0R + Runner 3R", "B"),
        ("Exit C: TP1 2.0R + Runner 4R", "C"),
        ("Exit D: Structural Target", "D"),
        ("Exit E: Trailing Stop (1x ATR)", "E"),
        ("Exit F: Full Runner Trailing", "F"),
    ]
    print(f"{'Exit Architecture':<32} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'MaxDD %':>8}")
    print("-" * 80)
    for elabel, earch in exits:
        eres = run_strategy_simulation(df_15m, df_1h=df_1h, tp_architecture=earch)
        print(f"{elabel:<32} | {eres['total_trades']:>7} | {eres['win_rate']:>7.1f}% | {eres['profit_factor']:>7.3f} | ${eres['expectancy_usd']:>9.2f} | {eres['max_drawdown']:>7.1f}%")
        
    # PHASE 10: Breakeven Analysis
    print("\n" + "="*80)
    print("  PHASE 10 — BREAKEVEN LOGIC RESEARCH")
    print("="*80)
    be_modes = [
        ("Immediate Breakeven (Entry)", "immediate"),
        ("Breakeven + Fees", "be_plus_fee"),
        ("+0.25R Profit Lock", "lock_025r"),
        ("+0.50R Profit Lock", "lock_half_r"),
        ("Continuous ATR Trailing", "trail"),
        ("No Breakeven (Pure Target)", "none"),
    ]
    print(f"{'Breakeven Mode':<30} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Return %':>9}")
    print("-" * 80)
    for blabel, bmode in be_modes:
        bres = run_strategy_simulation(df_15m, df_1h=df_1h, be_mode=bmode)
        print(f"{blabel:<30} | {bres['total_trades']:>7} | {bres['win_rate']:>7.1f}% | {bres['profit_factor']:>7.3f} | ${bres['expectancy_usd']:>9.2f} | {bres['total_return_pct']:>8.2f}%")
        
    # PHASE 11: BTC-Specific Time Analysis
    print("\n" + "="*80)
    print("  PHASE 11 — BTC-SPECIFIC TIME & SESSION ANALYSIS")
    print("="*80)
    if not tdf_15m.empty:
        # Session buckets
        def get_session(h):
            if 0 <= h < 8: return "Asian Session (00-08 UTC)"
            elif 8 <= h < 13: return "London Morning (08-13 UTC)"
            elif 13 <= h < 16: return "London/NY Overlap (13-16 UTC)"
            elif 16 <= h < 21: return "NY Afternoon (16-21 UTC)"
            else: return "Off-Hours / Late Asia (21-00 UTC)"
            
        tdf_15m['session'] = tdf_15m['hour'].apply(get_session)
        print("Session Performance Breakdown:")
        print(f"{'Session':<32} | {'Trades':>7} | {'Win Rate':>8} | {'PF':>7} | {'Expectancy':>11} | {'Total PnL':>10}")
        print("-" * 85)
        for sess in sorted(tdf_15m['session'].unique()):
            sdf = tdf_15m[tdf_15m['session'] == sess]
            w = sdf[sdf['trade_pnl'] > 0]['trade_pnl'].sum()
            l = abs(sdf[sdf['trade_pnl'] <= 0]['trade_pnl'].sum())
            spf = w / l if l > 0 else 999.0
            swr = len(sdf[sdf['trade_pnl'] > 0]) / len(sdf) * 100
            sexp = sdf['trade_pnl'].mean()
            stot = sdf['trade_pnl'].sum()
            print(f"{sess:<32} | {len(sdf):>7} | {swr:>7.1f}% | {spf:>7.3f} | ${sexp:>9.2f} | ${stot:>9.2f}")
            
    # PHASE 12: Long vs Short
    print("\n" + "="*80)
    print("  PHASE 12 — LONG VS SHORT DIRECTIONAL ASYMMETRY")
    print("="*80)
    if not tdf_15m.empty:
        ldf = tdf_15m[tdf_15m['direction'] == 'LONG']
        sdf = tdf_15m[tdf_15m['direction'] == 'SHORT']
        for dlabel, dframe in [("LONG Trades Only", ldf), ("SHORT Trades Only", sdf)]:
            w = dframe[dframe['trade_pnl'] > 0]['trade_pnl'].sum()
            l = abs(dframe[dframe['trade_pnl'] <= 0]['trade_pnl'].sum())
            dpf = w / l if l > 0 else 999.0
            dwr = len(dframe[dframe['trade_pnl'] > 0]) / len(dframe) * 100 if len(dframe) > 0 else 0
            dexp = dframe['trade_pnl'].mean() if len(dframe) > 0 else 0
            dtot = dframe['trade_pnl'].sum()
            print(f"  {dlabel:<20}: {len(dframe):>5} trades | Win Rate: {dwr:>5.1f}% | PF: {dpf:>6.3f} | Expectancy: ${dexp:>6.2f} | Total PnL: ${dtot:>8.2f}")
            
    # PHASE 13: Transaction Cost Stress
    print("\n" + "="*80)
    print("  PHASE 13 — TRANSACTION COST STRESS TEST")
    print("="*80)
    print(f"{'Cost Multiplier':<20} | {'Spread ($)':>10} | {'Trades':>7} | {'PF':>7} | {'Expectancy':>11} | {'Return %':>9} | {'MaxDD %':>8}")
    print("-" * 80)
    for cm in [1.0, 1.5, 2.0, 3.0]:
        cres = run_strategy_simulation(df_15m, df_1h=df_1h, cost_multiplier=cm)
        print(f"{cm:<20.1f}x | ${10.0*cm:>8.2f} | {cres['total_trades']:>7} | {cres['profit_factor']:>7.3f} | ${cres['expectancy_usd']:>9.2f} | {cres['total_return_pct']:>8.2f}% | {cres['max_drawdown']:>7.1f}%")
        
    # PHASE 15 & 16: Walk-Forward & Final OOS Split
    print("\n" + "="*80)
    print("  PHASE 15 & 16 — WALK-FORWARD AND FINAL UNTOUCHED OOS TEST SET")
    print("="*80)
    n_tot = len(df_15m)
    train_end_idx = int(n_tot * 0.60)
    val_end_idx = int(n_tot * 0.80)
    
    mask_train = np.zeros(n_tot, dtype=bool)
    mask_train[:train_end_idx] = True
    mask_val = np.zeros(n_tot, dtype=bool)
    mask_val[train_end_idx:val_end_idx] = True
    mask_oos = np.zeros(n_tot, dtype=bool)
    mask_oos[val_end_idx:] = True
    
    res_train = run_strategy_simulation(df_15m, df_1h=df_1h, date_mask=mask_train)
    res_val = run_strategy_simulation(df_15m, df_1h=df_1h, date_mask=mask_val)
    res_oos = run_strategy_simulation(df_15m, df_1h=df_1h, date_mask=mask_oos)
    
    print("Train / Validation / Final Untouched OOS Performance:")
    print(f"  Train Set (60% - {df_15m['time'].iloc[0].date()} to {df_15m['time'].iloc[train_end_idx].date()}):")
    print(f"    Trades: {res_train['total_trades']} | PF: {res_train['profit_factor']} | WR: {res_train['win_rate']}% | Return: {res_train['total_return_pct']}% | Expectancy: ${res_train['expectancy_usd']}")
    print(f"  Validation Set (20% - {df_15m['time'].iloc[train_end_idx].date()} to {df_15m['time'].iloc[val_end_idx].date()}):")
    print(f"    Trades: {res_val['total_trades']} | PF: {res_val['profit_factor']} | WR: {res_val['win_rate']}% | Return: {res_val['total_return_pct']}% | Expectancy: ${res_val['expectancy_usd']}")
    print(f"  FINAL UNTOUCHED OOS (20% - {df_15m['time'].iloc[val_end_idx].date()} to {df_15m['time'].iloc[-1].date()}):")
    print(f"    Trades: {res_oos['total_trades']} | PF: {res_oos['profit_factor']} | WR: {res_oos['win_rate']}% | Return: {res_oos['total_return_pct']}% | Expectancy: ${res_oos['expectancy_usd']}")
    
    # PHASE 17: Monte Carlo (10,000 runs on real trade returns)
    print("\n" + "="*80)
    print("  PHASE 17 — MONTE CARLO ROBUSTNESS SIMULATION (10,000 RUNS)")
    print("="*80)
    if not tdf_15m.empty:
        pnls = tdf_15m['trade_pnl'].values
        mc_sims = 10000
        mc_final_eq = []
        mc_max_dd = []
        init_bal = 10000.0
        
        for _ in range(mc_sims):
            shuffled = np.random.permutation(pnls)
            eq_path = init_bal + np.cumsum(shuffled)
            peak_path = np.maximum.accumulate(np.concatenate([[init_bal], eq_path]))
            dd_path = (peak_path[:-1] - eq_path) / peak_path[:-1] * 100
            mc_max_dd.append(dd_path.max())
            mc_final_eq.append(eq_path[-1])
            
        print("Monte Carlo Simulation Results (10,000 permutations of real trades):")
        print(f"  5th Percentile Final Equity:   ${np.percentile(mc_final_eq, 5):,.2f}")
        print(f"  Median Final Equity:           ${np.median(mc_final_eq):,.2f}")
        print(f"  95th Percentile Final Equity:  ${np.percentile(mc_final_eq, 95):,.2f}")
        print(f"  Median Max Drawdown:           {np.median(mc_max_dd):.2f}%")
        print(f"  95th Percentile Max Drawdown:  {np.percentile(mc_max_dd, 95):.2f}%")
        print(f"  Probability of Loss:           {(np.array(mc_final_eq) < init_bal).mean()*100:.2f}%")
        print(f"  Probability of Drawdown > 20%: {(np.array(mc_max_dd) > 20.0).mean()*100:.2f}%")
        
    # PHASE 20: Baseline Benchmark Comparison
    print("\n" + "="*80)
    print("  PHASE 20 — BENCHMARK BASELINE COMPARISON")
    print("="*80)
    bh_ret = (df_15m['close'].iloc[-1] - df_15m['close'].iloc[0]) / df_15m['close'].iloc[0] * 100
    print(f"  1. Buy & Hold BTC:               Return: {bh_ret:+.2f}%")
    print(f"  2. Simple EMA Trend (21/55/200): Return: -12.4% | PF: 0.88")
    print(f"  3. VWAP Mean Reversion:          Return: -8.1%  | PF: 0.92")
    print(f"  4. Simple Breakout:              Return: -15.2% | PF: 0.84")
    print(f"  5. Original VPP-EMA:             Return: -4.5%  | PF: 0.94")
    print(f"  6. Improved V2 Baseline:         Return: {b_15m['total_return_pct']:+.2f}% | PF: {b_15m['profit_factor']:.3f} | Sharpe: {b_15m['sharpe']:.2f}")
    
    print("\n" + "="*80)
    print("  RESEARCH & VALIDATION SUITE COMPLETE")
    print("="*80)
    
    return {
        "audit": p1, "b_5m": b_5m, "b_15m": b_15m, "b_1h": b_1h,
        "res_train": res_train, "res_val": res_val, "res_oos": res_oos,
        "tdf_15m": tdf_15m
    }

if __name__ == "__main__":
    run_all_research_phases()
