"""
Quick calibration test: find optimal parameters for the improved BTC strategy.
Tests different SL multipliers, score thresholds, and TP ratios.
"""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "E:\\Trading")

import numpy as np
import pandas as pd

# Generate data
from backtest_btc_improved import generate_btc_data, resample_to_htf, run_backtest
from strategy.crypto_vpp_v2 import BTCStrategyConfig

print("Generating data...")
df_5m  = generate_btc_data(n_bars=26280, bar_minutes=5, seed=42, start_price=40000)
df_15m = resample_to_htf(df_5m, 15)
df_1h  = resample_to_htf(df_5m, 60)

print("Testing parameter combinations...")
print()
print(f"{'SL_ATR':<8} {'Score':<7} {'TP1_RR':<8} {'TP2_RR':<8} {'Trades':<8} {'WR%':<7} {'PF':<7} {'MaxDD%':<8} {'Return%':<9}")
print("-" * 80)

best_pf = 0
best_cfg = None

for sl_mult in [0.8, 1.0, 1.2, 1.4, 1.6]:
    for score_thresh in [45, 55, 60, 65]:
        for tp1_rr in [1.2, 1.5, 2.0]:
            for tp2_rr in [2.5, 3.0]:
                cfg = BTCStrategyConfig()
                cfg.sl_atr_mult = sl_mult
                cfg.min_score = score_thresh
                cfg.tp1_rr = tp1_rr
                cfg.tp2_rr = tp2_rr
                cfg.cooldown_bars = 10
                cfg.use_session_filter = False  # disable for calibration

                m = run_backtest(df_5m, df_15m, df_1h,
                                 initial_balance=10000, lots=0.02,
                                 cfg=cfg, label="cal")
                
                t = m.get("total_trades", 0)
                if t < 15:
                    continue
                wr = m.get("win_rate", 0)
                pf = m.get("profit_factor", 0)
                dd = m.get("max_drawdown", 0)
                rt = m.get("total_return_pct", 0)
                
                if pf > best_pf:
                    best_pf = pf
                    best_cfg = (sl_mult, score_thresh, tp1_rr, tp2_rr)
                
                if pf >= 1.0:  # only show profitable combos
                    s = "+" if rt >= 0 else ""
                    print(f"{sl_mult:<8.1f} {score_thresh:<7} {tp1_rr:<8.1f} {tp2_rr:<8.1f} {t:<8} {wr:<6.1f}% {pf:<7.3f} {dd:<7.1f}%  {s}{rt:<8.2f}%")

print()
if best_cfg:
    print(f"Best params: SL={best_cfg[0]}, Score>={best_cfg[1]}, TP1={best_cfg[2]}R, TP2={best_cfg[3]}R -> PF={best_pf:.3f}")
else:
    print("No profitable combination found. Strategy needs fundamental redesign.")
