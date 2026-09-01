"""
Trend-Adaptive Liquidity Sweep Structure Strategy Engine
=========================================================
Institutional Execution Engine:
- In Macro Uptrend (Bullish):
    • Detects Sell-Side Liquidity (SSL) sweep below swing lows.
    • Identifies 5M Resistance Base & Market Structure Shift (MSS) breakout.
    • Enters on 50% discount pullback / FVG retest of breakout bar.
    • Stop Loss: Placed just below the liquidity sweep low.
    • Take Profit: Fixed 1:3.0 Risk:Reward target.
- In Macro Downtrend (Bearish):
    • Detects Buy-Side Liquidity (BSL) sweep above swing highs.
    • Identifies 5M Support Base breakdown.
    • Enters on full closed breakdown candle.
    • Stop Loss: Placed just above the liquidity sweep high.
    • Take Profit: Fixed 1:2.0 Risk:Reward target.
- Operates during high-alpha global market sessions (Asian + NY Power + Overnight), avoiding choppy London fakeouts.
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class SweepStructureStrategy:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.sweep_lookback = int(self.config.get('sweep_lookback', 15))
        self.min_base_bars = int(self.config.get('min_base_bars', 2))
        self.max_base_bars = int(self.config.get('max_base_bars', 10))
        self.sl_buffer_pts = float(self.config.get('sl_buffer_pts', 0.35))
        self.buy_rr = float(self.config.get('buy_rr', 3.0))
        self.sell_rr = float(self.config.get('sell_rr', 2.0))
        self.spread_pts = float(self.config.get('spread_pts', 0.35))
        self.session_filter = bool(self.config.get('session_filter', True))
        # 3 Winning Sessions: Asian (00-07 UTC), NY Power (13-18 UTC), Overnight (18-00 UTC)
        self.allowed_hours = set(range(0, 7)) | set(range(13, 24))

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Processes OHLCV dataframe and marks BUY (+1) or SELL (-1) signals on confirmed closed bars.
        """
        if df is None or len(df) < 50:
            return df

        df = df.copy()
        n = len(df)
        h = df['high'].values
        l = df['low'].values
        c = df['close'].values
        o = df['open'].values

        # Determine time / hour
        if 'time' in df.columns:
            df['time_dt'] = pd.to_datetime(df['time'])
            hours = df['time_dt'].dt.hour.values
        else:
            hours = np.zeros(n, dtype=int)

        # Precompute ATR & EMAs
        tr = np.zeros(n)
        for i in range(1, n):
            tr[i] = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))
        atr = pd.Series(tr).ewm(span=14, adjust=False).mean().values
        e50 = pd.Series(c).ewm(span=50, adjust=False).mean().values
        e200 = pd.Series(c).ewm(span=200, adjust=False).mean().values

        signals = np.zeros(n, dtype=int)
        entry_prices = np.full(n, np.nan)
        stop_losses = np.full(n, np.nan)
        take_profits = np.full(n, np.nan)
        rr_ratios = np.full(n, np.nan)
        setup_types = [''] * n

        for i in range(30, n):
            hr = hours[i]
            if self.session_filter and hr not in self.allowed_hours:
                continue

            a = atr[i]
            if a <= 0.15:
                continue

            macro_bull = e50[i] > e200[i]
            macro_bear = e50[i] < e200[i]

            buy_setup = False
            sell_setup = False
            sweep_low = 0.0
            sweep_high = 0.0

            # ── 1. BUY SETUP (Bullish Trend Only) ──
            if macro_bull:
                for base_len in range(self.min_base_bars, self.max_base_bars + 1):
                    sweep_idx = i - base_len
                    if sweep_idx < self.sweep_lookback:
                        continue
                    prev_low_ref = l[sweep_idx - self.sweep_lookback : sweep_idx].min()
                    if l[sweep_idx] <= prev_low_ref: # Liquidity sweep below swing low
                        sweep_low = l[max(0, sweep_idx - 1) : i].min()
                        base_highs = h[sweep_idx + 1 : i]
                        if len(base_highs) >= self.min_base_bars:
                            res_lvl = base_highs.max()
                            if c[i] > res_lvl and c[i] > o[i]:
                                buy_setup = True
                                break

            # ── 2. SELL SETUP (Bearish Trend Only) ──
            elif macro_bear:
                for base_len in range(self.min_base_bars, self.max_base_bars + 1):
                    sweep_idx = i - base_len
                    if sweep_idx < self.sweep_lookback:
                        continue
                    prev_high_ref = h[sweep_idx - self.sweep_lookback : sweep_idx].max()
                    if h[sweep_idx] >= prev_high_ref: # Liquidity sweep above swing high
                        sweep_high = h[max(0, sweep_idx - 1) : i].max()
                        base_lows = l[sweep_idx + 1 : i]
                        if len(base_lows) >= self.min_base_bars:
                            sup_lvl = base_lows.min()
                            if c[i] < sup_lvl and c[i] < o[i]:
                                sell_setup = True
                                break

            if buy_setup:
                b_low = l[i]
                b_high = h[i]
                entry = b_low + 0.50 * (b_high - b_low) + self.spread_pts # 50% discount retest entry
                sl = sweep_low - self.sl_buffer_pts
                risk = entry - sl
                if 0.8 <= risk <= 20.0:
                    tp = entry + self.buy_rr * risk
                    signals[i] = 1
                    entry_prices[i] = entry
                    stop_losses[i] = sl
                    take_profits[i] = tp
                    rr_ratios[i] = self.buy_rr
                    setup_types[i] = 'SWEEP_BUY_1:3'

            elif sell_setup:
                entry = c[i] - self.spread_pts
                sl = sweep_high + self.sl_buffer_pts
                risk = sl - entry
                if 0.8 <= risk <= 20.0:
                    tp = entry - self.sell_rr * risk
                    signals[i] = -1
                    entry_prices[i] = entry
                    stop_losses[i] = sl
                    take_profits[i] = tp
                    rr_ratios[i] = self.sell_rr
                    setup_types[i] = 'SWEEP_SELL_1:2'

        df['signal'] = signals
        df['entry_price'] = entry_prices
        df['stop_loss'] = stop_losses
        df['take_profit'] = take_profits
        df['rr_ratio'] = rr_ratios
        df['setup_type'] = setup_types
        return df
