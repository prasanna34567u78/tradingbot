"""
PDE Strategy Backtest Engine
=============================
Backtests the Premium/Discount/Equilibrium strategy on 5 years of
synthetic OHLCV data (or real MT5 data if available).

Features:
  - Dual-TP system: 50% at TP1, 50% at TP2 (or SL)
  - Tracks equity curve, drawdown, win rate, profit factor
  - Outputs full trade log and a summary report

Usage:
    python backtest_pde.py               # uses synthetic Gold data
    python backtest_pde.py --symbol XAUUSDm --mt5  # uses live MT5 data
"""

import argparse
import sys
import logging
import warnings
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M",
)
logger = logging.getLogger("pde_backtest")

# ── local imports ────────────────────────────────────────────────
try:
    from indicators import SMCIndicators
    from pde_strategy import PDEStrategy
except ImportError as e:
    logger.error(f"Import error: {e}")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# Synthetic OHLCV Generator (Gold-like behaviour)
# ─────────────────────────────────────────────────────────────────
def generate_synthetic_gold(years: int = 5, tf_minutes: int = 60) -> pd.DataFrame:
    """
    Generate realistic Gold (XAUUSD) synthetic price data using a
    multi-regime Ornstein-Uhlenbeck process.

    Gold behaviour modelled:
      - Long-run mean slowly drifts upward (secular bull trend)
      - Price mean-reverts to the drifting mean over days/weeks
      - Volatility clusters (GARCH-like)
      - Occasional regime shifts (risk-off spikes)

    This is the correct model for testing zone-based mean-reversion strategies.
    On GBM (random walk) there is no mean-reversion alpha — OU adds genuine alpha.
    """
    bars_per_day = 24 * 60 // tf_minutes
    total_bars   = bars_per_day * 252 * years

    np.random.seed(42)

    # OU parameters calibrated to Gold 1H data
    theta   = 0.008      # mean-reversion speed per bar (higher = faster reversion)
    sigma   = 0.0025     # volatility per bar
    drift   = 0.00003    # long-run upward drift per bar (secular gold trend)

    # GARCH(1,1) parameters
    omega   = 0.00001
    alpha_g = 0.08
    beta_g  = 0.88

    prices  = [1800.0]
    mu_t    = [1800.0]   # slowly drifting long-run mean
    vol     = sigma

    for t in range(1, total_bars):
        # Update long-run mean (slow random walk with upward drift)
        mean_shock = np.random.randn() * sigma * 0.1
        mu_t.append(mu_t[-1] * (1 + drift + mean_shock))

        # GARCH(1,1) vol update
        last_ret = (prices[-1] - prices[-2]) / prices[-2] if t > 1 else 0
        vol = np.sqrt(omega + alpha_g * last_ret**2 + beta_g * vol**2)
        vol = np.clip(vol, sigma * 0.4, sigma * 5)

        # Ornstein-Uhlenbeck step: revert to drifting mean
        ou_step = theta * (mu_t[-1] - prices[-1]) + vol * prices[-1] * np.random.randn()
        new_price = prices[-1] + ou_step
        prices.append(max(new_price, 100.0))

    prices  = np.array(prices)
    mu_arr  = np.array(mu_t)

    # Build OHLC with realistic wicks
    intra_noise = np.abs(np.random.normal(0, vol * 0.5, total_bars))
    highs = prices * (1 + intra_noise)
    lows  = prices * (1 - intra_noise)
    opens = np.roll(prices, 1)
    opens[0] = prices[0]

    highs = np.maximum(highs, np.maximum(opens, prices))
    lows  = np.minimum(lows,  np.minimum(opens, prices))

    start = datetime.now() - timedelta(days=252 * years)
    idx   = pd.date_range(start, periods=total_bars, freq=f"{tf_minutes}min")

    volume = np.random.lognormal(mean=10.0, sigma=0.6, size=total_bars).astype(int)

    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": prices, "volume": volume},
        index=idx,
    )
    return df



# ─────────────────────────────────────────────────────────────────
# MT5 Data Loader
# ─────────────────────────────────────────────────────────────────
def load_mt5_data(symbol: str = "XAUUSDm", years: int = 5, timeframe_str: str = "1h") -> pd.DataFrame:
    try:
        import MetaTrader5 as mt5
        import config

        if not mt5.initialize(
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER,
        ):
            raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")

        tf_map = {
            "5m": mt5.TIMEFRAME_M5,
            "15m": mt5.TIMEFRAME_M15,
            "1h": mt5.TIMEFRAME_H1,
        }
        mt5_tf = tf_map.get(timeframe_str.lower(), mt5.TIMEFRAME_H1)

        from_date = datetime.now() - timedelta(days=365 * years)
        rates = mt5.copy_rates_from(symbol, mt5_tf, from_date, 999999)
        mt5.shutdown()

        if rates is None or len(rates) == 0:
            raise RuntimeError("No data returned from MT5")

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        df.rename(
            columns={
                "tick_volume": "volume",
                "open": "open", "high": "high",
                "low": "low", "close": "close",
            },
            inplace=True,
        )
        return df[["open", "high", "low", "close", "volume"]]

    except Exception as e:
        tf_mins = {"5m": 5, "15m": 15, "1h": 60}.get(timeframe_str.lower(), 60)
        logger.warning(f"Could not load MT5 data ({e}). Falling back to synthetic data ({timeframe_str}).")
        return generate_synthetic_gold(years, tf_minutes=tf_mins)


# ─────────────────────────────────────────────────────────────────
# Backtest Engine
# ─────────────────────────────────────────────────────────────────
class PDEBacktester:
    def __init__(
        self,
        initial_capital: float = 10_000.0,
        risk_pct: float = 1.0,          # % of equity risked per trade
        tp1_close_pct: float = 0.50,    # close 50% at TP1
        commission_pips: float = 2.0,   # round-trip spread in pips
        pip_value: float = 0.1,         # $ per pip per 0.01 lot (Gold)
        point_value: float = 0.01,      # 1 pip = 0.01 for Gold
    ):
        self.initial_capital  = initial_capital
        self.risk_pct         = risk_pct
        self.tp1_close_pct    = tp1_close_pct
        self.commission_pips  = commission_pips
        self.pip_value        = pip_value
        self.point_value      = point_value

    def _lot_size(self, equity: float, entry: float, stop: float) -> float:
        """Risk-based lot sizing (0.01 lot units)."""
        risk_amount = equity * self.risk_pct / 100
        sl_distance = abs(entry - stop)
        if sl_distance < 1e-8:
            return 0.01
        # For Gold: 1 pip = $1 for 0.01 lot (approximate)
        sl_pips = sl_distance / self.point_value
        lots = risk_amount / (sl_pips * self.pip_value)
        return max(0.01, round(lots, 2))

    def run(self, df_signals: pd.DataFrame) -> dict:
        """
        Run the backtest on a signals dataframe.
        Returns dict with trade_log (DataFrame) + metrics.
        """
        equity       = self.initial_capital
        peak_equity  = equity
        max_dd       = 0.0
        trades       = []
        open_trade   = None    # {signal, entry, sl, tp1, tp2, lots, bar_open}

        for i, (ts, row) in enumerate(df_signals.iterrows()):
            high_  = row["high"]
            low_   = row["low"]
            close_ = row["close"]

            # ── manage open trade ──────────────────────────────
            if open_trade:
                ot = open_trade
                hit_sl  = False
                hit_tp1 = False
                hit_tp2 = False

                if ot["signal"] == 1:   # LONG
                    if low_ <= ot["sl"]:
                        hit_sl = True
                    elif high_ >= ot["tp2"]:
                        hit_tp2 = True
                    elif high_ >= ot["tp1"] and not ot.get("tp1_hit"):
                        hit_tp1 = True

                else:                   # SHORT
                    if high_ >= ot["sl"]:
                        hit_sl = True
                    elif low_ <= ot["tp2"]:
                        hit_tp2 = True
                    elif low_ <= ot["tp1"] and not ot.get("tp1_hit"):
                        hit_tp1 = True

                # TP1 partial close — record in trade_log too
                if hit_tp1 and not hit_sl:
                    tp1_pnl_gross = (
                        (ot["tp1"] - ot["entry"]) * ot["signal"]
                        * ot["lots"] * self.tp1_close_pct
                        / self.point_value * self.pip_value
                    )
                    tp1_comm = self.commission_pips * self.pip_value * ot["lots"] * self.tp1_close_pct
                    tp1_net  = tp1_pnl_gross - tp1_comm
                    equity  += tp1_net
                    open_trade["tp1_hit"]    = True
                    open_trade["tp1_net"]    = tp1_net          # store for combined reporting
                    open_trade["lots"]      *= (1 - self.tp1_close_pct)

                elif hit_tp2:
                    tp_price = ot["tp2"]
                    pnl_tp2  = (
                        (tp_price - ot["entry"]) * ot["signal"]
                        * ot["lots"]
                        / self.point_value * self.pip_value
                    )
                    comm    = self.commission_pips * self.pip_value * ot["lots"]
                    net_tp2 = pnl_tp2 - comm
                    equity += net_tp2
                    # Combine TP1 + TP2 into a single full trade record
                    tp1_contribution = ot.get("tp1_net", 0.0)
                    full_net = tp1_contribution + net_tp2
                    trades.append({
                        "open_time":    ot["bar_open"],
                        "close_time":   ts,
                        "signal":       ot["signal"],
                        "entry":        ot["entry"],
                        "exit":         tp_price,
                        "sl":           ot["sl"],
                        "tp1":          ot["tp1"],
                        "tp2":          ot["tp2"],
                        "lots":         ot["original_lots"],
                        "tp1_net_pnl":  round(tp1_contribution, 2),
                        "tp2_net_pnl":  round(net_tp2, 2),
                        "net_pnl":      round(full_net, 2),
                        "result":       "TP2",
                        "equity":       round(equity, 2),
                    })
                    open_trade = None

                elif hit_sl:
                    remaining = ot["lots"]
                    pnl_sl = (
                        (ot["sl"] - ot["entry"]) * ot["signal"]
                        * remaining
                        / self.point_value * self.pip_value
                    )
                    comm       = self.commission_pips * self.pip_value * remaining
                    net_sl     = pnl_sl - comm
                    equity    += net_sl
                    result     = "SL_after_TP1" if ot.get("tp1_hit") else "SL"
                    tp1_contribution = ot.get("tp1_net", 0.0)
                    full_net   = tp1_contribution + net_sl
                    trades.append({
                        "open_time":    ot["bar_open"],
                        "close_time":   ts,
                        "signal":       ot["signal"],
                        "entry":        ot["entry"],
                        "exit":         ot["sl"],
                        "sl":           ot["sl"],
                        "tp1":          ot["tp1"],
                        "tp2":          ot["tp2"],
                        "lots":         ot["original_lots"],
                        "tp1_net_pnl":  round(tp1_contribution, 2),
                        "tp2_net_pnl":  round(net_sl, 2),
                        "net_pnl":      round(full_net, 2),
                        "result":       result,
                        "equity":       round(equity, 2),
                    })
                    open_trade = None

                # Update drawdown
                peak_equity = max(peak_equity, equity)
                dd = (peak_equity - equity) / peak_equity * 100
                max_dd = max(max_dd, dd)

            # ── new signal (only if no open trade) ─────────────
            if open_trade is None and row["signal"] != 0:
                lots = self._lot_size(equity, row["entry_price"], row["sl"])
                open_trade = {
                    "signal":        row["signal"],
                    "entry":         row["entry_price"],
                    "sl":            row["sl"],
                    "tp1":           row["tp1"],
                    "tp2":           row["tp2"],
                    "lots":          lots,
                    "original_lots": lots,
                    "tp1_hit":       False,
                    "bar_open":      ts,
                }

        # Close any remaining open trade at last bar
        if open_trade:
            ot = open_trade
            exit_price = df_signals.iloc[-1]["close"]
            tp1_contribution = ot.get("tp1_net", 0.0)
            pnl = (
                (exit_price - ot["entry"]) * ot["signal"]
                * ot["lots"]
                / self.point_value * self.pip_value
            )
            comm = self.commission_pips * self.pip_value * ot["lots"]
            net_final = pnl - comm
            equity += net_final
            trades.append({
                "open_time":    ot["bar_open"],
                "close_time":   df_signals.index[-1],
                "signal":       ot["signal"],
                "entry":        ot["entry"],
                "exit":         exit_price,
                "sl":           ot["sl"],
                "tp1":          ot["tp1"],
                "tp2":          ot["tp2"],
                "lots":         ot["original_lots"],
                "tp1_net_pnl":  round(tp1_contribution, 2),
                "tp2_net_pnl":  round(net_final, 2),
                "net_pnl":      round(tp1_contribution + net_final, 2),
                "result":       "OPEN_CLOSE",
                "equity":       round(equity, 2),
            })

        trade_log = pd.DataFrame(trades)
        metrics   = self._compute_metrics(trade_log, equity, max_dd)
        return {"trade_log": trade_log, "metrics": metrics, "final_equity": round(equity, 2)}

    # ── metrics ───────────────────────────────────────────────────
    def _compute_metrics(self, tl: pd.DataFrame, final_eq: float, max_dd: float) -> dict:
        if tl.empty:
            return {"error": "No trades generated"}

        wins       = tl[tl["net_pnl"] > 0]
        losses     = tl[tl["net_pnl"] <= 0]
        tp2_hits   = tl[tl["result"] == "TP2"]
        tp1_after  = tl[tl["result"] == "SL_after_TP1"]

        total      = len(tl)
        win_rate   = len(wins) / total * 100 if total else 0
        avg_win    = wins["net_pnl"].mean() if len(wins) else 0
        avg_loss   = losses["net_pnl"].mean() if len(losses) else 0
        gross_p    = wins["net_pnl"].sum()
        gross_l    = abs(losses["net_pnl"].sum())
        pf         = gross_p / gross_l if gross_l > 0 else float("inf")
        total_ret  = (final_eq - self.initial_capital) / self.initial_capital * 100

        # Sharpe (annualised, assuming 252 trading days, 1H bars → 252*24 bars/year)
        if not tl.empty and "net_pnl" in tl.columns:
            daily_pnl = tl.set_index("close_time")["net_pnl"].resample("D").sum().dropna()
            sharpe = (
                daily_pnl.mean() / daily_pnl.std() * np.sqrt(252)
                if daily_pnl.std() > 0 else 0
            )
        else:
            sharpe = 0

        return {
            "total_trades":      total,
            "wins":              len(wins),
            "losses":            len(losses),
            "tp2_full_hits":     len(tp2_hits),
            "sl_after_tp1":      len(tp1_after),
            "win_rate_pct":      round(win_rate, 1),
            "avg_win_usd":       round(avg_win, 2),
            "avg_loss_usd":      round(avg_loss, 2),
            "profit_factor":     round(pf, 2),
            "max_drawdown_pct":  round(max_dd, 2),
            "total_return_pct":  round(total_ret, 2),
            "final_equity_usd":  round(final_eq, 2),
            "initial_capital":   self.initial_capital,
            "sharpe_ratio":      round(sharpe, 2),
        }


# ─────────────────────────────────────────────────────────────────
# Report Printer
# ─────────────────────────────────────────────────────────────────
def print_report(result: dict, symbol: str, years: int):
    m  = result["metrics"]
    tl = result["trade_log"]

    SEP  = "=" * 62
    LINE = "-" * 62

    print("\n" + SEP)
    print(f"  PDE STRATEGY BACKTEST REPORT -- {symbol}  ({years} Years)")
    print(SEP)
    print(f"  Initial Capital     : ${m['initial_capital']:>10,.2f}")
    print(f"  Final Equity        : ${m['final_equity_usd']:>10,.2f}")
    print(f"  Total Return        : {m['total_return_pct']:>+9.1f}%")
    print(f"  Max Drawdown        : {m['max_drawdown_pct']:>9.1f}%")
    print(f"  Sharpe Ratio        : {m['sharpe_ratio']:>9.2f}")
    print(LINE)
    print(f"  Total Trades        : {m['total_trades']:>10}")
    print(f"  Net Wins / Losses   : {m['wins']:>4}  /  {m['losses']:<4}")
    print(f"  Win Rate (net P&L)  : {m['win_rate_pct']:>9.1f}%")
    print(f"  TP2 Full Wins       : {m['tp2_full_hits']:>10}")
    print(f"  SL after TP1 hit    : {m['sl_after_tp1']:>10}  (partial TP1 profit recovered)")
    print(f"  Pure SL (no TP1)    : {m.get('pure_sl',0):>10}")
    print(f"  Avg Win  (net USD)  : ${m['avg_win_usd']:>9.2f}")
    print(f"  Avg Loss (net USD)  : ${m['avg_loss_usd']:>9.2f}")
    print(f"  Profit Factor       : {m['profit_factor']:>9.2f}")
    print(SEP)

    if not tl.empty:
        tl["year"] = pd.to_datetime(tl["close_time"]).dt.year
        yearly = (
            tl.groupby("year")["net_pnl"]
            .agg(trades="count", net_pnl="sum", wins=lambda x: (x > 0).sum())
            .assign(win_rate=lambda d: (d["wins"] / d["trades"] * 100).round(1))
        )
        print("\n  Yearly Performance (net P&L including TP1 partial):")
        print("  " + LINE)
        print(f"  {'Year':<6} {'Trades':>7} {'Win%':>7} {'Net P&L':>12}")
        print("  " + LINE)
        for yr, row in yearly.iterrows():
            flag = " **" if row['net_pnl'] > 0 else ""
            print(
                f"  {yr:<6} {int(row['trades']):>7} "
                f"{row['win_rate']:>6.1f}% "
                f"${row['net_pnl']:>10,.2f}{flag}"
            )
        print(SEP + "\n")

    return m


# ─────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="PDE Strategy Backtest")
    parser.add_argument("--symbol",    default="XAUUSDm",    help="Symbol (default XAUUSDm)")
    parser.add_argument("--tf",        default="1h",         choices=["5m", "15m", "1h"], help="Timeframe (5m, 15m, 1h)")
    parser.add_argument("--years",     type=int, default=5,  help="Years of data (default 5)")
    parser.add_argument("--mt5",       action="store_true",  help="Use live MT5 data")
    parser.add_argument("--capital",   type=float, default=10000.0, help="Starting capital USD")
    parser.add_argument("--risk",      type=float, default=1.0,     help="Risk percent per trade")
    parser.add_argument("--export",    action="store_true",  help="Export trade log to CSV")
    args = parser.parse_args()

    tf_mins = {"5m": 5, "15m": 15, "1h": 60}.get(args.tf.lower(), 60)
    logger.info(f"Loading {'MT5' if args.mt5 else 'synthetic'} data for {args.symbol} [{args.tf}] ({args.years}Y)...")

    if args.mt5:
        df = load_mt5_data(args.symbol, args.years, args.tf)
    else:
        df = generate_synthetic_gold(args.years, tf_minutes=tf_mins)

    logger.info(f"Loaded {len(df):,} bars [{args.tf}]  [{df.index[0]} -> {df.index[-1]}]")

    logger.info(f"Generating PDE signals (v4 range-based) for timeframe {args.tf}...")
    pde = PDEStrategy(
        swing_lookback       = 50,
        atr_period           = 14,
        sl_atr_mult          = 0.5,
        min_atr_pct          = 0.0002,
        rsi_period           = 14,
        rsi_buy_threshold    = 42.0,
        rsi_sell_threshold   = 58.0,
        max_zone_touches     = 3,
        require_confirmation = True,
        volume_filter        = True,
        min_rr               = 1.5,
        cooldown_bars        = 12 if args.tf == "1h" else (24 if args.tf == "15m" else 48),
    )
    df_signals = pde.generate_signals(df)

    sig_count = (df_signals["signal"] != 0).sum()
    logger.info(f"Generated {sig_count} trade signals on {args.tf}")

    logger.info("Running backtest...")
    bt = PDEBacktester(
        initial_capital  = args.capital,
        risk_pct         = args.risk,
        tp1_close_pct    = 0.50,
        commission_pips  = 3.0,
    )
    result = bt.run(df_signals)

    metrics = print_report(result, f"{args.symbol} [{args.tf}]", args.years)

    if args.export and not result["trade_log"].empty:
        fname = f"pde_backtest_{args.symbol}_{args.tf}_{args.years}y.csv"
        result["trade_log"].to_csv(fname, index=False)
        logger.info(f"Trade log exported -> {fname}")

    return metrics


if __name__ == "__main__":
    main()
