# Scalping Bot Main Entry Point - Optimized for High-Frequency Trading

import time
import logging
import pandas as pd
import sqlite3
import os
import sys
import signal as sys_signal
from datetime import datetime

# Add error handling for optional imports
try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:
    logging.error("apscheduler not installed. Install with: pip install apscheduler")
    sys.exit(1)

from mt5_executor import MT5Executor
import config
from scalping_strategy import ScalpingStrategy
from logger import TradeLogger

# Initialize logging for scalping
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scalping_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('scalping_bot')


class TelegramNotifier:
    """Telegram notifications for scalping trades"""
    def __init__(self, token=config.TELEGRAM_TOKEN, chat_id=config.TELEGRAM_CHAT_ID):
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)
        
        if self.enabled:
            try:
                from telegram import Bot
                from telegram.constants import ParseMode
                self.bot = Bot(token=self.token)
                self.parse_mode = ParseMode.MARKDOWN
                logger.info("Telegram notifier initialized for scalping")
            except ImportError:
                logger.error("python-telegram-bot package not installed. Telegram notifications disabled.")
                self.enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize Telegram notifier: {str(e)}")
                self.enabled = False
    
    def send_message(self, message):
        """Send a message to the Telegram chat"""
        if not self.enabled:
            return
        
        try:
            self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=self.parse_mode
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {str(e)}")


class ScalpingBot:
    """
    High-Frequency Scalping Bot for Gold Trading
    Optimized for 1m and 5m timeframes with rapid execution
    """
    
    def __init__(self):
        print("Initializing High-Frequency Scalping Bot...")
        logger.info("Starting Scalping Bot initialization...")
        
        # Initialize components
        try:
            self.telegram = TelegramNotifier()
            logger.info("Telegram notifier initialized")
        except Exception as e:
            logger.error(f"Error initializing Telegram: {e}")
            
        try:
            self.logger = TradeLogger(self.telegram)
            logger.info("Trade logger initialized")
        except Exception as e:
            logger.error(f"Error initializing trade logger: {e}")
        
        # Scalping-specific settings
        self.scalping_symbols = ['BTCUSDm']  # Focus on Gold for scalping
        self.executors = {}
        self.strategies = {}
        
        # Initialize MT5 executor for scalping
        try:
            executor = MT5Executor(
                login=config.MT5_LOGIN,
                password=config.MT5_PASSWORD,
                server=config.MT5_SERVER,
                symbol='BTCUSDm',
            )
            
            if executor.connected:
                self.executors['BTCUSDm'] = executor
                
                # Create scalping strategy
                strategy = ScalpingStrategy(
                    executor,
                    risk_percent=0.5,  # Lower risk for scalping
                    tp_pips=8,         # Quick 8 pip targets
                    sl_pips=4          # Tight 4 pip stops
                )
                self.strategies['BTCUSDm'] = strategy
                
                logger.info("Scalping setup initialized for BTCUSDm")
            else:
                logger.error("Failed to connect MT5 for scalping")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Error initializing scalping components: {e}")
            sys.exit(1)
        
        # Scalping performance tracking
        self.scalp_trades_today = 0
        self.daily_pnl = 0.0
        self.max_daily_trades = 50  # Limit for scalping
        self.max_daily_loss = 2.0   # Tight daily loss limit for scalping
        
        # Initialize scheduler for high-frequency checks
        self.scheduler = BackgroundScheduler()
        self.running = False
        
        logger.info("Scalping Bot initialization completed successfully")

    def check_scalping_conditions(self):
        """Check if market conditions are suitable for scalping"""
        try:
            executor = self.executors['BTCUSDm']
            
            # Get current market data
            current_price = executor.get_current_price()
            if not current_price:
                return False
            
            # Check spread
            spread = (current_price['ask'] - current_price['bid']) * 10000  # Convert to pips
            if spread > 3.0:  # Maximum 3 pip spread for scalping
                logger.debug(f"Spread too high for scalping: {spread:.1f} pips")
                return False
            
            # Check if it's a good trading session
            current_hour = datetime.now().hour
            is_active_session = (
                (7 <= current_hour <= 10) or   # London session
                (13 <= current_hour <= 16) or  # NY session overlap
                (20 <= current_hour <= 24)     # Asian session start
            )
            
            if not is_active_session:
                logger.debug("Outside active trading sessions")
                return False
            
            # Check daily limits
            if self.scalp_trades_today >= self.max_daily_trades:
                logger.info("Daily trade limit reached for scalping")
                return False
            
            if self.daily_pnl <= -self.max_daily_loss:
                logger.warning("Daily loss limit reached - stopping scalping")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking scalping conditions: {e}")
            return False

    def check_scalping_signals(self):
        """Check for scalping signals with high frequency"""
        try:
            if not self.check_scalping_conditions():
                return
            
            executor = self.executors['BTCUSDm']
            strategy = self.strategies['BTCUSDm']
            
            # Get current trades
            current_trades = executor.update_trade_status_mt5()
            
            # Only look for signals if no active trade (scalping one at a time)
            if current_trades:
                logger.debug("Active trade exists - skipping signal check")
                return
            
            # Get 1-minute data for scalping signals
            df_1m = executor.fetch_historical_data_mt5('1m', 100)
            if df_1m is None:
                logger.error("Failed to fetch 1m data for scalping")
                return
            
            # Generate scalping signals
            df_1m = strategy.generate_scalping_signals(df_1m)
            
            # Check for new signals
            latest = df_1m.iloc[-1]
            if latest['signal'] != 0:
                # Validate signal values
                entry_price = latest['entry_price']
                stop_loss = latest['stop_loss']
                take_profit = latest['take_profit']
                
                if (pd.isna(entry_price) or pd.isna(stop_loss) or pd.isna(take_profit) or
                    entry_price <= 0 or stop_loss <= 0 or take_profit <= 0):
                    logger.error("Invalid scalping signal values - BLOCKED")
                    return
                
                # Calculate position size for scalping
                account_balance = executor.get_account_balance()
                if not account_balance:
                    logger.error("Failed to get account balance")
                    return
                
                position_size = strategy.calculate_scalping_position_size(
                    account_balance,
                    entry_price,
                    stop_loss
                )
                
                # Execute the scalping trade
                trade_id = executor.execute_trade(
                    latest['signal'],
                    entry_price,
                    stop_loss,
                    take_profit,
                    position_size,
                    latest['signal_type']
                )
                
                if trade_id:
                    self.scalp_trades_today += 1
                    signal_type = "BUY" if latest['signal'] > 0 else "SELL"
                    
                    logger.info(f"SCALP TRADE #{self.scalp_trades_today} - {signal_type} {latest['signal_type']}")
                    logger.info(f"Entry: {entry_price:.5f}, SL: {stop_loss:.5f}, TP: {take_profit:.5f}")
                    logger.info(f"Size: {position_size}, Confidence: {latest['scalp_confidence']:.1%}")
                    
                    # Send notification
                    if self.telegram.enabled:
                        self.telegram.send_message(
                            f"[SCALP TRADE #{self.scalp_trades_today}] {signal_type}\n"
                            f"Type: {latest['signal_type']}\n"
                            f"Entry: {entry_price:.5f}\n"
                            f"Stop Loss: {stop_loss:.5f}\n"
                            f"Take Profit: {take_profit:.5f}\n"
                            f"Size: {position_size}\n"
                            f"Target: {latest.get('tp_pips', 8)} pips\n"
                            f"Risk: {latest.get('sl_pips', 4)} pips"
                        )
                
        except Exception as e:
            logger.error(f"Error checking scalping signals: {e}")

    def monitor_scalping_trades(self):
        """Monitor scalping trades with aggressive trailing"""
        try:
            executor = self.executors['BTCUSDm']
            strategy = self.strategies['BTCUSDm']
            
            # Get current trades
            current_trades = executor.update_trade_status_mt5()
            
            if not current_trades:
                strategy.set_current_trade(None)
                return
            
            # Monitor the active trade
            trade_id, trade_info = next(iter(current_trades.items()))
            strategy.set_current_trade(trade_info)
            
            # Get current price
            current_price = executor.get_current_price()
            if not current_price:
                logger.error("Failed to get current price for monitoring")
                return
            
            # Get current market data
            df = executor.fetch_historical_data_mt5('1m', 50)
            if df is None:
                logger.error("Failed to fetch data for monitoring")
                return
            
            # Update scalping trade
            actions = strategy.update_scalping_trade(df, current_price)
            
            if actions:
                # Execute trailing stop updates
                if actions['stop_loss']:
                    if executor.modify_position(trade_id, stop_loss=actions['stop_loss']):
                        logger.info(f"Scalping trailing stop updated: {actions['stop_loss']:.5f}")
                
                # Execute early exit if needed
                if actions['close_trade']:
                    position_size = trade_info.get('volume', 0.01)
                    if executor.close_trade(trade_id, position_size, "Scalping Early Exit"):
                        logger.info("Scalping trade closed early due to reversal")
                        
                        # Calculate and log PnL
                        exit_price = current_price['bid'] if trade_info['side'] == 'buy' else current_price['ask']
                        entry_price = trade_info['entry_price']
                        
                        if trade_info['side'] == 'buy':
                            pnl_pips = (exit_price - entry_price) * 10000
                        else:
                            pnl_pips = (entry_price - exit_price) * 10000
                        
                        self.daily_pnl += pnl_pips * position_size * 10  # Rough USD calculation
                        
                        status = "PROFIT" if pnl_pips > 0 else "LOSS"
                        logger.info(f"Scalping trade result: {status} {abs(pnl_pips):.1f} pips")
                        
                        if self.telegram.enabled:
                            self.telegram.send_message(
                                f"[SCALP {status}] Early Exit\n"
                                f"Result: {pnl_pips:+.1f} pips\n"
                                f"Daily P&L: {self.daily_pnl:+.2f} USD\n"
                                f"Trades Today: {self.scalp_trades_today}"
                            )
                        
                        strategy.set_current_trade(None)
                
        except Exception as e:
            logger.error(f"Error monitoring scalping trades: {e}")

    def reset_daily_counters(self):
        """Reset daily counters at start of new trading day"""
        try:
            current_hour = datetime.now().hour
            
            # Reset at 00:00 GMT (start of new trading day)
            if current_hour == 0:
                if self.scalp_trades_today > 0:
                    logger.info(f"Daily reset - Trades: {self.scalp_trades_today}, P&L: {self.daily_pnl:+.2f}")
                    
                    if self.telegram.enabled:
                        self.telegram.send_message(
                            f"📊 DAILY SCALPING SUMMARY\n"
                            f"Trades: {self.scalp_trades_today}\n"
                            f"P&L: {self.daily_pnl:+.2f} USD\n"
                            f"Avg per trade: {self.daily_pnl/max(1,self.scalp_trades_today):+.2f} USD"
                        )
                
                self.scalp_trades_today = 0
                self.daily_pnl = 0.0
                logger.info("Daily counters reset for new trading day")
                
        except Exception as e:
            logger.error(f"Error resetting daily counters: {e}")

    def start(self):
        """Start the scalping bot"""
        try:
            logger.info("Starting High-Frequency Scalping Bot...")
            
            # Send startup notification
            if self.telegram.enabled:
                self.telegram.send_message(
                    "[SCALPING BOT STARTED]\n"
                    "Target: 8 pips profit\n"
                    "Risk: 4 pips stop\n"
                    "Timeframe: 1m\n"
                    "Max Daily Trades: 50"
                )
            
            # Schedule high-frequency tasks for scalping
            
            # Check signals every 5 seconds for scalping
            self.scheduler.add_job(
                self.check_scalping_signals, 
                'interval', 
                seconds=30, 
                name='scalping_signals'
            )
            
            # Monitor trades every 2 seconds for aggressive management
            self.scheduler.add_job(
                self.monitor_scalping_trades, 
                'interval', 
                seconds=30, 
                name='scalping_monitor'
            )
            
            # Reset daily counters
            self.scheduler.add_job(
                self.reset_daily_counters, 
                'interval', 
                seconds=3600,  # Check every hour
                name='daily_reset'
            )
            
            # Start scheduler
            self.scheduler.start()
            self.running = True
            
            logger.info("Scalping bot started successfully!")
            logger.info("Signal check: Every 5 seconds")
            logger.info("Trade monitor: Every 2 seconds")
            
            # Keep the main thread alive
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                self.stop()
                
        except Exception as e:
            logger.error(f"Error starting scalping bot: {str(e)}")
            self.stop()
    
    def stop(self):
        """Stop the scalping bot"""
        try:
            logger.info("Stopping Scalping Bot...")
            
            # Stop scheduler
            if self.scheduler.running:
                self.scheduler.shutdown()
            
            # Set running flag
            self.running = False
            
            # Send shutdown notification
            if self.telegram.enabled:
                self.telegram.send_message(
                    f"🛑 SCALPING BOT STOPPED\n"
                    f"Final Stats:\n"
                    f"Trades Today: {self.scalp_trades_today}\n"
                    f"P&L Today: {self.daily_pnl:+.2f} USD"
                )
            
            logger.info("Scalping bot stopped successfully.")
            
        except Exception as e:
            logger.error(f"Error stopping scalping bot: {str(e)}")


# Handle system signals
def signal_handler(sig, frame):
    logger.info(f"Received signal {sig}. Stopping scalping bot...")
    if bot:
        bot.stop()
    sys.exit(0)


# Register signal handlers
sys_signal.signal(sys_signal.SIGINT, signal_handler)
sys_signal.signal(sys_signal.SIGTERM, signal_handler)


# Main entry point
if __name__ == "__main__":
    # Create scalping bot instance
    bot = ScalpingBot()
    
    # Start the bot
    bot.start() 