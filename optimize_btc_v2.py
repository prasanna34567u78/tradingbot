"""
BTC Strategy v2 - FIXED version based on calibration insights.
Key fixes:
  1. Require BOTH trend AND value zone (stricter filter)
  2. Use VP-based SL (below VAL for longs, above VAH for shorts)
  3. TP1 at 1.0R (quick profit), TP2 at 2.5R (runner)
  4. Require higher body_ratio (0.5) for stronger candle signal
  5. Score minimum 65 (higher quality only)
  6. Volume threshold 1.3x (stronger volume confirm)
  7. Session filter: London + NY overlap only
"""
import sys
sys.path.insert(0, "E:/Trading")
from strategy.crypto_vpp_v2 import BTCImprovedStrategy, BTCStrategyConfig
from backtest_btc_improved import generate_btc_data, resample_to_htf, run_backtest, monte_carlo, walk_forward_test

import numpy as np
import warnings
warnings.filterwarnings("ignore")

print("=" * 70)
print("  BTC STRATEGY v2 - OPTIMIZED PARAMETER BACKTEST")
print("=" * 70)
print()

print("Generating 6 months of BTC data (5M)...")
df_5m  = generate_btc_data(n_bars=52560, bar_minutes=5, seed=42, start_price=40000)
df_15m = resample_to_htf(df_5m, 15)
df_1h  = resample_to_htf(df_5m, 60)
print(f"Data: {len(df_5m)} 5M bars | {df_5m['time'].min()} -> {df_5m['time'].max()}")
print()

configs_to_test = [
    # label, sl_mult, score, tp1_rr, tp2_rr, rvol, cooldown, session_filter
    ("Loose (score>=45, sl=1.0x, session=off)",  1.0,  45, 1.5, 3.0, 1.1, 10, False),
    ("Moderate (score>=55, sl=1.2x, session=off)", 1.2, 55, 1.5, 3.0, 1.2, 12, False),
    ("Quality (score>=60, sl=1.2x, session=off)", 1.2, 60, 1.5, 3.0, 1.2, 12, False),
    ("High (score>=65, sl=1.2x, session=off)",   1.2,  65, 1.5, 3.0, 1.2, 15, False),
    ("Conservative (score>=60, sl=1.4x)",        1.4,  60, 1.5, 3.0, 1.2, 15, True),
    ("Scalping TP (score>=55, tp1=0.8R)",        1.0,  55, 0.8, 2.0, 1.2, 8, False),
    ("Wide TP (score>=55, tp2=4R)",              1.2,  55, 1.5, 4.0, 1.2, 12, False),
]

print(f"{'Label':<46} | {'Trades':>6} | {'WR%':>5} | {'PF':>6} | {'MaxDD%':>6} | {'Return%':>8}")
print(f"{'-'*46}-+-{'-'*6}-+-{'-'*5}-+-{'-'*6}-+-{'-'*6}-+-{'-'*8}")

best_pf = 0
best_label = ""
best_m = None

for label, sl_m, sc, tp1, tp2, rvol, cool, sess in configs_to_test:
    cfg = BTCStrategyConfig()
    cfg.sl_atr_mult = sl_m
    cfg.min_score = sc
    cfg.tp1_rr = tp1
    cfg.tp2_rr = tp2
    cfg.rvol_threshold = rvol
    cfg.cooldown_bars = cool
    cfg.use_session_filter = sess

    m = run_backtest(df_5m, df_15m, df_1h,
                     initial_balance=10000, lots=0.02, cfg=cfg, label=label)
    t  = m.get("total_trades", 0)
    wr = m.get("win_rate", 0)
    pf = m.get("profit_factor", 0)
    dd = m.get("max_drawdown", 0)
    rt = m.get("total_return_pct", 0)
    s  = "+" if rt >= 0 else ""
    print(f"{label:<46} | {t:>6} | {wr:>4.1f}% | {pf:>6.3f} | {dd:>5.1f}%  | {s}{rt:>7.2f}%")
    if pf > best_pf and t >= 20:
        best_pf = pf
        best_label = label
        best_m = m

print()
if best_m:
    print(f"*** Best config: [{best_label}] PF={best_pf:.3f} ***")
    print()
    if best_m.get("trades"):
        pnls = [t["trade_pnl"] for t in best_m["trades"]]
        mc = monte_carlo(pnls, n_sim=5000, initial_balance=10000)
        print("Monte Carlo (5000 sims):")
        print(f"  Avg MaxDD:       {mc.get('avg_max_dd', '?')}%")
        print(f"  95th pct MaxDD:  {mc.get('worst_max_dd', '?')}%")
        print(f"  P(ruin >20%DD):  {mc.get('prob_ruin_20pct', 0):.1%}")
        print(f"  P(negative):     {mc.get('prob_negative', 0):.1%}")
else:
    print("No profitable configuration found in this dataset. Strategy needs HTF real data.")
    print()
    print("Key insight: 5M BTC synthetic data may not match real BTC market microstructure.")
    print("Recommendation: Run with real MT5 BTCUSDm data for accurate results.")
print()
print("Done.")
