# Main entry point for the Gold Trading Bot

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
# Import custom modules
import config
from indicators import SMCIndicators
from strategy import SMCStrategy
from trade_quality_improvement import TradeQualityFilter, EnhancedSignalGenerator

# from webhook_listener import WebhookListener
from logger import TradeLogger

# Initialize logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('gold_trading_bot')


class TelegramNotifier:
    """
    Class to handle Telegram notifications with improved error handling
    """
    def __init__(self, token=config.TELEGRAM_TOKEN, chat_id=config.TELEGRAM_CHAT_ID):
        self.token = token
        self.chat_id = chat_id
        self.enabled = False
        self.bot = None
        self.parse_mode = None
        
        # Only try to initialize if both token and chat_id are provided
        if not (token and chat_id):
            logger.info("Telegram credentials not provided - notifications disabled")
            return
            
        try:
            # Try to import telegram bot
            from telegram import Bot
            from telegram.constants import ParseMode
            
            self.bot = Bot(token=self.token)
            self.parse_mode = ParseMode.MARKDOWN
            
            # Test the connection
            bot_info = self.bot.get_me()
            if bot_info:
                self.enabled = True
                logger.info(f"Telegram notifier initialized successfully - Bot: {bot_info.username}")
            else:
                logger.warning("Telegram bot authentication failed")
                
        except ImportError:
            logger.warning("python-telegram-bot package not installed. Install with: pip install python-telegram-bot")
            logger.info("Telegram notifications disabled - bot will continue without notifications")
        except Exception as e:
            logger.warning(f"Failed to initialize Telegram notifier: {str(e)}")
            logger.info("Telegram notifications disabled - bot will continue without notifications")
    
    def send_message(self, message):
        """
        Send a message to the Telegram chat with improved error handling
        
        Args:
            message: Message to send
        """
        if not self.enabled or not self.bot:
            return False
        
        try:
            result = self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=self.parse_mode
            )
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {str(e)}")
            return False

class DatabaseManager:
    """
    Class to handle database operations using thread-local connections.
    Each method will open and close its own connection.
    """
    def __init__(self, db_path=config.DB_PATH):
        self.db_path = db_path
        self.initialize_db() # Call to ensure table creation

    def _get_connection(self):
        """Helper to get a new SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row # Allows accessing columns by name
        return conn

    def initialize_db(self):
        """
        Initialize the database and create tables if they don't exist.
        This method can be called safely from any thread, as it gets its own connection.
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Create trades table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    symbol TEXT,
                    side TEXT,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    position_size REAL,
                    signal_type TEXT,
                    entry_time TEXT,
                    exit_time TEXT,
                    exit_price REAL,
                    pnl REAL,
                    status TEXT
                )
            ''')

            # Create signals table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    signal INTEGER,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    signal_type TEXT,
                    timestamp TEXT,
                    processed INTEGER DEFAULT 0
                )
            ''')

            conn.commit()
            logger.info("Database initialized (tables ensured).")

        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
        finally:
            if conn:
                conn.close()

    def log_trade(self, trade_data):
        """Log a trade to the database."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trades (
                    id, symbol, side, entry_price, stop_loss, take_profit,
                    position_size, signal_type, entry_time, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_data['id'],
                trade_data['symbol'],
                trade_data['side'],
                trade_data['entry_price'],
                trade_data['stop_loss'],
                trade_data['take_profit'],
                trade_data['position_size'],
                trade_data['signal_type'],
                trade_data['entry_time'],
                'open'
            ))
            conn.commit()
            logger.info(f"Trade {trade_data['id']} logged to DB.")
        except Exception as e:
            logger.error(f"Failed to log trade: {str(e)}")
        finally:
            if conn:
                conn.close()

    def update_trade(self, trade_id, exit_price, exit_time, pnl):
        """Update a trade with exit information."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE trades
                SET exit_price = ?, exit_time = ?, pnl = ?, status = ?
                WHERE id = ?
            ''', (exit_price, exit_time, pnl, 'closed', trade_id))
            conn.commit()
            logger.info(f"Trade {trade_id} updated in DB.")
        except Exception as e:
            logger.error(f"Failed to update trade: {str(e)}")
        finally:
            if conn:
                conn.close()

    def log_signal(self, signal_data):
        """Log a signal to the database."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO signals (
                    symbol, signal, entry_price, stop_loss, take_profit,
                    signal_type, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal_data['symbol'],
                signal_data['signal'],
                signal_data['entry_price'],
                signal_data['stop_loss'],
                signal_data['take_profit'],
                signal_data['signal_type'],
                signal_data['timestamp']
            ))
            conn.commit()
            logger.info("Signal logged to DB.")
        except Exception as e:
            logger.error(f"Failed to log signal: {str(e)}")
        finally:
            if conn:
                conn.close()

    def get_unprocessed_signals(self):
        """Get all unprocessed signals."""
        conn = None
        signals = []
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, symbol, signal, entry_price, stop_loss, take_profit,
                       signal_type, timestamp
                FROM signals
                WHERE processed = 0
            ''')
            for row in cursor.fetchall():
                signals.append({
                    'id': row['id'],
                    'symbol': row['symbol'],
                    'signal': row['signal'],
                    'entry_price': row['entry_price'],
                    'stop_loss': row['stop_loss'],
                    'take_profit': row['take_profit'],
                    'signal_type': row['signal_type'],
                    'timestamp': row['timestamp']
                })
            logger.debug(f"Fetched {len(signals)} unprocessed signals.")
            return signals
        except Exception as e:
            logger.error(f"Failed to get unprocessed signals: {str(e)}")
            return []
        finally:
            if conn:
                conn.close()

    def mark_signal_processed(self, signal_id):
        """Mark a signal as processed."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE signals
                SET processed = 1
                WHERE id = ?
            ''', (signal_id,))
            conn.commit()
            logger.info(f"Signal {signal_id} marked as processed.")
        except Exception as e:
            logger.error(f"Failed to mark signal as processed: {str(e)}")
        finally:
            if conn:
                conn.close()

    def close(self):
        """
        This method is now largely vestigial as connections are closed per-method.
        It's kept for API consistency if external code calls it.
        """
        logger.info("DatabaseManager close called. Connections are managed per-method.")


class GoldTradingBot:
    """
    Enhanced Multi-Symbol Trading Bot with AI-enhanced trading and advanced risk management
    """
    def __init__(self):
        # Initialize components
        print("Initializing Enhanced Multi-Symbol Trading Bot...")
        logger.info("Initializing Enhanced Multi-Symbol Trading Bot components...")
        
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
            
        try:
            self.db = DatabaseManager()
            logger.info("Database manager initialized")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            
        # Multi-symbol support
        self.executors = {}
        self.strategies = {}
        self.active_symbols = []
        
        # Initialize quality filtering system
        self.quality_filter = TradeQualityFilter()
        self.enhanced_signal_generator = EnhancedSignalGenerator(self.quality_filter)
        
        # Initialize executors and strategies for each enabled symbol
        for symbol, symbol_config in config.SYMBOLS.items():
            if symbol_config.get('enabled', False):
                try:
                    # Create executor for this symbol
                    executor = MT5Executor(
                        login=config.MT5_LOGIN,
                        password=config.MT5_PASSWORD,
                        server=config.MT5_SERVER,
                        symbol=symbol,
                    )
                    
                    if executor.connected:
                        self.executors[symbol] = executor
                        
                        # Create strategy for this symbol
                        strategy = SMCStrategy(
                            executor,
                            risk_percent=symbol_config.get('risk_percent', 1.0),
                            tp_ratio=symbol_config.get('tp_ratio', 2.0)
                        )
                        self.strategies[symbol] = strategy
                        self.active_symbols.append(symbol)
                        
                        logger.info(f"Initialized trading for {symbol}")
                    else:
                        logger.error(f"Failed to connect MT5 for {symbol}")
                        
                except Exception as e:
                    logger.error(f"Error initializing {symbol}: {e}")
        
        # Fallback to single symbol if no multi-symbol setup
        if not self.executors:
            logger.warning("No symbols initialized, falling back to single symbol mode")
            try:
                self.trade_executor = MT5Executor(
                    login=config.MT5_LOGIN,
                    password=config.MT5_PASSWORD,
                    server=config.MT5_SERVER,
                    symbol=config.SYMBOL,
                )
                logger.info("Single symbol MT5 executor initialized")
            except Exception as e:
                logger.error(f"Error initializing MT5 executor: {e}")
                logger.warning("Bot will return in demo mode without MT5 connection")
                self.trade_executor = None
                
            try:
                self.strategy = SMCStrategy(getattr(self, 'trade_executor', None))
                logger.info("Single symbol SMC strategy initialized")
            except Exception as e:
                logger.error(f"Error initializing strategy: {e}")
                self.strategy = None
        
        # Risk management
        self.daily_pnl = 0.0
        self.max_daily_loss = config.RISK_MANAGEMENT.get('daily_loss_limit', 5.0)
        self.correlation_matrix = {}
        self.last_correlation_update = 0
        
        # Initialize scheduler
        self.scheduler = BackgroundScheduler()
        self.running = False
        logger.info(f"All components initialized successfully. Active symbols: {self.active_symbols}")

    def update_correlations(self):
        """
        Update correlation matrix for all active symbols
        """
        try:
            if len(self.active_symbols) < 2:
                return
            
            # Use first executor to calculate correlations
            if self.executors:
                primary_executor = next(iter(self.executors.values()))
                correlations = primary_executor.calculate_correlations()
                self.correlation_matrix = correlations
                logger.info(f"Updated correlations for {len(correlations)} symbol pairs")
                
        except Exception as e:
            logger.error(f"Error updating correlations: {str(e)}")

    def check_global_risk_limits(self):
        """
        Check global risk limits across all symbols
        """
        try:
            total_risk = 0.0
            open_positions = 0
            
            for symbol, executor in self.executors.items():
                if not executor.check_risk_limits():
                    logger.warning(f"Risk limit exceeded for {symbol}")
                    return False
                
                # Count open positions
                positions = executor.get_open_positions()
                if positions:
                    open_positions += len(positions)
                    # Add to total risk calculation
                    for pos in positions:
                        volume = abs(pos.get('volume', 0))
                        price = pos.get('price_open', 0)
                        total_risk += volume * price * 0.01  # Simplified risk calculation
            
            # Check maximum total risk
            if total_risk > config.RISK_MANAGEMENT.get('max_total_risk', 3.0):
                logger.warning(f"Global risk limit exceeded: {total_risk:.2f}%")
                return False
            
            # Check maximum number of positions
            max_positions = sum(config.SYMBOLS[s].get('max_trades', 1) for s in self.active_symbols)
            if open_positions >= max_positions:
                logger.info(f"Maximum positions reached: {open_positions}/{max_positions}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking global risk limits: {str(e)}")
            return True  # Allow trading if check fails

    def _log_trade_result(self, trade_info, exit_price, market_data, symbol):
        """Log trade result and update AI model for specific symbol"""
        entry_price = trade_info['entry_price']
        profit = exit_price - entry_price if trade_info['side'] == 'buy' else entry_price - exit_price
        profitable = profit > 0
        
        # Prepare trade result for AI update
        trade_result = {
            'market_data': market_data,
            'profitable': profitable,
            'profit': profit,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'side': trade_info['side'],
            'symbol': symbol
        }
        
        # Update AI model for this symbol
        strategy = self.strategies.get(symbol)
        if strategy and strategy.ai_analyzer:
            strategy.ai_analyzer.update_model(trade_result)
        
        # Log trade result
        logger.info(f"{symbol} trade completed - Profit: {profit:.2f}, Success: {profitable}")
        
        # Send notification
        if self.telegram.enabled:
            status = "PROFIT" if profitable else "LOSS"
            self.telegram.send_message(
                f"{status} - {symbol} Trade Closed\n"
                f"Result: {'Profit' if profitable else 'Loss'}: {abs(profit):.2f}\n"
                f"Entry: {entry_price:.2f}\n"
                f"Exit: {exit_price:.2f}"
            )

    def update_open_trades(self):
        """
        Enhanced trade monitoring for all symbols with advanced trailing
        """
        try:
            # Multi-symbol mode
            if self.executors and self.active_symbols:
                # Check global risk limits first
                if not self.check_global_risk_limits():
                    logger.warning("Global risk limits exceeded - monitoring only")
                
                for symbol in self.active_symbols:
                    executor = self.executors.get(symbol)
                    strategy = self.strategies.get(symbol)
                    
                    if not executor or not strategy:
                        logger.warning(f"Skipping {symbol} - missing executor or strategy")
                        return
                    
                    try:
                        self._update_symbol_trades(symbol, executor, strategy)
                    except Exception as e:
                        logger.error(f"Error updating trades for {symbol}: {str(e)}")
            else:
                # Single symbol fallback mode
                logger.info("Using single symbol fallback mode")
                self._update_single_symbol_trades()
                    
        except Exception as e:
            logger.error(f"Error in update_open_trades: {str(e)}")
    
    def _update_symbol_trades(self, symbol, executor, strategy):
        """
        Update trades for a specific symbol
        """
        try:
            # Get current price and market data
            current_price = executor.get_current_price()
            if not current_price:
                logger.error(f"Failed to get current price for {symbol}")
                return
            
            # Get market data for analysis
            df = executor.fetch_historical_data_mt5_symbol(symbol, '15m', 100)
            if df is None:
                logger.error(f"Failed to fetch historical data for {symbol}")
                return
            
            # Analyze market data
            df = strategy.analyze_market(df)
            
            # Update trade status
            trades = executor.update_trade_status_mt5()
            
            if trades:
                trade_id, trade_info = next(iter(trades.items()))
                trade_info['symbol'] = symbol  # Add symbol info
                strategy.set_current_trade(trade_info)
                
                # Get current profit status
                price = current_price['bid'] if trade_info['side'] == 'buy' else current_price['ask']
                profit = price - trade_info['entry_price'] if trade_info['side'] == 'buy' else trade_info['entry_price'] - price
                
                # Calculate profit in pips for better display
                if 'USD' in symbol and symbol.endswith('m'):
                    # For forex pairs, convert to pips (0.0001)
                    profit_pips = profit * 10000
                    profit_display = f"{profit:.5f} ({profit_pips:+.1f} pips)"
                elif 'XAU' in symbol or 'GOLD' in symbol.upper():
                    # For gold, convert to cents
                    profit_cents = profit * 100
                    profit_display = f"{profit:.2f} (${profit_cents:+.2f})"
                elif 'BTC' in symbol:
                    # For BTC, show in USD
                    profit_display = f"${profit:+.2f}"
                else:
                    profit_display = f"{profit:+.5f}"
                
                # Get MCP AI validation of current market conditions & spread risk
                validation = strategy.ai_analyzer.mcp_validate_trade(df, 1 if trade_info['side'] == 'buy' else -1, symbol=symbol)
                market_conditions = validation.get('market_conditions', {})
                
                # Log current trade status
                logger.info(f"{symbol} - Monitoring active trade - Side: {trade_info['side']}, "
                          f"Entry: {trade_info['entry_price']}, Current: {price}, "
                          f"Current SL: {trade_info['stop_loss']}, "
                          f"Profit: {profit_display}")
                
                # Check if we should exit based on market conditions (Exempt PDE strategy to let it reach structural zones)
                is_pde = (
                    getattr(config, 'STRATEGY_MODE', '').lower() == 'pde' or
                    'pde' in str(trade_info.get('comment', '')).lower() or
                    'pde' in str(trade_info.get('signal_type', '')).lower() or
                    getattr(strategy, 'is_pde', False) or
                    'pde' in str(type(strategy)).lower()
                )
                should_exit = False
                if not is_pde:
                    should_exit = (
                        strategy.should_exit_trade(df) or
                        (validation.get('market_conditions', {}).get('risk_level') == 'high' and 
                         validation.get('confidence', 1.0) < 0.4)
                    )
                
                if should_exit:
                    logger.info(f"{symbol} - Market conditions indicate exit")
                    position_size = trade_info.get('volume', None)
                    if position_size and executor.close_trade(trade_id, position_size, "AI/Market Exit"):
                        exit_price = current_price['bid'] if trade_info['side'] == 'buy' else current_price['ask']
                        self._log_trade_result(trade_info, exit_price, df, symbol)
                        
                        if self.telegram.enabled:
                            self.telegram.send_message(
                                f"Trade Closed - {symbol} Market Conditions\n"
                                f"Risk Level: {market_conditions.get('risk_level', 'normal')}\n"
                                f"AI Confidence: {validation.get('confidence', 0.0):.1%}\n"
                                f"Final Profit: {profit:.2f}"
                            )
                    strategy.set_current_trade(None)
                    return
                
                # Enhanced trailing with dynamic partial profit booking (e.g. 50% lot) and SL/TP trailing
                trailing_result = strategy.update_trailing_stop(df, price)
                
                if trailing_result:
                    modifications_made = False
                    
                    # 1. Execute Dynamic Partial Profit Booking if triggered at Breakeven stage
                    if trailing_result.get('partial_close', False):
                        curr_vol = float(trade_info.get('volume', trade_info.get('position_size', 0.02)))
                        close_pct = float(trailing_result.get('partial_close_pct', 50.0))
                        vol_to_close = curr_vol * (close_pct / 100.0)
                        
                        logger.info(f"{symbol} - Executing Dynamic Partial Close: Booking {close_pct}% ({vol_to_close:.2f} lots of {curr_vol:.2f} lots)...")
                        part_res = executor.partial_close_trade(trade_id, vol_to_close, f"Partial_{int(close_pct)}pct_BE")
                        
                        if part_res.get('success', False):
                            logger.info(f"{symbol} - 💰 Partial Close SUCCESS: Booked {part_res['closed_volume']} lots at {part_res.get('close_price', price)}. Remaining: {part_res['remaining_volume']} lots.")
                            if self.telegram.enabled:
                                self.telegram.send_message(
                                    f"🎯 Partial Profit Booked - {symbol}\n"
                                    f"Closed: {part_res['closed_volume']} lots ({close_pct}%)\n"
                                    f"Remaining: {part_res['remaining_volume']} lots\n"
                                    f"Close Price: {part_res.get('close_price', price):.5f}\n"
                                    f"Status: SL Moved to Breakeven (Risk-Free Runner)"
                                )
                        else:
                            logger.warning(f"{symbol} - Partial close failed: {part_res.get('message', 'Unknown error')}")
                    
                    # 2. Update stop loss if provided (Breakeven or Trailing Stop)
                    if trailing_result.get('stop_loss'):
                        if executor.modify_position(trade_id, stop_loss=trailing_result['stop_loss']):
                            modifications_made = True
                            logger.info(f"{symbol} - Updated stop loss to {trailing_result['stop_loss']:.5f}")
                    
                    # 3. Update take profit if provided (Trailing TP)
                    if trailing_result.get('take_profit'):
                        if executor.modify_position(trade_id, take_profit=trailing_result['take_profit']):
                            modifications_made = True
                            logger.info(f"{symbol} - Updated trailing TP to {trailing_result['take_profit']:.5f}")
                    
                    # Send notification if SL/TP modifications were made
                    if modifications_made and self.telegram.enabled:
                        msg = f"Trailing / SL Update - {symbol}\n"
                        if trailing_result.get('stop_loss'):
                            msg += f"New SL: {trailing_result['stop_loss']:.5f}\n"
                        if trailing_result.get('take_profit'):
                            msg += f"New TP: {trailing_result['take_profit']:.5f}\n"
                        msg += f"Current Profit: {profit_display}"
                        self.telegram.send_message(msg)
            else:
                strategy.set_current_trade(None)
                
        except Exception as e:
            logger.error(f"Error monitoring {symbol}: {str(e)}")

    def check_for_signals(self):
        """
        Enhanced multi-symbol signal checking with correlation filtering
        """
        try:
            # Multi-symbol signal checking
            if self.executors:
                logger.info(f"=== SIGNAL CHECK CYCLE STARTED - Checking {len(self.active_symbols)} symbols ===")
                for symbol in self.active_symbols:
                    try:
                        logger.info(f">>> CHECKING SIGNALS FOR: {symbol}")
                        self._check_symbol_signals(symbol)
                        logger.info(f">>> COMPLETED signal check for: {symbol}")
                    except Exception as e:
                        logger.error(f"ERROR checking signals for {symbol}: {str(e)}")
                logger.info("=== SIGNAL CHECK CYCLE COMPLETED ===")
            else:
                # Fallback to single symbol mode
                logger.info(">>> CHECKING SIGNALS - Single Symbol Mode")
                self._check_single_symbol_signals()
                
        except Exception as e:
            logger.error(f"Error in check_for_signals: {str(e)}")
    
    def _check_symbol_signals(self, symbol):
        """
        Check trading signals for a specific symbol
        """
        try:
            executor = self.executors.get(symbol)
            strategy = self.strategies.get(symbol)
            symbol_config = config.SYMBOLS.get(symbol, {})
            
            if not executor or not strategy:
                logger.warning(f"  \\- {symbol}: Missing executor or strategy - SKIPPED")
                return
            
            # Check global risk limits
            if not self.check_global_risk_limits():
                logger.info(f"  \\- {symbol}: Global risk limits exceeded - SKIPPED")
                return
            
            # Get current open trades for this symbol
            current_trades = executor.update_trade_status_mt5()
            
            # Check if we can add more trades for this symbol
            max_trades = symbol_config.get('max_trades', 1)
            if len(current_trades) >= max_trades:
                logger.info(f"  \\- {symbol}: Max trades reached ({len(current_trades)}/{max_trades}) - SKIPPED")
                return
            
            logger.info(f"  +- {symbol}: Risk checks passed, starting analysis...")
            logger.info(f"  +- {symbol}: Current trades: {len(current_trades)}, Max allowed: {max_trades}")
            
            mode = getattr(config, 'STRATEGY_MODE', 'pde')
            
            # ── 1. PDE Strategy Mode (5M Structural Fib Zones) ────────────
            if mode == 'pde' and getattr(config, 'PDE_SETTINGS', {}).get('enabled', False):
                pde_tf = getattr(config, 'PDE_SETTINGS', {}).get('timeframe', '5m')
                candle_count = 150
                logger.info(f"  +- {symbol}: PDE MODE - Fetching {candle_count} candles on {pde_tf}...")
                
                df_pde = executor.fetch_historical_data_mt5_symbol(symbol, pde_tf, candle_count)
                if df_pde is None or len(df_pde) < 60:
                    logger.warning(f"  \\- {symbol}: Insufficient historical data on {pde_tf} - SKIPPED")
                    return
                
                # Dynamically sync symbol-specific Min R:R Ratio from UI configuration
                sym_min_rr = symbol_config.get('min_rr_ratio')
                if sym_min_rr is None:
                    sym_min_rr = getattr(config, 'PDE_SETTINGS', {}).get('min_rr', 1.5)
                if hasattr(strategy, 'pde_engine'):
                    strategy.pde_engine.min_rr = float(sym_min_rr)

                # Generate PDE signals
                df_pde = strategy.generate_signals(df_pde)
                
                # Evaluate the most recently COMPLETED/CLOSED candle (iloc[-2]) to avoid false mid-candle fluctuations
                # (iloc[-1] is the uncompleted in-progress live candle which fluctuates before the period finishes)
                confirmed_bar = df_pde.iloc[-2] if len(df_pde) >= 2 else df_pde.iloc[-1]
                live_bar = df_pde.iloc[-1]
                
                if confirmed_bar['signal'] == 0 or pd.isna(confirmed_bar.get('entry_price')):
                    zone_name = str(confirmed_bar.get('pde_zone', 'equilibrium'))
                    rsi_val = float(confirmed_bar.get('rsi', 0.0)) if pd.notna(confirmed_bar.get('rsi')) else None
                    bar_bull = confirmed_bar['close'] > confirmed_bar['open']
                    candle_color = "GREEN" if bar_bull else ("RED" if confirmed_bar['close'] < confirmed_bar['open'] else "DOJI")
                    
                    # Detailed diagnostic reasons
                    reasons = []
                    if zone_name not in ['discount', 'premium']:
                        reasons.append(f"Zone is {zone_name.upper()} (needs DISCOUNT for BUY or PREMIUM for SELL)")
                    elif zone_name == 'discount':
                        if rsi_val is not None and rsi_val > 42.0:
                            reasons.append(f"RSI {rsi_val:.1f} > 42.0 (not oversold)")
                        if not bar_bull:
                            reasons.append("Candle is RED (needs GREEN bullish confirmation)")
                        if (rsi_val is None or rsi_val <= 42.0) and bar_bull:
                            reasons.append(f"R:R below required {float(sym_min_rr):.2f}x")
                    elif zone_name == 'premium':
                        if rsi_val is not None and rsi_val < 58.0:
                            reasons.append(f"RSI {rsi_val:.1f} < 58.0 (not overbought)")
                        if bar_bull:
                            reasons.append("Candle is GREEN (needs RED bearish confirmation)")
                        if (rsi_val is None or rsi_val >= 58.0) and not bar_bull:
                            reasons.append(f"R:R below required {float(sym_min_rr):.2f}x")
                    
                    reason_str = " | ".join(reasons) if reasons else "Conditions not met"
                    rsi_str = f"{rsi_val:.1f}" if rsi_val is not None else "N/A"
                    logger.info(f"  \\- {symbol}: No PDE signal (Zone: {zone_name}, Price: {live_bar['close']:.5f}, RSI: {rsi_str}, Candle: {candle_color}) -> Reason: [{reason_str}] - NO TRADE")
                    return
                
                # Check if we already traded this exact completed candle bar to prevent duplicates
                bar_time = str(confirmed_bar.get('time', ''))
                if not hasattr(self, '_last_pde_trade_bars'):
                    self._last_pde_trade_bars = {}
                
                if bar_time and self._last_pde_trade_bars.get(symbol) == bar_time:
                    logger.info(f"  \\- {symbol}: PDE signal on closed bar {bar_time} already executed - WAITING for next bar")
                    return
                
                signal_direction = int(confirmed_bar['signal'])
                signal_type = "BUY" if signal_direction > 0 else "SELL"
                entry_price = float(live_bar['close'])  # Execute at current live market price
                stop_loss = float(confirmed_bar.get('stop_loss', confirmed_bar.get('sl', 0.0)))
                take_profit = float(confirmed_bar.get('take_profit', confirmed_bar.get('tp2', confirmed_bar.get('tp1', 0.0))))
                rr_ratio = float(confirmed_bar.get('rr_tp2', 1.5))
                zone_name = str(confirmed_bar.get('pde_zone', ''))
                
                logger.info(f"  +- {symbol}: [PDE SIGNAL TRIGGERED on CLOSED BAR {bar_time}] {signal_type} in {zone_name.upper()} ZONE! Entry: {entry_price:.5f}, SL: {stop_loss:.5f}, TP: {take_profit:.5f}, RR: {rr_ratio:.2f}")
                
                # Check correlation risk
                if not executor.check_correlation_risk(symbol, signal_direction):
                    logger.info(f"  \\- {symbol}: Correlation risk too high for {signal_type} signal - BLOCKED")
                    return
                
                # Check open positions
                if executor.get_open_positions():
                    logger.warning(f"Trade signal ignored for {symbol} - position opened during analysis")
                    return
                
                # Position Sizing
                fixed_lot = symbol_config.get('fixed_lot_size')
                if fixed_lot and fixed_lot > 0:
                    position_size = float(fixed_lot)
                else:
                    account_balance = executor.get_account_balance() or 2000.0
                    position_size = executor.calculate_dynamic_position_size(
                        symbol, account_balance, entry_price, stop_loss
                    )
                
                logger.info(f"[EXECUTING PDE] {symbol} {signal_type} TRADE:")
                logger.info(f"   Zone: {zone_name} | Lots: {position_size} | Entry: {entry_price:.5f} | SL: {stop_loss:.5f} | TP: {take_profit:.5f} | R:R: {rr_ratio:.2f}")
                
                trade_id = executor.execute_trade(
                    signal_direction, entry_price, stop_loss, take_profit, position_size, f"PDE_{zone_name}"
                )
                
                if trade_id:
                    self._last_pde_trade_bars[symbol] = bar_time
                    logger.info(f"[SUCCESS] {symbol} PDE trade opened with ID: {trade_id}")
                    if self.telegram.enabled:
                        self.telegram.send_message(
                            f"[PDE TRADE EXECUTED] {signal_type} - {symbol}\n"
                            f"Zone: {zone_name.upper()}\n"
                            f"Entry: {entry_price:.5f}\n"
                            f"SL: {stop_loss:.5f}\n"
                            f"TP: {take_profit:.5f}\n"
                            f"Lots: {position_size}\n"
                            f"Trade ID: {trade_id}"
                        )
                else:
                    logger.error(f"[FAILED] {symbol} PDE trade execution failed")
                return

            # ── 2. Scalping / SMC Mode Fallback ──────────────────────────
            timeframes = ['5m', '1m']
            mtf_analysis = {}
            
            logger.info(f"  +- {symbol}: SCALPING MODE - Analyzing {len(timeframes)} short timeframes...")
            
            # Fetch and analyze data for each timeframe
            for tf in timeframes:
                try:
                    candle_count = 200 if tf == '5m' else 300
                    df = executor.fetch_historical_data_mt5_symbol(symbol, tf, candle_count)
                    
                    if df is not None:
                        df = strategy.analyze_market(df)
                        trend = self._determine_trend(df)
                        structure = self._analyze_structure(df)
                        
                        mtf_analysis[tf] = {
                            'df': df,
                            'trend': trend,
                            'structure': structure,
                            'current_price': df['close'].iloc[-1],
                            'atr': df.get('atr', pd.Series([0])).iloc[-1]
                        }
                        logger.info(f"    +- {tf}: {trend} trend, Price: {df['close'].iloc[-1]:.5f}")
                    else:
                        logger.warning(f"    +- {tf}: Failed to fetch data")
                except Exception as e:
                    logger.error(f"    +- {tf}: Analysis error - {str(e)}")
            
            if not mtf_analysis:
                logger.error(f"  \\- {symbol}: No timeframe data available - ABORTED")
                return
            
            logger.info(f"  +- {symbol}: Checking confluence across {len(mtf_analysis)} timeframes...")
            confluence = self._check_scalping_confluence(mtf_analysis)
            
            if confluence['signal'] == 0:
                logger.info(f"  \\- {symbol}: No scalping signal found - NO TRADE")
                return
            
            signal_type = "BUY" if confluence['signal'] > 0 else "SELL"
            logger.info(f"  +- {symbol}: SCALPING SIGNAL! {signal_type} (confidence: {confluence.get('confidence', 0):.1%})")
            
            signal_direction = confluence['signal']
            if not executor.check_correlation_risk(symbol, signal_direction):
                logger.info(f"  \\- {symbol}: Correlation risk too high for {signal_type} signal - BLOCKED")
                return
            
            logger.info(f"  +- {symbol}: Correlation risk acceptable, proceeding with {signal_type} signal...")
            
            primary_df = mtf_analysis.get('1m', {}).get('df')
            if primary_df is None:
                logger.error(f"Primary scalping timeframe (1m) data not available for {symbol}")
                return
            
            high_quality_signal = self.enhanced_signal_generator.generate_high_quality_signals(
                primary_df, symbol, strategy, confluence
            )
            
            # Check if we got a high-quality signal
            if high_quality_signal:
                # Enhanced signal validation
                entry_price = high_quality_signal['entry_price']
                stop_loss = high_quality_signal['stop_loss']
                take_profit = high_quality_signal['take_profit']
                
                # Check for NaN or invalid values
                if (pd.isna(entry_price) or pd.isna(stop_loss) or pd.isna(take_profit) or
                    entry_price <= 0 or stop_loss <= 0 or take_profit <= 0):
                    logger.error(f"Invalid signal values for {symbol} - Entry: {entry_price}, SL: {stop_loss}, TP: {take_profit}")
                    logger.error("TRADE EXECUTION BLOCKED - Invalid price levels")
                    return
                
                # Enhanced quality checks with adaptive validation
                risk_distance = abs(entry_price - stop_loss)
                reward_distance = abs(take_profit - entry_price)
                
                # Get adaptive minimum distance
                min_distance = executor.get_minimum_distance() if hasattr(executor, 'get_minimum_distance') else 0.0001
                
                # Apply adaptive minimum distance check
                if risk_distance < min_distance:
                    # Try to adjust the signal if it's close to minimum
                    adjustment_factor = min_distance / risk_distance
                    if adjustment_factor <= 2.0:  # Only adjust if within 2x of minimum
                        if signal_direction > 0:  # BUY signal
                            adjusted_sl = entry_price - min_distance
                            adjusted_tp = entry_price + (reward_distance * adjustment_factor)
                        else:  # SELL signal
                            adjusted_sl = entry_price + min_distance
                            adjusted_tp = entry_price - (reward_distance * adjustment_factor)
                        
                        logger.info(f"Adjusted {symbol} signal - SL: {stop_loss:.5f} -> {adjusted_sl:.5f}, TP: {take_profit:.5f} -> {adjusted_tp:.5f}")
                        high_quality_signal['stop_loss'] = adjusted_sl
                        high_quality_signal['take_profit'] = adjusted_tp
                        
                        # Recalculate distances
                        risk_distance = abs(entry_price - adjusted_sl)
                        reward_distance = abs(adjusted_tp - entry_price)
                    else:
                        logger.warning(f"Risk distance {risk_distance:.5f} too small for {symbol} (min: {min_distance:.5f}) - adjustment would be too large")
                        return
                
                # Check risk-reward ratio with more lenient approach
                rr_ratio = reward_distance / risk_distance if risk_distance > 0 else 0
                min_rr = symbol_config.get('min_rr_ratio', 1.2)  # Default reduced to 1.2
                
                # For scalping signals, allow lower RR ratios
                if 'scalp' in high_quality_signal.get('signal_type', '').lower():
                    min_rr = max(1.0, min_rr * 0.8)  # 20% reduction for scalping
                
                if rr_ratio < min_rr:
                    logger.warning(f"Risk-reward ratio {rr_ratio:.2f} below minimum {min_rr} for {symbol}")
                    # Don't return immediately for scalping - try one more adjustment
                    if 'scalp' in high_quality_signal.get('signal_type', '').lower() and rr_ratio >= 0.8:
                        logger.info(f"Accepting scalping signal with RR {rr_ratio:.2f} (below normal minimum but acceptable for scalping)")
                    else:
                        return
                
                logger.info(f"[SUCCESS] {symbol} signal validation passed - RR: {rr_ratio:.2f}, Risk: {risk_distance:.5f}")
                
                # Check if another trade was opened during analysis
                if executor.get_open_positions():
                    logger.warning(f"Trade signal ignored for {symbol} - position opened during analysis")
                    return
                    
                current_price = executor.get_current_price()
                if not current_price:
                    logger.error(f"Failed to get current price for {symbol}")
                    return
                    
                # Calculate position size with enhanced risk management
                account_balance = executor.get_account_balance()
                if not account_balance:
                    logger.error(f"Failed to get account balance for {symbol}")
                    return
                    
                position_size = executor.calculate_dynamic_position_size(
                    symbol,
                    account_balance,
                    high_quality_signal['entry_price'],
                    high_quality_signal['stop_loss']
                )
                
                # Execute the trade with enhanced logging
                logger.info(f"[EXECUTING] {symbol} {signal_type} TRADE:")
                logger.info(f"   Entry: {high_quality_signal['entry_price']:.5f}")
                logger.info(f"   Stop Loss: {high_quality_signal['stop_loss']:.5f}")
                logger.info(f"   Take Profit: {high_quality_signal['take_profit']:.5f}")
                logger.info(f"   Position Size: {position_size}")
                logger.info(f"   Risk-Reward: {rr_ratio:.2f}")
                logger.info(f"   Quality Score: {high_quality_signal.get('quality_score', 0):.1f}%")
                
                trade_id = executor.execute_trade(
                    high_quality_signal['signal'],
                    high_quality_signal['entry_price'],
                    high_quality_signal['stop_loss'],
                    high_quality_signal['take_profit'],
                    position_size,
                    high_quality_signal['signal_type']
                )
                
                if trade_id:
                    logger.info(f"[SUCCESS] {symbol} trade opened with ID: {trade_id}")
                    logger.info(f"Trade Type: {high_quality_signal['signal_type']}")
                    logger.info(f"Quality Score: {high_quality_signal.get('quality_score', 0):.1f}%")
                    
                    # Send enhanced notification
                    if self.telegram.enabled:
                        if 'BTC' in symbol:
                            target_amount = abs(high_quality_signal['take_profit'] - high_quality_signal['entry_price'])
                            risk_amount = abs(high_quality_signal['entry_price'] - high_quality_signal['stop_loss'])
                            self.telegram.send_message(
                                f"[TRADE EXECUTED] {signal_type} - {symbol}\n"
                                f"Type: {high_quality_signal['signal_type']}\n"
                                f"Entry: {high_quality_signal['entry_price']:.2f}\n"
                                f"Target: +${target_amount:.2f}\n"
                                f"Risk: -${risk_amount:.2f}\n"
                                f"Size: {position_size} lots\n"
                                f"RR: {rr_ratio:.2f}\n"
                                f"Quality: {high_quality_signal.get('quality_score', 0):.1f}%\n"
                                f"Trade ID: {trade_id}"
                            )
                        else:
                            pips_target = abs(high_quality_signal['take_profit'] - high_quality_signal['entry_price']) * 10000
                            pips_risk = abs(high_quality_signal['entry_price'] - high_quality_signal['stop_loss']) * 10000
                            self.telegram.send_message(
                                f"[TRADE EXECUTED] {signal_type} - {symbol}\n"
                                f"Type: {high_quality_signal['signal_type']}\n"
                                f"Entry: {high_quality_signal['entry_price']:.5f}\n"
                                f"Target: +{pips_target:.1f} pips\n"
                                f"Risk: -{pips_risk:.1f} pips\n"
                                f"Size: {position_size} lots\n"
                                f"RR: {rr_ratio:.2f}\n"
                                f"Quality: {high_quality_signal.get('quality_score', 0):.1f}%\n"
                                f"Trade ID: {trade_id}"
                            )
                else:
                    logger.error(f"[FAILED] {symbol} trade execution failed")
                    logger.error(f"Signal details: {high_quality_signal['signal_type']}, Entry: {high_quality_signal['entry_price']:.5f}")
                
        except Exception as e:
            logger.error(f"Error checking signals for {symbol}: {str(e)}")
    
    def _determine_trend(self, df):
        """
        Determine trend direction for a timeframe
        """
        try:
            # Simple trend determination using moving averages
            ma_20 = df['close'].rolling(20).mean()
            ma_50 = df['close'].rolling(50).mean()
            
            if ma_20.iloc[-1] > ma_50.iloc[-1]:
                return 'bullish'
            else:
                return 'bearish'
        except Exception:
            return 'neutral'
    
    def _analyze_structure(self, df):
        """
        Analyze market structure for break of structure
        """
        try:
            recent = df.iloc[-10:]
            return {
                'bos_bullish': recent.get('bos_bullish', pd.Series([False])).any(),
                'bos_bearish': recent.get('bos_bearish', pd.Series([False])).any(),
                'has_structure_break': recent.get('bos_bullish', pd.Series([False])).any() or recent.get('bos_bearish', pd.Series([False])).any()
            }
        except Exception:
            return {'bos_bullish': False, 'bos_bearish': False, 'has_structure_break': False}
    
    def _check_scalping_confluence(self, mtf_analysis):
        """
        Check for scalping confluence across short timeframes (more aggressive)
        """
        try:
            confluence = {
                'signal': 0,
                'confidence': 0,
                'bullish_votes': 0,
                'bearish_votes': 0,
                'timeframe_weights': {'5m': 2, '1m': 3}  # 1m gets higher weight for scalping
            }
            
            total_weight = 0
            bullish_weight = 0
            bearish_weight = 0
            
            for tf, data in mtf_analysis.items():
                weight = confluence['timeframe_weights'].get(tf, 1)
                total_weight += weight
                
                trend = data.get('trend', 'neutral')
                structure = data.get('structure', {})
                
                # Check trend alignment
                if trend == 'bullish':
                    bullish_weight += weight
                    confluence['bullish_votes'] += 1
                elif trend == 'bearish':
                    bearish_weight += weight
                    confluence['bearish_votes'] += 1
                
                # Boost confidence for structure breaks
                if structure.get('bos_bullish'):
                    bullish_weight += weight * 0.5
                if structure.get('bos_bearish'):
                    bearish_weight += weight * 0.5
            
            # Determine overall signal based on weighted votes (more aggressive for scalping)
            if bullish_weight > bearish_weight and bullish_weight / total_weight > 0.4:  # Lower threshold for scalping
                confluence['signal'] = 1
                confluence['confidence'] = bullish_weight / total_weight
            elif bearish_weight > bullish_weight and bearish_weight / total_weight > 0.4:  # Lower threshold for scalping
                confluence['signal'] = -1
                confluence['confidence'] = bearish_weight / total_weight
            
            return confluence
            
        except Exception as e:
            logger.error(f"Error in confluence analysis: {str(e)}")
            return {'signal': 0, 'confidence': 0}
    
    def process_unprocessed_signals(self):
        """
        Process any unprocessed signals from the database
        """
        try:
            # Get unprocessed signals
            signals = self.db.get_unprocessed_signals()
            
            for signal in signals:
                # Mark signal as processed for now
                # TODO: Implement signal processing logic if needed
                self.db.mark_signal_processed(signal['id'])
            
        except Exception as e:
            logger.error(f"Error processing unprocessed signals: {str(e)}")
    
    def start(self):
        """
        Start the trading bot
        """
        try:
            logger.info("Starting Enhanced Multi-Symbol Trading Bot with Quality Filters...")
            
            # Send startup notification
            if self.telegram.enabled:
                self.telegram.send_message(
                    f"[ENHANCED BOT STARTED]\n"
                    f"Active Symbols: {', '.join(self.active_symbols)}\n"
                    f"Quality Filtering: ENABLED\n"
                    f"AI Analysis: ACTIVE\n"
                    f"Signal Frequency: Every 2 minutes\n"
                    f"Min Quality Score: 65%\n"
                    f"Status: Ready for high-quality trades"
                )
    
            
            # Schedule scalping tasks with high-frequency intervals
            intervals = config.SCHEDULER_INTERVALS
            
            # Check signals for all symbols (much more frequent for scalping)
            self.scheduler.add_job(self.check_for_signals, 'interval', 
                                 seconds=intervals.get('signal_check', 60),  # Every 10 seconds for scalping
                                 name='scalping_signal_check')
            
            # Monitor active trades with aggressive trailing (very frequent)
            self.scheduler.add_job(self.update_open_trades, 'interval', 
                                 seconds=intervals.get('trade_monitor', 30),  # Every 3 seconds for scalping
                                 name='scalping_trade_monitor')
            
            # Update correlations periodically
            if len(self.active_symbols) > 1:
                self.scheduler.add_job(self.update_correlations, 'interval', 
                                     seconds=intervals.get('correlation_update', 300), 
                                     name='correlation_update')
            
            # Risk assessment
            self.scheduler.add_job(self.check_global_risk_limits, 'interval', 
                                 seconds=intervals.get('risk_check', 120), 
                                 name='risk_check')
            
            # Start scheduler
            self.scheduler.start()
            
            # Keep the main thread alive
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                self.stop()
                
        except Exception as e:
            logger.error(f"Error starting bot: {str(e)}")
            self.stop()
    
    def stop(self):
        """
        Stop the trading bot
        """
        try:
            logger.info("Stopping Gold Trading Bot...")
            
            # Stop scheduler
            self.scheduler.shutdown()
            
            # Stop webhook listener
            # self.webhook_listener.stop()
            
            # Close database connection
            self.db.close()
            
            # Set running flag
            self.running = False
            
            # Send shutdown notification
            if self.telegram.enabled:
                self.telegram.send_message("STOPPED - Multi-Symbol Trading Bot\n\nBot has been shut down.")
            
            logger.info("Bot stopped.")
            
        except Exception as e:
            logger.error(f"Error stopping bot: {str(e)}")

    def _check_single_symbol_signals(self):
        """
        Fallback method for single symbol mode
        """
        try:
            # Check if MT5 executor is available
            if not self.trade_executor:
                logger.warning("MT5 executor not available - skipping signal check")
                return
                
            # Check if strategy is available
            if not self.strategy:
                logger.warning("Strategy not available - skipping signal check")
                return
                
            # Get current open trades
            current_trades = self.trade_executor.update_trade_status_mt5()
            
            # Only check for signals if we have no active trades
            if current_trades:
                logger.info("Skipping signal check - active trade already exists")
                return
            
            # Multi-timeframe analysis for single symbol
            timeframes = ['4h', '1h', '15m', '5m']
            mtf_analysis = {}
            
            # Fetch and analyze data for each timeframe
            for tf in timeframes:
                try:
                    candle_count = 100 if tf in ['4h', '1h'] else 200
                    df = self.trade_executor.fetch_historical_data_mt5(tf, candle_count)
                    
                    if df is not None:
                        # Analyze market data
                        df = self.strategy.analyze_market(df)
                        mtf_analysis[tf] = {
                            'df': df,
                            'trend': self._determine_trend(df),
                            'structure': self._analyze_structure(df),
                            'current_price': df['close'].iloc[-1],
                            'atr': df.get('atr', pd.Series([0])).iloc[-1]
                        }
                    else:
                        logger.warning(f"Failed to fetch {tf} data")
                except Exception as e:
                    logger.error(f"Error analyzing {tf} timeframe: {str(e)}")
            
            if not mtf_analysis:
                logger.error("No timeframe data available")
                return
            
            # Check for confluence across timeframes
            confluence = self._check_scalping_confluence(mtf_analysis)
            
            if confluence['signal'] == 0:
                logger.info("No confluence signal found across timeframes")
                return
            
            # Use primary timeframe (15m) for signal generation
            primary_df = mtf_analysis.get('15m', {}).get('df')
            if primary_df is None:
                logger.error("Primary timeframe data not available")
                return
            
            # Generate signals with enhanced confluence logic
            df = self.strategy.generate_signals_with_confluence(primary_df, confluence, mtf_analysis)
            
            # Check for new signals in the latest candle
            latest = df.iloc[-1]
            if latest['signal'] != 0:
                # Validate signal values
                entry_price = latest['entry_price']
                stop_loss = latest['stop_loss']
                take_profit = latest['take_profit']
                
                if (pd.isna(entry_price) or pd.isna(stop_loss) or pd.isna(take_profit) or
                    entry_price <= 0 or stop_loss <= 0 or take_profit <= 0):
                    logger.error("Invalid signal values detected - TRADE EXECUTION BLOCKED")
                    return
                
                # Check if another trade was opened during analysis
                if self.trade_executor.get_open_positions():
                    logger.warning("Trade signal ignored - position opened during analysis")
                    return
                    
                current_price = self.trade_executor.get_current_price()
                if not current_price:
                    logger.error("Failed to get current price")
                    return
                    
                # Calculate position size
                account_balance = self.trade_executor.get_account_balance()
                if not account_balance:
                    logger.error("Failed to get account balance")
                    return
                    
                position_size = self.strategy.calculate_position_size(
                    account_balance,
                    latest['entry_price'],
                    latest['stop_loss']
                )
                
                # Execute the trade
                trade_id = self.trade_executor.execute_trade(
                    latest['signal'],
                    latest['entry_price'],
                    latest['stop_loss'],
                    latest['take_profit'],
                    position_size,
                    latest['signal_type']
                )
                
                if trade_id:
                    logger.info(f"New trade opened: {latest['signal_type']}")
                    # Send notification
                    if self.telegram.enabled:
                        self.telegram.send_message(
                            f"NEW TRADE Opened\n"
                            f"Type: {latest['signal_type']}\n"
                            f"Entry: {latest['entry_price']:.5f}\n"
                            f"Stop Loss: {latest['stop_loss']:.5f}\n"
                            f"Take Profit: {latest['take_profit']:.5f}\n"
                            f"Size: {position_size}\n"
                            f"AI Confidence: {latest['ai_confidence']:.1%}"
                        )
                
        except Exception as e:
            logger.error(f"Error checking single symbol signals: {str(e)}")


# Handle system signals

    def _update_single_symbol_trades(self):
        """
        Fallback method for single symbol mode
        """
        try:
            if not hasattr(self, 'trade_executor') or not self.trade_executor:
                logger.warning("Single symbol mode - MT5 executor not available")
                return
                
            if not hasattr(self, 'strategy') or not self.strategy:
                logger.warning("Single symbol mode - strategy not available")
                return
                
            # Get current open trades
            try:
                current_trades = self.trade_executor.update_trade_status_mt5()
                if current_trades:
                    logger.info("Single symbol mode - monitoring existing trades")
                    # Simple monitoring logic
                    for trade_id, trade_info in current_trades.items():
                        logger.info(f"Monitoring trade {trade_id}: {trade_info.get('side', 'unknown')} at {trade_info.get('entry_price', 'unknown')}")
                else:
                    logger.debug("Single symbol mode - no active trades")
            except Exception as e:
                logger.error(f"Error in single symbol trade monitoring: {e}")
                
        except Exception as e:
            logger.error(f"Error in single symbol mode: {e}")


def signal_handler(sig, frame):
    logger.info(f"Received signal {sig}. Stopping bot...")
    if bot:
        bot.stop()
    sys.exit(0)


# Register signal handlers
sys_signal.signal(sys_signal.SIGINT, signal_handler)
sys_signal.signal(sys_signal.SIGTERM, signal_handler)


# Main entry point
if __name__ == "__main__":
    # Create bot instance
    bot = GoldTradingBot()
    
    # Start the bot
    bot.start()