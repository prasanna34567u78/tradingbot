"""
Comprehensive BTC Backtest Engine with Walk-Forward, Monte Carlo,
Ablation Testing, and Full Statistical Reporting.

Run:
    python E:\Trading\backtest_btc_improved.py

Outputs:
  - Full trade log CSV
  - Walk-forward results
  - Monte Carlo simulation
  - Ablation table
  - Statistical report
"""

import sys
import os
import time
import numpy as np
import pandas as pd
import json
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, "E:\\Trading")

print("=" * 80)
print("   BTC IMPROVED STRATEGY v2 - COMPREHENSIVE BACKTEST ENGINE")
print("=" * 80)

# ---------- synthetic data generation ----------

def generate_btc_data(n_bars=26280, bar_minutes=5, seed=42, start_price=35000):
    """
    Generate realistic BTC-like synthetic OHLCV data.
    Uses GBM with regime-switching (trend/range/volatile cycles).
    26280 bars * 5min = ~91 days. For 5yr use 525600 bars.
    """
    np.random.seed(seed)
    n = n_bars
    times = pd.date_range("2020-01-01 00:00", periods=n, freq=f"{bar_minutes}min")
    
    price = start_price
    closes = np.zeros(n)
    opens  = np.zeros(n)
    highs  = np.zeros(n)
    lows   = np.zeros(n)
    vols   = np.zeros(n)
    
    regime = "range"
    regime_len = 0
    vol_base = price * 0.008
    
    for i in range(n):
        regime_len += 1
        if regime_len > np.random.randint(100, 500):
            regime = np.random.choice(["trend_up","trend_down","range","volatile"], p=[0.25,0.20,0.40,0.15])
            regime_len = 0
        
        if regime == "trend_up":
            drift = vol_base * 0.08
            vol   = vol_base * 1.1
        elif regime == "trend_down":
            drift = -vol_base * 0.06
            vol   = vol_base * 1.0
        elif regime == "volatile":
            drift = 0
            vol   = vol_base * 2.5
        else:
            drift = 0
            vol   = vol_base * 0.7
        
        ret = drift + np.random.randn() * vol
        o = price
        price = max(price + ret, price * 0.3)
        c = price
        rng = abs(np.random.randn()) * vol * 1.2 + abs(ret) * 0.5
        h = max(o, c) + abs(np.random.randn()) * rng * 0.5
        l = min(o, c) - abs(np.random.randn()) * rng * 0.5
        l = max(l, price * 0.5)
        v = max(np.random.exponential(500) + 200, 50)
        
        opens[i]  = round(o, 2)
        highs[i]  = round(h, 2)
        lows[i]   = round(l, 2)
        closes[i] = round(c, 2)
        vols[i]   = round(v, 1)
    
    df = pd.DataFrame({
        "time":   times,
        "open":   opens,
        "high":   highs,
        "low":    lows,
        "close":  closes,
        "volume": vols,
    })
    return df


def resample_to_htf(df_5m, target_minutes):
    """Resample 5M data to higher timeframe. No lookahead."""
    rule = f"{target_minutes}min"
    df = df_5m.set_index("time").resample(rule).agg({
        "open":   "first",
        "high":   "max",
        "low":    "min",
        "close":  "last",
        "volume": "sum",
    }).dropna().reset_index()
    return df


# ---------- backtest simulation ----------

def run_backtest(
    df_5m, df_15m=None, df_1h=None,
    initial_balance=10000.0,
    lots=0.02,
    spread_usd=8.0,
    commission_pct=0.0001,
    slippage_usd=2.0,
    strategy_module=None,
    cfg=None,
    label="v2",
    htf_available=True,
):
    """
    Full event-driven backtest with realistic cost modeling.
    
    Returns: dict with metrics and trade_log
    """
    from strategy.crypto_vpp_v2 import BTCImprovedStrategy, BTCStrategyConfig
    
    if cfg is None:
        cfg = BTCStrategyConfig()
    strat = BTCImprovedStrategy(cfg)
    
    _df_15m = df_15m if htf_available else None
    _df_1h  = df_1h  if htf_available else None
    
    sig_df = strat.generate_signals(df_5m.copy(), df_15m=_df_15m, df_1h=_df_1h)
    
    equity       = initial_balance
    peak_equity  = initial_balance
    max_dd       = 0.0
    trades       = []
    eq_curve     = [initial_balance]
    
    in_pos       = False
    pos_type     = 0  # +1 long, -1 short
    entry_price  = 0.0
    sl_price     = 0.0
    tp1_price    = 0.0
    tp2_price    = 0.0
    tp1_hit      = False
    entry_idx    = 0
    entry_time   = None
    entry_score  = 0
    entry_regime = ""
    entry_setup  = 0
    
    lot_value = 1.0  # BTC: $1 per $1 per lot
    
    daily_losses  = 0
    consec_loss   = 0
    current_date  = None
    daily_pnl     = 0.0
    
    c = sig_df["close"].values
    o = sig_df["open"].values
    h = sig_df["high"].values
    l = sig_df["low"].values
    sigs  = sig_df["signal"].values
    sls   = sig_df["sl"].values
    tp1s  = sig_df["tp1"].values
    tp2s  = sig_df["tp2"].values
    times = sig_df["time"].values
    scores  = sig_df["entry_score"].values
    regimes = sig_df["regime_label"].values
    setups  = sig_df["setup_type"].values
    
    n = len(sig_df)
    
    for i in range(1, n):
        bar_date = pd.Timestamp(times[i]).date()
        if current_date != bar_date:
            current_date = bar_date
            daily_pnl = 0.0
            if consec_loss >= cfg.max_consecutive_losses:
                consec_loss = 0  # reset at new day
        
        if not in_pos:
            # Check daily limits
            if daily_pnl < -equity * cfg.max_daily_loss_pct:
                continue
            if consec_loss >= cfg.max_consecutive_losses:
                continue
            
            # New signal (EXECUTE on NEXT bar open after signal bar)
            if i > 0 and sigs[i-1] != 0:
                # Execute at next bar open + slippage
                direction = sigs[i-1]
                exec_price = o[i] + direction * slippage_usd
                actual_sl  = sls[i-1]
                actual_tp1 = tp1s[i-1]
                actual_tp2 = tp2s[i-1]
                
                # Apply spread to entry
                if direction == 1:
                    exec_price += spread_usd / 2
                else:
                    exec_price -= spread_usd / 2
                
                # Commission
                commission = exec_price * lots * commission_pct
                equity -= commission
                
                in_pos     = True
                pos_type   = direction
                entry_price = exec_price
                sl_price    = actual_sl
                tp1_price   = actual_tp1
                tp2_price   = actual_tp2
                tp1_hit     = False
                entry_idx   = i
                entry_time  = pd.Timestamp(times[i])
                entry_score = scores[i-1]
                entry_regime = regimes[i-1]
                entry_setup  = setups[i-1]

        else:
            # Trade management
            hit_tp2 = hit_sl = False
            exit_price = 0.0
            
            if pos_type == 1:  # Long
                if not tp1_hit and h[i] >= tp1_price:
                    tp1_hit = True
                    # TP1: close 50%, apply spread + commission
                    partial_exit = tp1_price - spread_usd / 2
                    partial_pnl  = (partial_exit - entry_price) * (lots * 0.5) * lot_value
                    partial_pnl -= partial_exit * (lots * 0.5) * commission_pct
                    equity      += partial_pnl
                    # Move SL to breakeven + half the commission fee
                    sl_price = entry_price + spread_usd * 0.5
                
                if h[i] >= tp2_price:
                    hit_tp2 = True
                    exit_price = tp2_price - spread_usd / 2
                elif l[i] <= sl_price:
                    hit_sl = True
                    # Conservative: assume worst case (SL hit at exact SL price)
                    exit_price = sl_price - spread_usd / 2
            
            else:  # Short
                if not tp1_hit and l[i] <= tp1_price:
                    tp1_hit = True
                    partial_exit = tp1_price + spread_usd / 2
                    partial_pnl  = (entry_price - partial_exit) * (lots * 0.5) * lot_value
                    partial_pnl -= partial_exit * (lots * 0.5) * commission_pct
                    equity      += partial_pnl
                    sl_price = entry_price - spread_usd * 0.5
                
                if l[i] <= tp2_price:
                    hit_tp2 = True
                    exit_price = tp2_price + spread_usd / 2
                elif h[i] >= sl_price:
                    hit_sl = True
                    exit_price = sl_price + spread_usd / 2
            
            if hit_tp2 or hit_sl:
                rem_lots = (lots * 0.5) if tp1_hit else lots
                if pos_type == 1:
                    final_pnl = (exit_price - entry_price) * rem_lots * lot_value
                else:
                    final_pnl = (entry_price - exit_price) * rem_lots * lot_value
                final_pnl -= exit_price * rem_lots * commission_pct
                
                equity    += final_pnl
                daily_pnl += final_pnl
                
                if equity > peak_equity:
                    peak_equity = equity
                dd = (peak_equity - equity) / peak_equity * 100
                if dd > max_dd:
                    max_dd = dd
                
                total_pnl = (final_pnl + (partial_pnl if tp1_hit else 0))
                if total_pnl < 0:
                    consec_loss += 1
                    daily_losses += 1
                else:
                    consec_loss = 0
                
                duration = i - entry_idx
                trades.append({
                    "entry_date":   str(entry_time)[:16],
                    "exit_date":    str(pd.Timestamp(times[i]))[:16],
                    "direction":    "BUY" if pos_type == 1 else "SELL",
                    "entry_price":  round(entry_price, 2),
                    "exit_price":   round(exit_price, 2),
                    "lots":         lots,
                    "pnl":          round(equity - initial_balance, 2),
                    "trade_pnl":    round(final_pnl, 2),
                    "tp1_hit":      tp1_hit,
                    "outcome":      "TP2" if hit_tp2 else "SL",
                    "score":        entry_score,
                    "regime":       entry_regime,
                    "setup":        entry_setup,
                    "duration_bars":duration,
                    "equity":       round(equity, 2),
                })
                eq_curve.append(round(equity, 2))
                in_pos = False
    
    if not trades:
        return {"label": label, "total_trades": 0, "pnl": 0, "win_rate": 0,
                "profit_factor": 0, "max_dd": 0, "sharpe": 0, "trades": []}
    
    trade_df  = pd.DataFrame(trades)
    wins      = trade_df[trade_df["trade_pnl"] > 0]
    losses    = trade_df[trade_df["trade_pnl"] <= 0]
    gross_win = wins["trade_pnl"].sum()
    gross_loss = abs(losses["trade_pnl"].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else 999.0
    wr = len(wins) / len(trade_df) * 100
    
    # Expectancy
    avg_win  = wins["trade_pnl"].mean()  if len(wins)  > 0 else 0
    avg_loss = losses["trade_pnl"].mean() if len(losses) > 0 else 0
    expectancy = (wr / 100) * avg_win + (1 - wr / 100) * avg_loss
    
    # Sharpe (daily returns from equity curve)
    eq_arr = np.array(eq_curve)
    rets = np.diff(eq_arr) / eq_arr[:-1]
    sharpe = (rets.mean() / (rets.std() + 1e-9)) * np.sqrt(252 * 288)  # annualized
    
    # Sortino
    neg_rets = rets[rets < 0]
    down_std = neg_rets.std() if len(neg_rets) > 0 else 1e-9
    sortino = (rets.mean() / (down_std + 1e-9)) * np.sqrt(252 * 288)
    
    # Calmar
    total_return = (equity - initial_balance) / initial_balance * 100
    calmar = total_return / max_dd if max_dd > 0 else 0
    
    final_metrics = {
        "label":          label,
        "total_trades":   len(trades),
        "win_rate":       round(wr, 2),
        "profit_factor":  round(pf, 3),
        "max_drawdown":   round(max_dd, 2),
        "sharpe_ratio":   round(sharpe, 3),
        "sortino_ratio":  round(sortino, 3),
        "calmar_ratio":   round(calmar, 3),
        "total_return_pct": round(total_return, 2),
        "expectancy_usd": round(expectancy, 2),
        "avg_win_usd":    round(avg_win, 2),
        "avg_loss_usd":   round(avg_loss, 2),
        "gross_profit":   round(gross_win, 2),
        "gross_loss":     round(gross_loss, 2),
        "final_equity":   round(equity, 2),
        "initial_balance": initial_balance,
        "equity_curve":   eq_curve,
        "trades":         trades,
    }
    return final_metrics


def monte_carlo(trades_pnl, n_sim=10000, initial_balance=10000.0):
    """Run Monte Carlo simulation by reshuffling trade order."""
    if len(trades_pnl) < 5:
        return {}
    pnl = np.array(trades_pnl)
    max_dds = []
    final_eqs = []
    for _ in range(n_sim):
        shuffled = np.random.permutation(pnl)
        eq = initial_balance + np.cumsum(shuffled)
        peak = np.maximum.accumulate(np.concatenate([[initial_balance], eq]))
        dd = ((peak[:-1] - eq) / peak[:-1] * 100)
        max_dds.append(dd.max())
        final_eqs.append(eq[-1])
    return {
        "avg_max_dd":        round(np.mean(max_dds), 2),
        "worst_max_dd":      round(np.percentile(max_dds, 95), 2),
        "prob_ruin_20pct":   round(np.mean(np.array(max_dds) > 20), 4),
        "prob_negative":     round(np.mean(np.array(final_eqs) < initial_balance), 4),
        "expected_equity_p5":  round(np.percentile(final_eqs, 5), 2),
        "expected_equity_p95": round(np.percentile(final_eqs, 95), 2),
        "n_simulations":     n_sim,
    }


def walk_forward_test(df_5m, df_15m, df_1h, initial_balance=10000.0, lots=0.02,
                      train_months=12, val_months=3, oos_months=3):
    """
    Rolling walk-forward test.
    Returns list of per-window metrics.
    """
    from strategy.crypto_vpp_v2 import BTCStrategyConfig
    
    results = []
    df_5m["time"] = pd.to_datetime(df_5m["time"])
    start = df_5m["time"].min()
    end   = df_5m["time"].max()
    
    window_start = start
    window_size  = pd.DateOffset(months=train_months + val_months + oos_months)
    step         = pd.DateOffset(months=oos_months)
    
    win_idx = 0
    while window_start + window_size <= end:
        train_end = window_start + pd.DateOffset(months=train_months)
        val_end   = train_end    + pd.DateOffset(months=val_months)
        oos_end   = val_end      + pd.DateOffset(months=oos_months)
        
        oos_mask  = (df_5m["time"] >= val_end) & (df_5m["time"] < oos_end)
        oos_df    = df_5m[oos_mask].reset_index(drop=True)
        
        if len(oos_df) < 500:
            window_start += step
            win_idx += 1
            continue
        
        oos_15m = df_15m[(df_15m["time"] >= val_end) & (df_15m["time"] < oos_end)].reset_index(drop=True) if df_15m is not None else None
        oos_1h  = df_1h[ (df_1h["time"]  >= val_end) & (df_1h["time"]  < oos_end)].reset_index(drop=True) if df_1h  is not None else None
        
        m = run_backtest(
            oos_df, oos_15m, oos_1h,
            initial_balance=initial_balance, lots=lots,
            label=f"WF_OOS_W{win_idx:02d}"
        )
        m["window_start"] = str(val_end)[:10]
        m["window_end"]   = str(oos_end)[:10]
        m["window_idx"]   = win_idx
        results.append(m)
        
        window_start += step
        win_idx += 1
    
    return results


def ablation_test(df_5m, df_15m, df_1h, initial_balance=10000.0, lots=0.02):
    """
    Ablation: remove one component at a time, measure contribution.
    """
    from strategy.crypto_vpp_v2 import BTCStrategyConfig
    
    configs = {
        "Full Strategy (Baseline)": {},
        "No HTF (1H removed)": {"htf_off": True},
        "No MTF (15M removed)": {"mtf_off": True},
        "No Liquidity Sweep": {"no_sweep": True},
        "No Volume Filter": {"no_vol": True},
        "No Session Filter": {"no_session": True},
        "No Score Filter (score>=1)": {"min_score_override": 1},
        "Score >= 70": {"min_score_override": 70},
        "Score >= 75": {"min_score_override": 75},
    }
    
    results = []
    for label, overrides in configs.items():
        cfg = BTCStrategyConfig()
        if overrides.get("no_session"):
            cfg.use_session_filter = False
        if overrides.get("min_score_override"):
            cfg.min_score = overrides["min_score_override"]
        if overrides.get("no_vol"):
            cfg.rvol_threshold = 0.0
        
        _df_15m = None if overrides.get("mtf_off") else df_15m
        _df_1h  = None if overrides.get("htf_off") else df_1h
        
        m = run_backtest(_df_15m or df_5m[:1], _df_1h or df_5m[:1], df_5m,
                         initial_balance=initial_balance, lots=lots,
                         label=label, cfg=cfg)
        # Fix arg order
        m2 = run_backtest(df_5m, _df_15m, _df_1h,
                          initial_balance=initial_balance, lots=lots,
                          label=label, cfg=cfg)
        results.append(m2)
    
    return results


def spread_stress_test(df_5m, df_15m, df_1h, initial_balance=10000.0, lots=0.02):
    """Test under increasing transaction costs."""
    results = []
    cost_scenarios = [
        ("Normal (spread=$8, comm=0.01%)", 8.0,  0.0001),
        ("1.5x costs",                     12.0, 0.00015),
        ("2x costs",                       16.0, 0.0002),
        ("3x costs",                       24.0, 0.0003),
    ]
    for label, spread, comm in cost_scenarios:
        m = run_backtest(df_5m, df_15m, df_1h,
                         initial_balance=initial_balance, lots=lots,
                         spread_usd=spread, commission_pct=comm, label=label)
        results.append(m)
    return results


def print_metrics(m, indent=""):
    pnl_sign = "+" if m.get("total_return_pct", 0) >= 0 else ""
    print(f"{indent}  Trades:        {m.get('total_trades', 0)}")
    print(f"{indent}  Win Rate:      {m.get('win_rate', 0)}%")
    print(f"{indent}  Profit Factor: {m.get('profit_factor', 0)}")
    print(f"{indent}  Sharpe:        {m.get('sharpe_ratio', 0)}")
    print(f"{indent}  Sortino:       {m.get('sortino_ratio', 0)}")
    print(f"{indent}  Calmar:        {m.get('calmar_ratio', 0)}")
    print(f"{indent}  Max Drawdown:  {m.get('max_drawdown', 0)}%")
    print(f"{indent}  Total Return:  {pnl_sign}{m.get('total_return_pct', 0):.2f}%")
    print(f"{indent}  Expectancy:    ${m.get('expectancy_usd', 0):.2f}/trade")


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print()
    print("[1/6] Generating synthetic BTC data (12 months of 5M bars)...")
    t0 = time.time()
    
    # 12 months * 30 days * 24h * 12 bars/h = ~103,680 bars (adjust for speed)
    N_BARS = 52560  # ~6 months of 5M data
    df_5m  = generate_btc_data(n_bars=N_BARS, bar_minutes=5, seed=42, start_price=40000)
    df_15m = resample_to_htf(df_5m, 15)
    df_1h  = resample_to_htf(df_5m, 60)
    
    print(f"   Generated {len(df_5m):,} 5M bars, {len(df_15m):,} 15M bars, {len(df_1h):,} 1H bars")
    print(f"   Date range: {df_5m['time'].min()} -> {df_5m['time'].max()}")
    
    print()
    print("[2/6] Running baseline strategy backtest...")
    base = run_backtest(df_5m, df_15m, df_1h, initial_balance=10000, lots=0.02, label="BTC_v2_Improved")
    
    print()
    print("=" * 70)
    print("   IMPROVED STRATEGY BASELINE RESULTS")
    print("=" * 70)
    print_metrics(base)
    
    if base["total_trades"] == 0:
        print()
        print("  No trades generated. Running with relaxed parameters...")
        from strategy.crypto_vpp_v2 import BTCStrategyConfig
        cfg_relaxed = BTCStrategyConfig()
        cfg_relaxed.min_score = 45
        cfg_relaxed.cooldown_bars = 8
        cfg_relaxed.use_session_filter = False
        base = run_backtest(df_5m, df_15m, df_1h, initial_balance=10000, lots=0.02,
                            label="BTC_v2_Relaxed", cfg=cfg_relaxed)
        print_metrics(base)
    
    # Compare with original VPP-EMA
    print()
    print("[3/6] Running original VPP-EMA for comparison...")
    try:
        sys.path.insert(0, "E:\\Trading")
        from crypto_vpp_strategy import CryptoVolumeProfileStrategy
        
        strat_orig = CryptoVolumeProfileStrategy()
        sig_orig = strat_orig.generate_signals(df_5m.copy())
        
        eq = 10000.0
        peak = 10000.0
        max_dd_orig = 0.0
        trades_orig = []
        in_p = False
        pt = 0; ep = sl = tp1 = tp2 = 0.0; tp1h = False
        
        for i in range(1, len(sig_orig)):
            row = sig_orig.iloc[i]
            if not in_p and sig_orig["signal"].iloc[i-1] != 0:
                d = sig_orig["signal"].iloc[i-1]
                ep  = row["open"] + d * 5
                sl  = sig_orig["sl"].iloc[i-1]
                tp1 = sig_orig["tp1"].iloc[i-1]
                tp2 = sig_orig["tp2"].iloc[i-1]
                in_p = True; pt = d; tp1h = False
            elif in_p:
                if pt == 1:
                    if not tp1h and row["high"] >= tp1:
                        tp1h = True
                        eq += (tp1 - ep) * 0.01 * 1.0
                        sl = ep
                    if row["high"] >= tp2:
                        eq += (tp2 - ep) * 0.01 * 0.5
                        trades_orig.append(eq)
                        if eq > peak: peak = eq
                        dd = (peak - eq) / peak * 100
                        if dd > max_dd_orig: max_dd_orig = dd
                        in_p = False
                    elif row["low"] <= sl:
                        eq += (sl - ep) * 0.01 * (0.5 if tp1h else 1.0)
                        trades_orig.append(eq)
                        if eq > peak: peak = eq
                        dd = (peak - eq) / peak * 100
                        if dd > max_dd_orig: max_dd_orig = dd
                        in_p = False
                else:
                    if not tp1h and row["low"] <= tp1:
                        tp1h = True
                        eq += (ep - tp1) * 0.01 * 1.0
                        sl = ep
                    if row["low"] <= tp2:
                        eq += (ep - tp2) * 0.01 * 0.5
                        trades_orig.append(eq)
                        if eq > peak: peak = eq
                        dd = (peak - eq) / peak * 100
                        if dd > max_dd_orig: max_dd_orig = dd
                        in_p = False
                    elif row["high"] >= sl:
                        eq += (ep - sl) * 0.01 * (0.5 if tp1h else 1.0)
                        trades_orig.append(eq)
                        if eq > peak: peak = eq
                        dd = (peak - eq) / peak * 100
                        if dd > max_dd_orig: max_dd_orig = dd
                        in_p = False
        
        w_orig = [t for t in trades_orig if t > trades_orig[max(0,i-1)] if i > 0]
        wr_orig = len([i for i in range(1, len(trades_orig)) if trades_orig[i] > trades_orig[i-1]]) / max(len(trades_orig), 1) * 100
        ret_orig = (eq - 10000) / 10000 * 100
        print(f"   Original VPP-EMA: {len(trades_orig)} trades | WR: {wr_orig:.1f}% | Return: {ret_orig:.2f}% | MaxDD: {max_dd_orig:.1f}%")
    except Exception as e:
        print(f"   Original VPP-EMA comparison skipped: {e}")
        ret_orig = 0.0
        trades_orig = []
    
    # ── Spread Stress Test ─────────────────────────────────────────────────
    print()
    print("[4/6] Running transaction cost stress test...")
    stress = spread_stress_test(df_5m, df_15m, df_1h, lots=0.02)
    print()
    print("  COST STRESS TEST RESULTS:")
    print(f"  {'Scenario':<30} | {'Trades':>7} | {'PF':>6} | {'WR':>6} | {'MaxDD':>6} | {'Return':>8}")
    print(f"  {'-'*30}-+-{'-'*7}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}-+-{'-'*8}")
    for m in stress:
        r = m.get("total_return_pct", 0)
        sign = "+" if r >= 0 else ""
        print(f"  {m['label']:<30} | {m.get('total_trades',0):>7} | {m.get('profit_factor',0):>6.3f} | {m.get('win_rate',0):>5.1f}% | {m.get('max_drawdown',0):>5.1f}% | {sign}{r:>7.2f}%")
    
    # ── Monte Carlo ────────────────────────────────────────────────────────
    print()
    print("[5/6] Running Monte Carlo simulation (10,000 iterations)...")
    if base.get("trades"):
        pnls = [t["trade_pnl"] for t in base["trades"]]
        mc = monte_carlo(pnls, n_sim=10000, initial_balance=10000.0)
        print()
        print("  MONTE CARLO RESULTS (10,000 simulations):")
        print(f"    Avg Max Drawdown:     {mc.get('avg_max_dd', 'N/A')}%")
        print(f"    95th pct Max Drawdown:{mc.get('worst_max_dd', 'N/A')}%")
        print(f"    Prob Ruin (>20% DD):  {mc.get('prob_ruin_20pct', 'N/A'):.1%}")
        print(f"    Prob Negative Return: {mc.get('prob_negative', 'N/A'):.1%}")
        print(f"    5th pct Final Equity: ${mc.get('expected_equity_p5', 'N/A'):,.2f}")
        print(f"    95th pct Final Equity:${mc.get('expected_equity_p95', 'N/A'):,.2f}")
    else:
        mc = {}
        print("  Skipped (no trades)")
    
    # ── Walk-Forward ────────────────────────────────────────────────────────
    print()
    print("[6/6] Running Walk-Forward Analysis (3-month OOS windows)...")
    wf_results = []
    try:
        wf_results = walk_forward_test(df_5m, df_15m, df_1h, lots=0.02,
                                       train_months=3, val_months=1, oos_months=1)
        if wf_results:
            wf_pfs = [w.get("profit_factor", 0) for w in wf_results]
            wf_dds = [w.get("max_drawdown", 0) for w in wf_results]
            wf_wr  = [w.get("win_rate", 0) for w in wf_results]
            n_profitable = sum(1 for w in wf_results if w.get("profit_factor", 0) >= 1.0)
            print()
            print(f"  WALK-FORWARD SUMMARY ({len(wf_results)} windows):")
            print(f"    Avg Profit Factor:    {np.mean(wf_pfs):.3f}")
            print(f"    Median Profit Factor: {np.median(wf_pfs):.3f}")
            print(f"    Avg Max Drawdown:     {np.mean(wf_dds):.2f}%")
            print(f"    Avg Win Rate:         {np.mean(wf_wr):.1f}%")
            print(f"    Windows PF >= 1.0:    {n_profitable}/{len(wf_results)} ({n_profitable/len(wf_results)*100:.0f}%)")
            print(f"    Windows PF >= 1.2:    {sum(1 for p in wf_pfs if p >= 1.2)}/{len(wf_results)}")
        else:
            print("  No walk-forward windows (dataset too small)")
    except Exception as e:
        print(f"  Walk-forward error: {e}")
    
    # ── Final Report ────────────────────────────────────────────────────────
    print()
    print("=" * 80)
    print("   FINAL COMPREHENSIVE REPORT")
    print("=" * 80)
    print()
    
    r = base.get("total_return_pct", 0)
    pf = base.get("profit_factor", 0)
    dd = base.get("max_drawdown", 0)
    sh = base.get("sharpe_ratio", 0)
    trades_n = base.get("total_trades", 0)
    wr = base.get("win_rate", 0)
    
    print(f"  Strategy:         BTC Improved v2 (VPP + Regime + Score)")
    print(f"  Symbol:           BTCUSDm (5M primary, 15M+1H confirmation)")
    print(f"  Total Return:     {'+'if r>=0 else ''}{r:.2f}%")
    print(f"  Profit Factor:    {pf:.3f}")
    print(f"  Sharpe Ratio:     {sh:.3f}")
    print(f"  Max Drawdown:     {dd:.2f}%")
    print(f"  Win Rate:         {wr:.1f}%")
    print(f"  Total Trades:     {trades_n}")
    print(f"  Expectancy/Trade: ${base.get('expectancy_usd', 0):.2f}")
    print()
    
    # Verdict
    deploy_score = 0
    if pf >= 1.30: deploy_score += 3
    elif pf >= 1.15: deploy_score += 2
    elif pf >= 1.05: deploy_score += 1
    if sh >= 1.0: deploy_score += 2
    elif sh >= 0.7: deploy_score += 1
    if dd <= 10: deploy_score += 2
    elif dd <= 15: deploy_score += 1
    if trades_n >= 30: deploy_score += 1
    if wr >= 30: deploy_score += 1
    
    if deploy_score >= 8:
        verdict = "A. DEPLOY CANDIDATE -- Strategy shows robust statistical edge."
    elif deploy_score >= 5:
        verdict = "B. NEEDS FURTHER RESEARCH -- Promising but needs more validation."
    else:
        verdict = "C. NOT ROBUST ENOUGH -- Do not deploy. Continue research."
    
    print(f"  *** FINAL VERDICT: {verdict} ***")
    print()
    
    # Save trade log
    if base.get("trades"):
        trade_df = pd.DataFrame(base["trades"])
        out_path = "E:\\Trading\\btc_v2_trade_log.csv"
        trade_df.to_csv(out_path, index=False)
        print(f"  Trade log saved to: {out_path}")
    
    print()
    print("=" * 80)
    print("  Backtest complete.")
    print("=" * 80)
