# smt_ict_gold_bot.py

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime,timezone
import pytz

# --- Import your custom modules ---
import config
from mt5_executor import MT5Executor

# --- Initialize logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gold_trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('smt_ict_gold_bot')


class SMTICTGoldBot:
    def __init__(self):
        """Initialize the trading bot with SMT and ICT strategies"""
        self.mt5_executor = MT5Executor(
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER
        )
        
        # Trading parameters
        self.symbol = config.SYMBOL
        self.correlated_symbol = config.SYMBOL
        self.timeframe = mt5.TIMEFRAME_M15
        self.lookback_periods = 200
        
        # Risk management
        self.risk_per_trade = 0.01  # 1% of account balance
        self.max_trades = 1         # Max concurrent trades
        self.min_rr_ratio = 2.0     # Minimum 2:1 risk-reward ratio
        
        # ICT Kill Zones (New York Time)
        self.kill_zones = {
            'london': ('02:00', '05:00'),
            'ny_am': ('07:00', '10:00'),
        }
        # New, explicit line
        self.ny_tz = pytz.timezone('America/New_York')

        self.market_structure = {}
        self.recent_fvg = None

    def get_market_data(self, symbol, timeframe, bars):
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
            if rates is None or len(rates) == 0:
                logger.warning(f"No market data for {symbol} on {timeframe}")
                return None
            
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            df['atr'] = (df['high'] - df['low']).rolling(14).mean()
            return df
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None

    def analyze_market_structure(self, df):
        """Identify Market Structure by finding the last two swing highs and lows"""
        df['swing_high'] = df['high'][(df['high'] > df['high'].shift(5)) & (df['high'] > df['high'].shift(-5))]
        df['swing_low'] = df['low'][(df['low'] < df['low'].shift(5)) & (df['low'] < df['low'].shift(-5))]
        
        last_highs = df['swing_high'].dropna().tail(2)
        last_lows = df['swing_low'].dropna().tail(2)

        if len(last_highs) < 2 or len(last_lows) < 2:
            return # Not enough data

        trend = 'undetermined'
        if last_highs.iloc[-1] > last_highs.iloc[-2] and last_lows.iloc[-1] > last_lows.iloc[-2]:
            trend = 'bullish'
        elif last_highs.iloc[-1] < last_highs.iloc[-2] and last_lows.iloc[-1] < last_lows.iloc[-2]:
            trend = 'bearish'
        
        self.market_structure = {'trend': trend, 'high': last_highs.iloc[-1], 'low': last_lows.iloc[-1]}

    def find_recent_fvg(self, df):
        """Find the most recent Fair Value Gap"""
        self.recent_fvg = None
        for i in range(len(df) - 2, 2, -1):
            # Bullish FVG
            if df['low'].iloc[i] > df['high'].iloc[i-2]:
                self.recent_fvg = {'type': 'bullish', 'low': df['high'].iloc[i-2], 'high': df['low'].iloc[i]}
                break
            # Bearish FVG
            if df['high'].iloc[i] < df['low'].iloc[i-2]:
                self.recent_fvg = {'type': 'bearish', 'low': df['high'].iloc[i], 'high': df['low'].iloc[i-2]}
                break

    def check_smt_divergence(self, gold_df, dxy_df):
        """Check for SMT divergence between Gold and DXY"""
        gold_lows = gold_df['low'].rolling(10).min()
        dxy_highs = dxy_df['high'].rolling(10).max()
        
        gold_highs = gold_df['high'].rolling(10).max()
        dxy_lows = dxy_df['low'].rolling(10).min()

        # Bullish SMT: Gold makes a lower low, but DXY fails to make a higher high
        if gold_df['low'].iloc[-1] < gold_lows.iloc[-2] and dxy_df['high'].iloc[-1] < dxy_highs.iloc[-2]:
            return 'bullish_smt'
            
        # Bearish SMT: Gold makes a higher high, but DXY fails to make a lower low
        if gold_df['high'].iloc[-1] > gold_highs.iloc[-2] and dxy_df['low'].iloc[-1] > dxy_lows.iloc[-2]:
            return 'bearish_smt'
        
        return None

    def is_kill_zone(self):
        """Check if the current time is within an ICT kill zone"""
        
        # Use the standard library's timezone.utc for a modern, aware object
        now_utc = datetime.now(timezone.utc)
        
        # The rest of the function is correct and stays the same
        now_ny = now_utc.astimezone(self.ny_tz)
        current_time_str = now_ny.strftime('%H:%M')
        logger.info(f"current_time_str {current_time_str}")
        for zone, (start, end) in self.kill_zones.items():
            if start <= current_time_str <= end:
                return True, zone
        return True, None

    def calculate_position_size(self, stop_loss_pips):
        """Calculate position size based on risk percentage"""
        account_balance = self.mt5_executor.get_account_balance()
        if not account_balance: return 0.01

        risk_amount = account_balance * self.risk_per_trade
        
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info: return 0.01
        
        pip_value = symbol_info.trade_tick_value * (1 / symbol_info.trade_tick_size) * (symbol_info.point * 10)
        if pip_value == 0: return 0.01

        position_size = risk_amount / (stop_loss_pips * pip_value)
        
        # Normalize to valid lot step
        lot_step = symbol_info.volume_step
        position_size = round(position_size / lot_step) * lot_step
        
        return max(symbol_info.volume_min, min(position_size, symbol_info.volume_max))

    def generate_trade_decision(self):
        """The core logic to decide whether to enter a trade."""
        # 1. Pre-trade checks
        open_positions = self.mt5_executor.get_open_positions()
        if len(open_positions) >= self.max_trades:
            logger.info("Max trades limit reached. No new trades will be opened.")
            return

        in_kill_zone, zone_name = self.is_kill_zone()
        if not in_kill_zone:
            logger.info("Not in a kill zone. Waiting...")
            return

        # 2. Data Collection
        gold_df = self.get_market_data(self.symbol, self.timeframe, self.lookback_periods)
        dxy_df = self.get_market_data(self.correlated_symbol, self.timeframe, self.lookback_periods)
        logger.info(f"Gold Data: {gold_df}")
        logger.info(f"DXY Data: {dxy_df}")
        if gold_df is None or dxy_df is None:
            logger.warning("Could not fetch market data. Skipping cycle.")
            return

        # 3. Market Analysis
        self.analyze_market_structure(gold_df)
        self.find_recent_fvg(gold_df)
        smt_signal = self.check_smt_divergence(gold_df, dxy_df)
        current_price = self.mt5_executor.get_current_price()
        logger.info(f"Current Price: {current_price}")
        logger.info(f"smt_signal {smt_signal}")
        if not current_price: return

        logger.info(f"Analysis complete. Trend: {self.market_structure.get('trend')}, SMT: {smt_signal}, FVG: {self.recent_fvg['type'] if self.recent_fvg else 'None'}")
        
        # 4. Trade Execution Logic
        # --- BUY LOGIC ---
        if (self.market_structure.get('trend') == 'bullish' and 
            smt_signal == 'bullish_smt' and
            self.recent_fvg and self.recent_fvg['type'] == 'bullish' and
            self.recent_fvg['low'] < current_price['ask'] < self.recent_fvg['high']):
            
            signal_type = "BULLISH_SMT_FVG"
            stop_loss_price = self.market_structure['low'] - (gold_df['atr'].iloc[-1] * 0.5)
            sl_pips = (current_price['ask'] - stop_loss_price) / (gold_df.point.iloc[-1] * 10)
            take_profit_price = current_price['ask'] + (sl_pips * self.min_rr_ratio * (gold_df.point.iloc[-1] * 10))
            
            position_size = self.calculate_position_size(sl_pips)
            logger.info(f"BUY SIGNAL DETECTED: {signal_type}. Size: {position_size}, SL: {stop_loss_price}, TP: {take_profit_price}")
            
            self.mt5_executor.execute_trade(signal=1, stop_loss=stop_loss_price, take_profit=take_profit_price, position_size=position_size, signal_type=signal_type)

        # --- SELL LOGIC ---
        elif (self.market_structure.get('trend') == 'bearish' and 
              smt_signal == 'bearish_smt' and
              self.recent_fvg and self.recent_fvg['type'] == 'bearish' and
              self.recent_fvg['low'] < current_price['bid'] < self.recent_fvg['high']):
            
            signal_type = "BEARISH_SMT_FVG"
            stop_loss_price = self.market_structure['high'] + (gold_df['atr'].iloc[-1] * 0.5)
            sl_pips = (stop_loss_price - current_price['bid']) / (gold_df.point.iloc[-1] * 10)
            take_profit_price = current_price['bid'] - (sl_pips * self.min_rr_ratio * (gold_df.point.iloc[-1] * 10))

            position_size = self.calculate_position_size(sl_pips)
            logger.info(f"SELL SIGNAL DETECTED: {signal_type}. Size: {position_size}, SL: {stop_loss_price}, TP: {take_profit_price}")

            self.mt5_executor.execute_trade(signal=-1, stop_loss=stop_loss_price, take_profit=take_profit_price, position_size=position_size, signal_type=signal_type)

    def run(self):
        """The main continuous loop for the bot."""
        logger.info("Starting SMT/ICT Gold Trading Bot...")
        if not self.mt5_executor.connected:
            logger.error("Failed to connect to MT5. Bot cannot start.")
            return

        while True:
            try:
                self.generate_trade_decision()
                logger.info("Cycle complete. Waiting for the next 15-minute candle...")
                time.sleep(900)  # Sleep for 15 minutes
            except KeyboardInterrupt:
                logger.info("Bot stopped by user.")
                break
            except Exception as e:
                logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
                time.sleep(60) # Wait a minute before retrying
        
        self.mt5_executor.shutdown()

if __name__ == "__main__":
    bot = SMTICTGoldBot()
    bot.run()