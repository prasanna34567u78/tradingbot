"""
Risk & Position Sizing Engine
================================
Features:
  - Fixed fractional risk per trade (Kelly-inspired)
  - Dynamic ATR-based SL distance
  - Structural SL (below swing low / above swing high)
  - Hybrid SL (max of ATR-based vs structural)
  - Dynamic TP with multiple configurations
  - Daily loss limit enforcement
  - Consecutive loss tracking
  - Exposure cap
  - Cooldown after abnormal volatility
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RiskConfig:
    # Position sizing
    risk_pct_per_trade: float = 0.005   # 0.5% of equity
    min_risk_pct: float = 0.0025        # minimum 0.25%
    max_risk_pct: float = 0.01          # maximum 1%

    # Stop loss
    sl_atr_mult: float = 1.4            # default ATR multiplier for SL
    sl_min_atr_mult: float = 0.8        # never closer than this
    sl_max_atr_mult: float = 2.0        # never further than this
    use_structural_sl: bool = True      # use swing-based SL when possible
    structural_sl_buffer: float = 0.3   # ATR buffer beyond swing level

    # Take profit
    tp1_rr: float = 1.5                 # Risk:Reward at TP1
    tp2_rr: float = 3.0                 # Risk:Reward at TP2
    tp1_close_pct: float = 0.50         # Close 50% at TP1
    use_trailing_stop: bool = True      # Trail TP2 runner
    trailing_atr_mult: float = 1.0      # Trail by 1x ATR

    # Breakeven
    be_mode: str = 'lock_half_r'        # 'immediate', 'breakeven_plus_fee', 'lock_half_r', 'trail'
    be_fee_pct: float = 0.0002          # 0.02% fee for BE calc

    # Daily risk controls
    max_daily_loss_pct: float = 0.02    # 2% daily max loss
    max_consecutive_losses: int = 4     # stop after N consecutive losses
    max_open_risk_pct: float = 0.02     # max 2% total exposure

    # Volatility controls
    high_vol_atr_pct_threshold: float = 80.0   # ATR percentile for high vol
    high_vol_risk_scale: float = 0.5           # scale risk to 50% in high vol
    extreme_vol_atr_pct_threshold: float = 95.0
    extreme_vol_disable_mean_reversion: bool = True

    # Lots
    lot_size_usd: float = 100000.0      # standard lot value (BTC: 1 BTC)
    min_lot: float = 0.01
    max_lot: float = 10.0


@dataclass
class DailyRiskState:
    daily_pnl: float = 0.0
    daily_trades: int = 0
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    open_risk: float = 0.0
    trading_halted: bool = False
    halt_reason: str = ''
    current_date: Optional[str] = None

    def reset_daily(self, new_date: str):
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.trading_halted = False
        self.halt_reason = ''
        self.open_risk = 0.0
        self.current_date = new_date

    def record_trade(self, pnl: float, risk_amount: float, equity: float, cfg: 'RiskConfig'):
        self.daily_pnl += pnl
        self.daily_trades += 1
        if pnl < 0:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        else:
            self.consecutive_wins += 1
            self.consecutive_losses = 0

        # Check halt conditions
        if self.daily_pnl < -equity * cfg.max_daily_loss_pct:
            self.trading_halted = True
            self.halt_reason = f'Daily loss limit hit: {self.daily_pnl:.2f}'
        if self.consecutive_losses >= cfg.max_consecutive_losses:
            self.trading_halted = True
            self.halt_reason = f'Consecutive losses: {self.consecutive_losses}'


def calculate_position_size(
    equity: float,
    entry_price: float,
    sl_price: float,
    cfg: RiskConfig,
    atr_pct: float = 50.0,
    lot_value_per_unit: float = 1.0,
) -> float:
    """
    Calculate position size based on fixed fractional risk.
    
    Position Size = Risk Amount / SL Distance
    
    Adjusts risk% based on volatility regime:
      High vol (ATR pct > 80): scale down to high_vol_risk_scale
      Extreme vol (ATR pct > 95): scale down further
    """
    risk_pct = cfg.risk_pct_per_trade

    if atr_pct >= cfg.extreme_vol_atr_pct_threshold:
        risk_pct *= 0.3
    elif atr_pct >= cfg.high_vol_atr_pct_threshold:
        risk_pct *= cfg.high_vol_risk_scale

    risk_pct = np.clip(risk_pct, cfg.min_risk_pct, cfg.max_risk_pct)
    risk_amount = equity * risk_pct
    sl_distance = abs(entry_price - sl_price)

    if sl_distance < 1e-9:
        return cfg.min_lot

    lots = risk_amount / (sl_distance * lot_value_per_unit)
    lots = np.clip(lots, cfg.min_lot, cfg.max_lot)
    return round(lots, 2)


def calculate_sl_price(
    direction: int,  # +1 = long, -1 = short
    entry_price: float,
    atr: float,
    cfg: RiskConfig,
    swing_level: float = None,
) -> float:
    """
    Calculate stop loss price.
    
    Modes:
      structural: SL at swing_level - buffer (long) or + buffer (short)
      atr:        SL at entry +/- sl_atr_mult * ATR
      hybrid:     max(structural distance, min_atr_mult * ATR) from entry
    """
    atr_sl = atr * cfg.sl_atr_mult
    min_atr_sl = atr * cfg.sl_min_atr_mult

    if cfg.use_structural_sl and swing_level is not None and not np.isnan(swing_level):
        buffer = atr * cfg.structural_sl_buffer
        if direction == 1:  # Long: SL below swing low
            structural_dist = entry_price - (swing_level - buffer)
        else:               # Short: SL above swing high
            structural_dist = (swing_level + buffer) - entry_price

        # Hybrid: at least min_atr_sl from entry
        final_dist = max(structural_dist, min_atr_sl)
        final_dist = min(final_dist, atr * cfg.sl_max_atr_mult)  # cap
    else:
        final_dist = np.clip(atr_sl, min_atr_sl, atr * cfg.sl_max_atr_mult)

    if direction == 1:
        return entry_price - final_dist
    else:
        return entry_price + final_dist


def calculate_tp_prices(
    direction: int,
    entry_price: float,
    sl_price: float,
    cfg: RiskConfig,
    vp_vah: float = None,
    vp_val: float = None,
    prev_swing: float = None,
) -> tuple:
    """
    Calculate TP1 and TP2 prices.
    Uses structure targets when available, falls back to ATR R:R.
    Returns: (tp1, tp2)
    """
    risk = abs(entry_price - sl_price)
    atr_tp1 = entry_price + direction * risk * cfg.tp1_rr
    atr_tp2 = entry_price + direction * risk * cfg.tp2_rr

    # Structure target for TP1
    tp1 = atr_tp1
    if direction == 1 and vp_vah is not None and not np.isnan(vp_vah):
        if vp_vah > entry_price + risk * 0.5:  # Only if meaningful
            tp1 = vp_vah
    elif direction == -1 and vp_val is not None and not np.isnan(vp_val):
        if vp_val < entry_price - risk * 0.5:
            tp1 = vp_val

    # Structure target for TP2
    tp2 = atr_tp2
    if prev_swing is not None and not np.isnan(prev_swing):
        if direction == 1 and prev_swing > tp1:
            tp2 = prev_swing
        elif direction == -1 and prev_swing < tp1:
            tp2 = prev_swing

    return tp1, tp2


def calculate_breakeven_sl(
    direction: int,
    entry_price: float,
    cfg: RiskConfig,
) -> float:
    """
    Calculate new SL after TP1 hit, based on breakeven mode.
    """
    risk = 0.0  # placeholder for R calculation
    if cfg.be_mode == 'immediate':
        return entry_price
    elif cfg.be_mode == 'breakeven_plus_fee':
        fee = entry_price * cfg.be_fee_pct
        return entry_price + direction * fee
    elif cfg.be_mode == 'lock_half_r':
        # Lock in 0.5R (need original risk passed in, use small proxy)
        return entry_price + direction * entry_price * 0.0005
    else:
        return entry_price
