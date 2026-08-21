# smt_ict_gold_bot_m1.py

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime, timezone
import pytz

# --- Import your custom modules ---
import config
from mt5_executor import MT5Executor

# --- Initialize logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gold_trading_bot_m1.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('smt_ict_gold_bot_m1')

class SMTICTGoldBotM1:
    def __init__(self):
        self.mt5_executor = MT5Executor(
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER
        )
        
        # --- STRATEGY PARAMETERS ---
        self.symbol = config.SYMBOL  # Gold symbol, e.g., 'XAUUSD'
        self.timeframe = mt5.TIMEFRAME_M1          # Lower Timeframe (LTF) for entry
        self.htf_timeframe = mt5.TIMEFRAME_M5     # Higher Timeframe (HTF) for bias

        self.risk_per_trade = 0.01
        self.min_rr_ratio = 1.5  # Lowered RR for more frequent scalps
        self.max_trades = 1
        
        # Kill Zones are even MORE important for M1 trading to avoid noise
        self.kill_zones = {
            'london': ('02:00', '05:00'),
            'ny_am': ('07:00', '10:00'),
        }
        self.ny_tz = pytz.timezone('America/New_York')

        # State variables for multi-timeframe analysis
        self.htf_bias = 'None'  # 'Bullish', 'Bearish', or 'None'
        self.htf_poi = None     # Higher timeframe Point of Interest

    def get_market_data(self, symbol, timeframe, bars):
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
            if rates is None or len(rates) < bars: return None
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df['atr'] = (df['high'] - df['low']).rolling(14).mean()
            return df
        except Exception as e:
            logger.error(f"Error getting data for {symbol}: {e}")
            return None

    def analyze_htf_context(self, htf_df):
        """Analyze M15 chart for bias and find a Point of Interest (POI)."""
        self.htf_bias = 'None'
        self.htf_poi = None

        # Find last major swing points
        htf_df['swing_high'] = htf_df['high'][(htf_df['high'] > htf_df['high'].shift(3)) & (htf_df['high'] > htf_df['high'].shift(-3))]
        htf_df['swing_low'] = htf_df['low'][(htf_df['low'] < htf_df['low'].shift(3)) & (htf_df['low'] < htf_df['low'].shift(-3))]
        last_highs = htf_df['swing_high'].dropna().tail(2)
        last_lows = htf_df['swing_low'].dropna().tail(2)

        if len(last_highs) < 2 or len(last_lows) < 2: return

        # Determine HTF bias
        if last_highs.iloc[-1] > last_highs.iloc[-2] and last_lows.iloc[-1] > last_lows.iloc[-2]:
            self.htf_bias = 'Bullish'
            # In a bullish trend, our POI is the last swing low, expecting a pullback
            self.htf_poi = {'type': 'bullish', 'price': last_lows.iloc[-1]}
        elif last_highs.iloc[-1] < last_highs.iloc[-2] and last_lows.iloc[-1] < last_lows.iloc[-2]:
            self.htf_bias = 'Bearish'
            # In a bearish trend, our POI is the last swing high
            self.htf_poi = {'type': 'bearish', 'price': last_highs.iloc[-1]}
        
        logger.info(f"HTF (M15) Analysis: Bias is {self.htf_bias}. POI at {self.htf_poi['price'] if self.htf_poi else 'None'}")

    def find_m1_entry_pattern(self, m1_df):
        """On the M1 chart, look for a Liquidity Sweep + Market Structure Shift."""
        # Look at the last 30 minutes of M1 data
        recent_data = m1_df.tail(30)
        
        # Bullish Entry Pattern (when HTF Bias is Bullish)
        if self.htf_bias == 'Bullish':
            recent_low = recent_data['low'].min()
            # 1. Liquidity Sweep: Has price recently dipped below a short-term low?
            if recent_data['low'].iloc[-2] < recent_low and recent_data['close'].iloc[-2] < recent_low:
                # 2. Market Structure Shift (MSS): After the sweep, did price aggressively break a recent high?
                recent_swing_high = recent_data['high'][(recent_data['high'] > recent_data['high'].shift(1)) & (recent_data['high'] > recent_data['high'].shift(-1))].max()
                if pd.notna(recent_swing_high) and m1_df['close'].iloc[-1] > recent_swing_high:
                    logger.info(f"BULLISH M1 PATTERN DETECTED: Liquidity Sweep at {recent_low}, MSS at {recent_swing_high}")
                    return {'type': 'buy', 'sl': recent_low}

        # Bearish Entry Pattern (when HTF Bias is Bearish)
        elif self.htf_bias == 'Bearish':
            recent_high = recent_data['high'].max()
            # 1. Liquidity Sweep: Has price recently spiked above a short-term high?
            if recent_data['high'].iloc[-2] > recent_high and recent_data['close'].iloc[-2] > recent_high:
                # 2. Market Structure Shift (MSS): After the sweep, did price aggressively break a recent low?
                recent_swing_low = recent_data['low'][(recent_data['low'] < recent_data['low'].shift(1)) & (recent_data['low'] < recent_data['low'].shift(-1))].min()
                if pd.notna(recent_swing_low) and m1_df['close'].iloc[-1] < recent_swing_low:
                    logger.info(f"BEARISH M1 PATTERN DETECTED: Liquidity Sweep at {recent_high}, MSS at {recent_swing_low}")
                    return {'type': 'sell', 'sl': recent_high}
        
        return None

    def is_kill_zone(self):
        now_utc = datetime.now(timezone.utc)
        now_ny = now_utc.astimezone(self.ny_tz)
        current_time_str = now_ny.strftime('%H:%M')
        for zone, (start, end) in self.kill_zones.items():
            if start <= current_time_str <= end:
                return False
        return False

    def calculate_position_size(self, stop_loss_pips):
        account_balance = self.mt5_executor.get_account_balance()
        if not account_balance or stop_loss_pips <= 0: return 0.01

        risk_amount = account_balance * self.risk_per_trade
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info: return 0.01
        
        pip_value = symbol_info.trade_tick_value / symbol_info.trade_tick_size * (symbol_info.point * 10)
        if pip_value == 0: return 0.01

        position_size = risk_amount / (stop_loss_pips * pip_value)
        lot_step = symbol_info.volume_step
        position_size = round(position_size / lot_step) * lot_step
        return max(symbol_info.volume_min, min(position_size, symbol_info.volume_max))

    def generate_trade_decision(self):
        if len(self.mt5_executor.get_open_positions()) >= self.max_trades:
            return
        

        # 1. Higher Timeframe (M15) Analysis for context
        htf_df = self.get_market_data(self.symbol, self.htf_timeframe, 200)
        if htf_df is None: return
        self.analyze_htf_context(htf_df)

        if not self.htf_poi:
            logger.info("No clear HTF (M15) bias or POI found. Waiting.")
            return

        # 2. Check if price is near our HTF Point of Interest
        current_price = self.mt5_executor.get_current_price()
        if not current_price: return

        # Check if price is within a reasonable distance (e.g., 2 * M15 ATR) of our POI
        atr_threshold = htf_df['atr'].iloc[-1] * 2.0
        logger.info(f"atr_threshold {atr_threshold}")
        logger.info(f"current_price {current_price}")
        logger.info(f"self.htf_poi['price'] {self.htf_poi['price']}")
        if abs(current_price['bid'] - self.htf_poi['price']) > atr_threshold:
            logger.info(f"Price {current_price['bid']} is too far from HTF POI at {self.htf_poi['price']}. Waiting.")
            return

        # 3. Lower Timeframe (M1) Analysis for entry pattern
        m1_df = self.get_market_data(self.symbol, self.timeframe, 100)
        if m1_df is None: return
        
        entry_signal = self.find_m1_entry_pattern(m1_df)

        if entry_signal:
            # 4. Execute Trade
            if entry_signal['type'] == 'buy' and self.htf_bias == 'Bullish':
                stop_loss_price = entry_signal['sl'] - (m1_df['atr'].iloc[-1] * 2) # Add small buffer
                sl_pips = (current_price['ask'] - stop_loss_price) / (m1_df.point.iloc[-1] * 10)
                tp_price = current_price['ask'] + (sl_pips * self.min_rr_ratio * (m1_df.point.iloc[-1] * 10))
                position_size = self.calculate_position_size(sl_pips)
                
                self.mt5_executor.execute_trade(1, stop_loss_price, tp_price, position_size, "M1_MSS_BUY")

            elif entry_signal['type'] == 'sell' and self.htf_bias == 'Bearish':
                stop_loss_price = entry_signal['sl'] + (m1_df['atr'].iloc[-1] * 2) # Add small buffer
                sl_pips = (stop_loss_price - current_price['bid']) / (m1_df.point.iloc[-1] * 10)
                tp_price = current_price['bid'] - (sl_pips * self.min_rr_ratio * (m1_df.point.iloc[-1] * 10))
                position_size = self.calculate_position_size(sl_pips)

                self.mt5_executor.execute_trade(-1, stop_loss_price, tp_price, position_size, "M1_MSS_SELL")

    def run(self):
        logger.info("Starting M1 SMT/ICT Gold Trading Bot...")
        if not self.mt5_executor.connected:
            logger.error("Failed to connect to MT5. Bot cannot start.")
            return

        while True:
            try:
                self.generate_trade_decision()
                # For M1, we check every minute
                time.sleep(60)
            except KeyboardInterrupt:
                logger.info("Bot stopped by user.")
                break
            except Exception as e:
                logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
                time.sleep(60)
        
        self.mt5_executor.shutdown()

if __name__ == "__main__":
    bot = SMTICTGoldBotM1()
    bot.run()