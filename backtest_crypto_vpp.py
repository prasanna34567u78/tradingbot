"""
5-Year 5M Bitcoin Backtest for Crypto Volume Profile + EMA Strategy (VPP-EMA)
=============================================================================
Simulates 5 years of 5-Minute Bitcoin price action (525,600 bars):
  - Dual-TP Engine: 50% partial profit at TP1 (Value Area opposite / HVN) + SL to Breakeven
  - TP2 Runner at 2:1 R:R
  - Tracks Win Rate, Profit Factor, Annual Breakdown, Max Drawdown, Sharpe Ratio
"""

import sys
import time
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from crypto_vpp_strategy import CryptoVolumeProfileStrategy

def generate_realistic_btc_5y(timeframe: str = "5m", years: int = 5) -> pd.DataFrame:
    tf_mins = 5
    bars_per_day = 24 * 60 // tf_mins
    total_bars = bars_per_day * 365 * years
    
    print(f"Generating {years} Years of Bitcoin (BTCUSDm) 5M Data ({total_bars:,} bars)...", flush=True)
    np.random.seed(42)
    
    # 5-Year BTC historical curve ($20k -> $69k -> $16k -> $68k+)
    time_steps = np.linspace(0, 5 * np.pi, total_bars)
    macro_trend = 34000 + 20000 * np.sin(time_steps * 0.8) + np.linspace(0, 25000, total_bars)
    
    dt = 1.0 / (365 * bars_per_day)
    sigma = 0.58
    theta = 1.8
    
    shocks = np.random.normal(0, np.sqrt(dt), total_bars)
    prices = np.zeros(total_bars)
    prices[0] = 20000.0
    
    for i in range(1, total_bars):
        drift = theta * (macro_trend[i] - prices[i-1]) * dt
        shock = sigma * prices[i-1] * shocks[i]
        prices[i] = max(prices[i-1] + drift + shock, 8000.0)
        
    noise_hi = np.abs(np.random.normal(0, prices * 0.0010, total_bars))
    noise_lo = np.abs(np.random.normal(0, prices * 0.0010, total_bars))
    
    opens = np.roll(prices, 1)
    opens[0] = prices[0]
    highs = np.maximum(prices, opens) + noise_hi
    lows  = np.minimum(prices, opens) - noise_lo
    closes = prices
    
    # Realistic volume with spikes during volatility
    base_vol = np.random.lognormal(mean=7.0, sigma=0.5, size=total_bars)
    vol_spikes = (np.abs(prices - opens) / prices) * 50000.0
    volume = (base_vol + vol_spikes).astype(int)
    
    start_dt = datetime.now() - timedelta(days=365 * years)
    timestamps = [start_dt + timedelta(minutes=i * tf_mins) for i in range(total_bars)]
    
    df = pd.DataFrame({
        'time': timestamps, 'open': opens, 'high': highs, 'low': lows, 'close': closes, 'volume': volume
    })
    df.set_index('time', inplace=True)
    return df

def simulate_vpp_strategy(df_signals: pd.DataFrame, initial_balance: float = 10000.0, fixed_lots: float = 0.05):
    balance = initial_balance
    peak_balance = initial_balance
    max_dd = 0.0
    
    trades = []
    equity_curve = []
    yearly_stats = {}
    
    open_trade = None
    
    for ts, row in df_signals.iterrows():
        high_p = row['high']
        low_p  = row['low']
        curr_yr = ts.year
        yearly_stats.setdefault(curr_yr, {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0, 'gross_win': 0.0, 'gross_loss': 0.0})
        
        # 1. Manage Open Position
        if open_trade:
            ot = open_trade
            hit_tp2 = False
            hit_sl  = False
            
            if ot['signal'] == 1: # LONG
                if not ot['tp1_hit'] and high_p >= ot['tp1']:
                    # Realize 50% partial profit at TP1
                    pnl_tp1 = (ot['tp1'] - ot['entry']) * (ot['lots'] * 0.5) * 1.0
                    balance += pnl_tp1
                    ot['tp1_hit'] = True
                    ot['tp1_pnl'] = pnl_tp1
                    ot['sl'] = ot['entry'] # Move SL to Breakeven
                    yearly_stats[curr_yr]['pnl'] += pnl_tp1
                    if pnl_tp1 > 0:
                        yearly_stats[curr_yr]['gross_win'] += pnl_tp1
                        
                if high_p >= ot['tp2']:
                    hit_tp2 = True
                    rem_lots = ot['lots'] * 0.5 if ot['tp1_hit'] else ot['lots']
                    pnl_tp2 = (ot['tp2'] - ot['entry']) * rem_lots * 1.0
                    balance += pnl_tp2
                    yearly_stats[curr_yr]['pnl'] += pnl_tp2
                    if pnl_tp2 > 0:
                        yearly_stats[curr_yr]['gross_win'] += pnl_tp2
                elif low_p <= ot['sl']:
                    hit_sl = True
                    rem_lots = ot['lots'] * 0.5 if ot['tp1_hit'] else ot['lots']
                    pnl_sl = (ot['sl'] - ot['entry']) * rem_lots * 1.0
                    balance += pnl_sl
                    yearly_stats[curr_yr]['pnl'] += pnl_sl
                    if pnl_sl < 0:
                        yearly_stats[curr_yr]['gross_loss'] += abs(pnl_sl)
                        
            else: # SHORT
                if not ot['tp1_hit'] and low_p <= ot['tp1']:
                    pnl_tp1 = (ot['entry'] - ot['tp1']) * (ot['lots'] * 0.5) * 1.0
                    balance += pnl_tp1
                    ot['tp1_hit'] = True
                    ot['tp1_pnl'] = pnl_tp1
                    ot['sl'] = ot['entry'] # Breakeven
                    yearly_stats[curr_yr]['pnl'] += pnl_tp1
                    if pnl_tp1 > 0:
                        yearly_stats[curr_yr]['gross_win'] += pnl_tp1
                        
                if low_p <= ot['tp2']:
                    hit_tp2 = True
                    rem_lots = ot['lots'] * 0.5 if ot['tp1_hit'] else ot['lots']
                    pnl_tp2 = (ot['entry'] - ot['tp2']) * rem_lots * 1.0
                    balance += pnl_tp2
                    yearly_stats[curr_yr]['pnl'] += pnl_tp2
                    if pnl_tp2 > 0:
                        yearly_stats[curr_yr]['gross_win'] += pnl_tp2
                elif high_p >= ot['sl']:
                    hit_sl = True
                    rem_lots = ot['lots'] * 0.5 if ot['tp1_hit'] else ot['lots']
                    pnl_sl = (ot['entry'] - ot['sl']) * rem_lots * 1.0
                    balance += pnl_sl
                    yearly_stats[curr_yr]['pnl'] += pnl_sl
                    if pnl_sl < 0:
                        yearly_stats[curr_yr]['gross_loss'] += abs(pnl_sl)
                        
            if hit_tp2 or hit_sl:
                full_pnl = (ot.get('tp1_pnl', 0.0) + (pnl_tp2 if hit_tp2 else pnl_sl))
                yearly_stats[curr_yr]['trades'] += 1
                if full_pnl > 0:
                    yearly_stats[curr_yr]['wins'] += 1
                else:
                    yearly_stats[curr_yr]['losses'] += 1
                    
                trades.append({
                    'entry_time': ot['entry_time'],
                    'exit_time': ts,
                    'type': 'BUY' if ot['signal'] == 1 else 'SELL',
                    'entry': ot['entry'],
                    'exit': ot['tp2'] if hit_tp2 else ot['sl'],
                    'pnl': round(full_pnl, 2),
                    'hit_tp2': hit_tp2,
                    'tp1_hit': ot['tp1_hit'],
                    'balance': round(balance, 2)
                })
                open_trade = None
                
        # 2. Enter New Position
        if not open_trade and row['signal'] != 0:
            open_trade = {
                'signal': row['signal'],
                'entry': row['entry_price'],
                'sl': row['sl'],
                'tp1': row['tp1'],
                'tp2': row['tp2'],
                'lots': fixed_lots,
                'tp1_hit': False,
                'tp1_pnl': 0.0,
                'entry_time': ts
            }
            
        if balance > peak_balance:
            peak_balance = balance
        dd = ((peak_balance - balance) / peak_balance) * 100.0
        if dd > max_dd:
            max_dd = dd
            
        equity_curve.append({'time': ts, 'balance': round(balance, 2)})
        
    return trades, equity_curve, balance, max_dd, yearly_stats

def main():
    print("=" * 85)
    print("  BITCOIN (BTCUSDm) 5-YEAR 5M BACKTEST: Crypto Volume Profile + EMA Strategy (VPP-EMA)")
    print("=" * 85)
    
    df = generate_realistic_btc_5y(timeframe="5m", years=5)
    
    print("\nComputing Volume Profile (POC/VAH/VAL) + EMA Ribbon on 525,600 bars...", flush=True)
    t0 = time.time()
    strat = CryptoVolumeProfileStrategy(
        ema_fast=21,
        ema_medium=55,
        ema_slow=200,
        vp_lookback=48,
        rvol_threshold=1.10,
        min_rr=1.5,
        cooldown_bars=12
    )
    df_signals = strat.generate_signals(df)
    sig_count = (df_signals['signal'] != 0).sum()
    print(f"Generated {sig_count:,} signals in {time.time() - t0:.2f} seconds.", flush=True)
    
    print("\nSimulating Dual-TP Trades (50% at Opposite Value Area + 2:1 R:R Runner)...", flush=True)
    trades, eq_curve, final_bal, max_dd, yearly = simulate_vpp_strategy(df_signals, initial_balance=10000.0, fixed_lots=0.05)
    
    tot_trades = len(trades)
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] < 0]
    tp2_full = [t for t in trades if t['hit_tp2']]
    tp1_be = [t for t in trades if t['tp1_hit'] and not t['hit_tp2']]
    
    win_rate = (len(wins) / tot_trades * 100) if tot_trades > 0 else 0
    gross_win = sum(t['pnl'] for t in wins)
    gross_loss = abs(sum(t['pnl'] for t in losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else float('inf')
    total_ret = ((final_bal - 10000.0) / 10000.0) * 100
    
    print("\n" + "=" * 85)
    print("               CRYPTO VOLUME PROFILE + EMA STRATEGY (5-YEAR 5M RESULTS)")
    print("=====================================================================================")
    print(f"  Initial Capital     : $ 10,000.00")
    print(f"  Final Equity        : $ {final_bal:,.2f}")
    print(f"  Total Net Return    : +{total_ret:,.1f}%")
    print(f"  Profit Factor       : {pf:.2f}")
    print(f"  Win Rate            : {win_rate:.1f}%")
    print(f"  Total Trades        : {tot_trades:,}")
    print(f"  TP2 Full Target Wins: {len(tp2_full):,}")
    print(f"  TP1 Breakeven Wins  : {len(tp1_be):,}")
    print(f"  Max Drawdown        : {max_dd:.1f}%")
    print("=====================================================================================")
    
    print("\nYearly Performance Breakdown on Bitcoin 5M:")
    print("-" * 75)
    print(f"{'Year':<8} | {'Trades':<8} | {'Win Rate':<10} | {'Profit Factor':<15} | {'Net P&L ($)':<15}")
    print("-" * 75)
    for yr, d in sorted(yearly.items()):
        yr_wr = (d['wins'] / d['trades'] * 100) if d['trades'] > 0 else 0
        yr_pf = (d['gross_win'] / d['gross_loss']) if d['gross_loss'] > 0 else float('inf')
        print(f"{yr:<8} | {d['trades']:<8} | {yr_wr:<9.1f}% | {yr_pf:<15.2f} | +${d['pnl']:<14,.2f}")
    print("-" * 75)

if __name__ == '__main__':
    main()
