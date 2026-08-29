# MT5 Trade execution module for the Multi-Symbol Trading Bot

import MetaTrader5 as mt5
import os
import time
import logging
import pandas as pd
import numpy as np
from datetime import datetime
import config

logger = logging.getLogger('gold_trading_bot')


class MT5Executor:
    """
    Enhanced class to handle multi-symbol trade execution with MT5
    """
    
    def __init__(self, login=240959058, password="", server="Exness-MT5Trial6", symbol="XAUUSDm"):
        logger.info("Initializing Enhanced MT5Executor for Multi-Symbol Trading")
        logger.info(f"Initializing MT5Executor with login: {login}, server: {server}, primary symbol: {symbol}")
        self.login = login
        self.password = password
        self.server = server
        self.symbol = symbol  # Primary symbol for backward compatibility
        self.connected = False
        self.open_trades = {}
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        
        # Multi-symbol support
        self.symbols = list(config.SYMBOLS.keys())
        self.symbol_info = {}
        self.correlations = {}
        self.last_correlation_update = 0
        
        # Risk tracking
        self.daily_pnl = 0.0
        self.peak_balance = 0.0
        self.current_total_risk = 0.0
        
        # Initialize connection to MT5
        self._initialize_connection()
        
        # Initialize all symbols
        self._initialize_symbols()
    
    def _initialize_symbols(self):
        """
        Initialize all trading symbols and get their specifications
        """
        if not self.connected:
            logger.warning("Not connected to MT5, skipping symbol initialization")
            return
            
        try:
            for symbol in self.symbols:
                if not config.SYMBOLS[symbol]['enabled']:
                    continue
                    
                # Get symbol info
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info is None:
                    logger.warning(f"Symbol {symbol} not found")
                    continue
                
                # Enable symbol if not visible
                if not symbol_info.visible:
                    if not mt5.symbol_select(symbol, True):
                        logger.error(f"Failed to select symbol {symbol}")
                        continue
                
                # Store symbol specifications
                self.symbol_info[symbol] = {
                    'point': symbol_info.point,
                    'digits': symbol_info.digits,
                    'volume_min': symbol_info.volume_min,
                    'volume_max': symbol_info.volume_max,
                    'volume_step': symbol_info.volume_step,
                    'margin_initial': symbol_info.margin_initial,
                    'trade_contract_size': symbol_info.trade_contract_size,
                    'spread': symbol_info.spread,
                }
                
                logger.info(f"Initialized symbol {symbol}: "
                           f"Point={symbol_info.point}, "
                           f"Digits={symbol_info.digits}, "
                           f"Min Volume={symbol_info.volume_min}")
                           
        except Exception as e:
            logger.error(f"Error initializing symbols: {str(e)}")
    
    def calculate_correlations(self, lookback_periods=100):
        """
        Calculate correlations between enabled symbols
        """
        if not self.connected:
            return {}
            
        try:
            # Get enabled symbols
            enabled_symbols = [s for s in self.symbols if config.SYMBOLS[s]['enabled']]
            if len(enabled_symbols) < 2:
                return {}
            
            # Fetch price data for all symbols
            price_data = {}
            for symbol in enabled_symbols:
                try:
                    df = self.fetch_historical_data_mt5_symbol(symbol, '1h', lookback_periods)
                    if df is not None and len(df) > 50:
                        price_data[symbol] = df['close'].pct_change().dropna()
                except Exception as e:
                    logger.error(f"Error fetching data for correlation: {symbol} - {str(e)}")
                    continue
            
            # Calculate correlations
            correlations = {}
            symbols_list = list(price_data.keys())
            
            for i, symbol1 in enumerate(symbols_list):
                for j, symbol2 in enumerate(symbols_list[i+1:], i+1):
                    try:
                        # Align the data
                        data1 = price_data[symbol1]
                        data2 = price_data[symbol2]
                        
                        # Find common index
                        common_index = data1.index.intersection(data2.index)
                        if len(common_index) > 30:
                            corr = data1.loc[common_index].corr(data2.loc[common_index])
                            correlations[f"{symbol1}_{symbol2}"] = corr
                            correlations[f"{symbol2}_{symbol1}"] = corr
                            
                            logger.info(f"Correlation {symbol1}-{symbol2}: {corr:.3f}")
                    except Exception as e:
                        logger.error(f"Error calculating correlation {symbol1}-{symbol2}: {str(e)}")
            
            self.correlations = correlations
            self.last_correlation_update = time.time()
            return correlations
            
        except Exception as e:
            logger.error(f"Error in correlation calculation: {str(e)}")
            return {}
    
    def get_correlation(self, symbol1, symbol2):
        """
        Get correlation between two symbols
        """
        # Update correlations if stale (older than 5 minutes)
        if time.time() - self.last_correlation_update > 300:
            self.calculate_correlations()
        
        key = f"{symbol1}_{symbol2}"
        return self.correlations.get(key, 0.0)
    
    def check_correlation_risk(self, new_symbol, new_side):
        """
        Check if adding a new position would violate correlation limits
        """
        try:
            # Check if correlation filtering is enabled for this symbol
            symbol_config = config.SYMBOLS.get(new_symbol, {})
            if not symbol_config.get('correlation_filter', False):
                return True
            
            current_positions = self.get_open_positions()
            if not current_positions:
                return True
            
            threshold = config.RISK_MANAGEMENT['correlation_threshold']
            max_correlated_risk = config.RISK_MANAGEMENT['max_correlated_risk']
            
            correlated_risk = 0.0
            
            for pos in current_positions:
                pos_symbol = pos.get('symbol', '')
                pos_side = 1 if pos.get('type', 0) == 0 else -1  # 0=buy, 1=sell
                
                correlation = abs(self.get_correlation(new_symbol, pos_symbol))
                
                # If symbols are highly correlated and same direction
                if correlation > threshold:
                    if (new_side > 0 and pos_side > 0) or (new_side < 0 and pos_side < 0):
                        pos_risk = abs(pos.get('volume', 0)) * pos.get('price_open', 0) * 0.01  # Approximate risk
                        correlated_risk += pos_risk
            
            new_risk = config.SYMBOLS.get(new_symbol, {}).get('risk_percent', 1.0)
            total_correlated_risk = correlated_risk + new_risk
            
            if total_correlated_risk > max_correlated_risk:
                logger.warning(f"Correlation risk exceeded: {total_correlated_risk:.2f}% > {max_correlated_risk}%")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking correlation risk: {str(e)}")
            return True  # Allow trade if check fails
    
    def get_account_currency(self) -> str:
        """Fetch base account currency from MT5 (e.g. 'INR', 'USD', 'EUR', 'GBP')"""
        try:
            acc = mt5.account_info()
            if acc and hasattr(acc, 'currency') and acc.currency:
                return str(acc.currency).upper().strip()
        except Exception:
            pass
        return "USD"

    def get_usd_conversion_rate(self, account_currency: str) -> float:
        """
        Get exchange rate to convert 1 USD to account currency.
        e.g., if currency is INR, returns ~87.0 (87 INR = 1 USD).
        """
        c = (account_currency or "USD").upper().strip()
        if c in ["USD", "USDT"]:
            return 1.0
        
        # Check MT5 ticker if available
        try:
            for pair in [f"USD{c}", f"USD{c}m", f"{c}USD", f"{c}USDm"]:
                tick = mt5.symbol_info_tick(pair)
                if tick and tick.bid > 0:
                    if pair.startswith("USD"):
                        return float(tick.bid)
                    else:
                        return 1.0 / float(tick.bid)
        except Exception:
            pass

        # Fallback static exchange rates
        fallbacks = {
            "INR": 87.0,
            "RS": 87.0,
            "RUPEES": 87.0,
            "EUR": 0.92,
            "GBP": 0.78,
            "AED": 3.67,
            "JPY": 155.0,
            "CAD": 1.36,
            "AUD": 1.52,
        }
        return fallbacks.get(c, 1.0)

    def calculate_dynamic_position_size(self, symbol, account_balance, entry_price, stop_loss):
        """
        Calculate position size with multi-currency risk management.
        Supports:
          1. Fixed Lot Size (Highest priority: e.g. 0.02 lots)
          2. Fixed Risk Amount in Account Currency (e.g. ₹500 INR or $50 USD)
          3. Dynamic Risk % of Balance (e.g. 1.0%)
          4. Currency normalization for INR/EUR/GBP accounts
          5. Hard Safety Max Lot Cap (default 0.10 lots)
        """
        try:
            symbol_config = config.SYMBOLS.get(symbol, {})
            account_currency = self.get_account_currency()
            fixed_lot_size = symbol_config.get('fixed_lot_size') or symbol_config.get('lot_size')
            max_money_risk = symbol_config.get('max_risk_amount')
            
            # 1. CALCULATE BASE RISK AMOUNT IN ACCOUNT CURRENCY
            if max_money_risk is not None and float(max_money_risk) > 0:
                risk_amount_acc = float(max_money_risk)
                logger.info(f"[{symbol}] Using Money Risk Limit: {risk_amount_acc:.2f} {account_currency}")
            else:
                base_risk_percent = float(symbol_config.get('risk_percent', 1.0))
                risk_amount_acc = account_balance * (base_risk_percent / 100.0)
                logger.info(f"[{symbol}] Using Dynamic Risk {base_risk_percent}% of {account_balance:.2f} {account_currency} = {risk_amount_acc:.2f} {account_currency}")

            # 2. CONVERT RISK AMOUNT TO USD (Since Gold/Forex contracts are USD-based)
            usd_rate = self.get_usd_conversion_rate(account_currency)
            risk_amount_usd = risk_amount_acc / usd_rate
            
            price_diff = abs(entry_price - stop_loss)
            if price_diff == 0:
                logger.error(f"[{symbol}] Invalid stop loss distance (0.00) - same as entry price")
                return 0.01

            # Get symbol specifications
            symbol_spec = self.symbol_info.get(symbol, {})
            point = symbol_spec.get('point', 0.001)
            volume_min = symbol_spec.get('volume_min', 0.01)
            volume_step = symbol_spec.get('volume_step', 0.01)

            # 3. PRECISE LOT CALCULATION BY ASSET CLASS
            if 'XAU' in symbol or 'GOLD' in symbol.upper():
                # Gold: 1 Lot = 100 oz -> $1.00 move = $100 USD
                # Lots = USD Risk Amount / (Points difference * 100)
                calculated_lots = risk_amount_usd / (price_diff * 100.0)
            elif 'BTC' in symbol:
                # BTC: 1 Lot = 1 BTC -> $1.00 move = $1.00 USD
                calculated_lots = risk_amount_usd / price_diff
            elif 'USD' in symbol and symbol.endswith('m'):
                # Forex: 1 Standard Lot = 100,000 units -> $10/pip
                pip_value = 10.0
                stop_loss_pips = price_diff / (point * 10.0)
                calculated_lots = risk_amount_usd / (max(stop_loss_pips, 1.0) * pip_value)
            else:
                # Generic asset
                calculated_lots = risk_amount_usd / (price_diff * 100.0)

            # 4. DUAL CONSIDERATION: If Fixed Lot is enabled, take min(Fixed Lot, Money Risk Lot)
            if fixed_lot_size is not None and float(fixed_lot_size) > 0:
                fixed_val = float(fixed_lot_size)
                if max_money_risk is not None and float(max_money_risk) > 0:
                    # Both options enabled: strictly use fixed lot unless risk cap demands smaller
                    position_size = min(fixed_val, calculated_lots)
                    logger.info(f"[{symbol}] Dual Risk Active: Fixed Lot {fixed_val} vs Max Risk Cap Lot {calculated_lots:.2f} -> Using {position_size:.2f} lots")
                else:
                    position_size = fixed_val
                    logger.info(f"[{symbol}] Using FIXED Lot Size: {position_size:.2f} lots")
            else:
                position_size = calculated_lots

            # 5. VOLATILITY ADJUSTMENT
            if symbol_config.get('volatility_adj', False) and (fixed_lot_size is None or float(fixed_lot_size) <= 0):
                try:
                    df = self.fetch_historical_data_mt5_symbol(symbol, '1h', 24)
                    if df is not None and len(df) > 20:
                        atr = df['high'].subtract(df['low']).rolling(14).mean().iloc[-1]
                        avg_atr = df['high'].subtract(df['low']).rolling(50).mean().iloc[-1]
                        if avg_atr > 0:
                            vol_ratio = atr / avg_atr
                            if vol_ratio > 1.5:
                                position_size *= 0.75
                            elif vol_ratio < 0.7:
                                position_size *= 1.15
                except Exception as e:
                    logger.error(f"Error in volatility adjustment: {e}")

            # 6. ROUNDING & HARD SAFETY LOT CEILING
            position_size = max(volume_min, round(position_size / volume_step) * volume_step)
            
            # Hard-cap safety limits (default max 0.10 lots per position unless user configured higher)
            max_allowed_lot = float(symbol_config.get('max_lot_size', 0.10) or 0.10)
            final_position_size = min(position_size, max_allowed_lot)

            logger.info(
                f"[{symbol}] Final Position Size: {final_position_size:.2f} lots "
                f"(Risk: {risk_amount_acc:.2f} {account_currency} / ${risk_amount_usd:.2f} USD | "
                f"SL Distance: {price_diff:.3f} pts | Max Cap: {max_allowed_lot:.2f} lots)"
            )
            return round(final_position_size, 2)
            
        except Exception as e:
            logger.error(f"Error calculating position size: {str(e)}")
            return 0.01
            
        except Exception as e:
            logger.error(f"Error calculating position size: {str(e)}")
            return volume_min or 0.01
    
    def check_risk_limits(self, new_symbol=None):
        """
        Check if current risk levels are within limits
        """
        try:
            # Get account info
            account_info = mt5.account_info()
            if account_info is None:
                return False
            
            current_balance = account_info.balance
            current_equity = account_info.equity
            
            # Update peak balance
            self.peak_balance = max(self.peak_balance, current_balance)
            
            # Check drawdown
            if self.peak_balance > 0:
                drawdown = ((self.peak_balance - current_equity) / self.peak_balance) * 100
                max_dd = config.RISK_MANAGEMENT['max_drawdown_stop']
                
                if drawdown > max_dd:
                    logger.error(f"TRADING HALTED - Maximum drawdown exceeded: {drawdown:.2f}% > {max_dd}%")
                    logger.error(f"Peak Balance: ${self.peak_balance:.2f}, Current Equity: ${current_equity:.2f}")
                    return False
                elif drawdown > max_dd * 0.8:  # Warning at 80% of max drawdown
                    logger.warning(f"DRAWDOWN WARNING: {drawdown:.2f}% approaching limit of {max_dd}%")
            
            # Check total risk across all positions
            current_positions = self.get_open_positions()
            total_risk = 0.0
            
            for pos in current_positions:
                symbol = pos.get('symbol', '')
                volume = abs(pos.get('volume', 0))
                price = pos.get('price_open', 0)
                
                # Estimate risk as 1% of position value (simplified)
                position_risk = volume * price * 0.01
                total_risk += position_risk
            
            # Add new position risk if provided
            if new_symbol:
                symbol_config = config.SYMBOLS.get(new_symbol, {})
                new_risk = symbol_config.get('risk_percent', 1.0)
                total_risk += current_balance * (new_risk / 100)
            
            max_total_risk = config.RISK_MANAGEMENT['max_total_risk']
            total_risk_percent = (total_risk / current_balance) * 100
            
            if total_risk_percent > max_total_risk:
                logger.warning(f"Total risk limit exceeded: {total_risk_percent:.2f}% > {max_total_risk}%")
                return False
            
            self.current_total_risk = total_risk_percent
            return True
            
        except Exception as e:
            logger.error(f"Error checking risk limits: {str(e)}")
            return True  # Allow if check fails
    
    def fetch_historical_data_mt5_symbol(self, symbol, timeframe='1h', limit=100):
        """
        Fetch historical data for a specific symbol
        """
        if not self._ensure_connected():
            return None
        
        try:
            # Map timeframe strings to MT5 constants
            timeframe_map = {
                '1m': mt5.TIMEFRAME_M1,
                '5m': mt5.TIMEFRAME_M5,
                '15m': mt5.TIMEFRAME_M15,
                '30m': mt5.TIMEFRAME_M30,
                '1h': mt5.TIMEFRAME_H1,
                '4h': mt5.TIMEFRAME_H4,
                '1d': mt5.TIMEFRAME_D1,
            }
            
            mt5_timeframe = timeframe_map.get(timeframe, mt5.TIMEFRAME_H1)
            
            # Get the data
            rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, limit)
            
            if rates is None or len(rates) == 0:
                logger.error(f"Failed to get historical data for {symbol}: {mt5.last_error()}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            
            # Rename columns to standard format
            df.rename(columns={
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'tick_volume': 'volume'
            }, inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
            return None

    def _ensure_mt5_initialized(self):
        """
        Ensure MT5 is initialized with retry logic
        """
        # Detect installed MT5 terminal paths
        mt5_paths = [
            os.environ.get("MT5_PATH", ""),
            getattr(config, "MT5_PATH", ""),
            r"C:\Program Files\MetaTrader 5\terminal64.exe",
            r"C:\Program Files\Exness MetaTrader 5\terminal64.exe",
            r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe",
            r"C:\Program Files (x86)\Exness MetaTrader 5\terminal64.exe",
        ]
        mt5_path = None
        for p in mt5_paths:
            if p and os.path.exists(p):
                mt5_path = p
                break

        for attempt in range(self.max_retries):
            try:
                initialized = False
                # Try with explicit terminal path + credentials first
                if mt5_path and self.login and self.password and self.server:
                    initialized = mt5.initialize(path=mt5_path, login=self.login, password=self.password, server=self.server)

                # Try with credentials only
                if not initialized and self.login and self.password and self.server:
                    initialized = mt5.initialize(login=self.login, password=self.password, server=self.server)

                # Try with path only
                if not initialized and mt5_path:
                    initialized = mt5.initialize(path=mt5_path)

                # Default fallback
                if not initialized:
                    initialized = mt5.initialize()

                if initialized:
                    logger.info("MT5 initialized successfully")
                    return True
                else:
                    error_code = mt5.last_error()
                    logger.error(f"MT5 initialization failed on attempt {attempt + 1}/{self.max_retries}, "
                               f"error code = {error_code}")
                    
                    if error_code[0] == -6:  # Authorization failed
                        logger.error("Authorization failed (-6). Please verify:")
                        logger.error(f"1. Open MetaTrader 5 terminal application on your desktop")
                        logger.error(f"2. Log in manually in MT5 (File -> Login to Trade Account)")
                        logger.error(f"3. Verify login ({self.login}), server ({self.server}), and password in .env")
                    
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
            except Exception as e:
                logger.error(f"Unexpected error during MT5 initialization: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
        
        return False

    def _initialize_connection(self):
        """
        Initialize connection to MT5 with enhanced error handling
        """
        try:
            # First ensure MT5 is initialized
            if not self._ensure_mt5_initialized():
                logger.error("Failed to initialize MT5 after multiple attempts")
                self.connected = False
                return False
            
            # Connect to MT5 account with retry logic
            for attempt in range(self.max_retries):
                try:
                    authorized = mt5.login(self.login, password=self.password, server=self.server)
                    if authorized:
                        break
                    else:
                        error_code = mt5.last_error()
                        logger.error(f"Login failed on attempt {attempt + 1}/{self.max_retries}, "
                                   f"error code: {error_code}")
                        if attempt < self.max_retries - 1:
                            time.sleep(self.retry_delay)
                            continue
                        else:
                            logger.error("Failed to login after all attempts")
                            mt5.shutdown()
                            self.connected = False
                            return False
                except Exception as e:
                    logger.error(f"Login attempt {attempt + 1} failed with error: {str(e)}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
            
            # Verify account connection
            account_info = mt5.account_info()
            if account_info is None:
                logger.error(f"Failed to get account info, error code: {mt5.last_error()}")
                mt5.shutdown()
                self.connected = False
                return False
            
            # Log account info
            account_info_dict = account_info._asdict()
            logger.info(f"Connected to MT5 account #{account_info_dict['login']} on {account_info_dict['server']}")
            logger.info(f"Balance: {account_info_dict['balance']} {account_info_dict['currency']}")
            
            # Check and enable symbol with retry logic
            for attempt in range(self.max_retries):
                try:
                    symbol_info = mt5.symbol_info(self.symbol)
                    if symbol_info is None:
                        error_code = mt5.last_error()
                        logger.error(f"Symbol {self.symbol} not found, attempt {attempt + 1}/{self.max_retries}, "
                                   f"error code: {error_code}")
                        if attempt < self.max_retries - 1:
                            time.sleep(self.retry_delay)
                            continue
                        else:
                            mt5.shutdown()
                            self.connected = False
                            return False
                    
                    if not symbol_info.visible and not mt5.symbol_select(self.symbol, True):
                        error_code = mt5.last_error()
                        logger.error(f"Failed to select symbol {self.symbol}, attempt {attempt + 1}/{self.max_retries}, "
                                   f"error code: {error_code}")
                        if attempt < self.max_retries - 1:
                            time.sleep(self.retry_delay)
                            continue
                        else:
                            mt5.shutdown()
                            self.connected = False
                            return False
                    break
                except Exception as e:
                    logger.error(f"Symbol selection attempt {attempt + 1} failed with error: {str(e)}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
            
            self.connected = True
            logger.info(f"Successfully connected to MT5 and selected symbol {self.symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize connection to MT5: {str(e)}")
            if mt5.initialize():
                mt5.shutdown()
            self.connected = False
            return False

    def reconnect(self):
        """
        Attempt to reconnect to MT5
        """
        logger.info("Attempting to reconnect to MT5...")
        if mt5.initialize():
            mt5.shutdown()
        time.sleep(2)
        return self._initialize_connection()

    # Add auto-reconnect capability to all methods that require MT5 connection
    def _ensure_connected(self):
        """
        Ensure connection to MT5 is active, attempt reconnection if needed
        """
        if not self.connected or not mt5.initialize():
            logger.warning("MT5 connection lost, attempting to reconnect...")
            return self.reconnect()
        return True
    
    def get_minimum_distance(self):
        """
        Get adaptive minimum distance for SL/TP based on symbol type and current market conditions
        
        Returns:
            float: Minimum distance in symbol price units
        """
        try:
            # Get current spread for adaptive distance calculation
            current_price = self.get_current_price()
            spread = 0
            if current_price:
                spread = current_price['ask'] - current_price['bid']
            
            if 'XAU' in self.symbol or 'GOLD' in self.symbol.upper():
                # For gold: adaptive based on spread, minimum 0.2 points (more reasonable)
                base_distance = max(0.2, spread * 3)  # 3x spread or 0.2, whichever is higher
                return min(base_distance, 0.8)  # Cap at 0.8 to avoid being too restrictive
                
            elif 'BTC' in self.symbol:
                # For BTC: adaptive based on spread, minimum $30 (reduced from $100)
                base_distance = max(30.0, spread * 2)  # 2x spread or $30
                return min(base_distance, 150.0)  # Cap at $150 for reasonable scalping
                
            elif 'USD' in self.symbol and self.symbol.endswith('m'):
                # For forex: adaptive based on spread, minimum 0.5 pips (reduced from 1 pip)
                base_distance = max(0.0005, spread * 2)  # 2x spread or 0.5 pips
                return min(base_distance, 0.002)  # Cap at 2 pips for scalping
                
            elif any(oil in self.symbol.upper() for oil in ['OIL', 'CL', 'BRENT']):
                # For oil: minimum 0.05 points
                base_distance = max(0.05, spread * 2)
                return min(base_distance, 0.3)
                
            else:
                # Default adaptive minimum distance
                base_distance = max(0.001, spread * 2)
                return min(base_distance, 0.01)
                
        except Exception as e:
            logger.error(f"Error getting adaptive minimum distance: {e}")
            # Fallback to more lenient defaults
            if 'XAU' in self.symbol or 'GOLD' in self.symbol.upper():
                return 0.2
            elif 'BTC' in self.symbol:
                return 30.0
            elif 'USD' in self.symbol and self.symbol.endswith('m'):
                return 0.0005
            else:
                return 0.001
    
    def _get_spread_cost(self):
        """
        Get current spread cost and estimate trading costs
        
        Returns:
            dict: Contains spread, estimated_cost_per_lot
        """
        try:
            current_price = self.get_current_price()
            if not current_price:
                return {'spread': 0, 'estimated_cost_per_lot': 0}
            
            spread = current_price['ask'] - current_price['bid']
            
            # Estimate cost per lot based on symbol
            if 'BTC' in self.symbol:
                # For BTC, spread cost can be $20-50 per lot
                estimated_cost = spread * 0.5  # Conservative estimate
            elif 'XAU' in self.symbol or 'GOLD' in self.symbol.upper():
                # For gold, spread cost around $3-10 per lot  
                estimated_cost = spread * 0.1
            elif 'USD' in self.symbol and self.symbol.endswith('m'):
                # For forex, spread cost around $10-20 per lot
                estimated_cost = spread * 100000 * 0.1  # Convert pips to dollars
            else:
                estimated_cost = spread * 0.1
            
            return {
                'spread': spread,
                'estimated_cost_per_lot': estimated_cost
            }
        except Exception as e:
            logger.error(f"Error calculating spread cost: {e}")
            return {'spread': 0, 'estimated_cost_per_lot': 0}
    
    def get_account_balance(self):
        """
        Get account balance with connection check
        """
        if not self._ensure_connected():
            return None
            
        try:
            account_info = mt5.account_info()
            if account_info is None:
                logger.error(f"Failed to get account info, error code: {mt5.last_error()}")
                return None
            
            return account_info.balance
        except Exception as e:
            logger.error(f"Failed to fetch account balance: {str(e)}")
            return None

    def get_current_price(self):
        """
        Get current price with connection check
        """
        if not self._ensure_connected():
            return None
            
        try:
            symbol_info_tick = mt5.symbol_info_tick(self.symbol)
            if symbol_info_tick is None:
                logger.error(f"Failed to get symbol info tick, error code: {mt5.last_error()}")
                return None
            
            return {
                'bid': symbol_info_tick.bid,
                'ask': symbol_info_tick.ask,
                'last': symbol_info_tick.last
            }
        except Exception as e:
            logger.error(f"Failed to fetch current price: {str(e)}")
            return None

    def execute_trade(self, signal, entry_price, stop_loss, take_profit, position_size, signal_type):
        """
        Execute a trade based on the signal with pre-flight validation checks.
        """
        if not self._ensure_connected():
            return None

        try:
            # CRITICAL SAFETY CHECK: Validate position size before execution
            account_balance = self.get_account_balance()
            if account_balance is None:
                logger.error("Trade rejected: Cannot get account balance")
                return None
                
            # Additional safety checks for position size
            if position_size > 10.0:  # Never allow more than 10 lots
                logger.error(f"Trade rejected: Position size {position_size} exceeds safety limit of 10 lots")
                return None
                
            if position_size * entry_price > account_balance * 0.5:  # Never risk more than 50% of account
                logger.error(f"Trade rejected: Position value {position_size * entry_price:.2f} exceeds 50% of account balance {account_balance:.2f}")
                return None
            
            # Check for existing positions first
            positions = mt5.positions_get(symbol=self.symbol)
            if positions is not None and len(positions) > 0:
                logger.warning("Trade rejected: Already have an open position. Only one trade allowed at a time.")
                return None

            symbol_info = mt5.symbol_info(self.symbol)
            if not symbol_info:
                logger.error(f"Could not get symbol info for {self.symbol}")
                return None

            # --- 1. VALIDATION: Check Volume/Lot Size ---
            min_volume = symbol_info.volume_min
            max_volume = symbol_info.volume_max
            volume_step = symbol_info.volume_step
            
            if position_size < min_volume:
                logger.error(f"Trade Rejected: Position size {position_size} is less than minimum {min_volume}.")
                return None
            if position_size > max_volume:
                logger.error(f"Trade Rejected: Position size {position_size} is greater than maximum {max_volume}.")
                return None
            # Ensure the volume matches the step rule
            position_size = round(position_size / volume_step) * volume_step

            order_type = mt5.ORDER_TYPE_BUY if signal > 0 else mt5.ORDER_TYPE_SELL
            
            # --- 2. Get Current Prices ---
            current_price = self.get_current_price()
            if not current_price:
                logger.error("Cannot execute trade: Failed to get current market price")
                return None
            
            price = current_price['ask'] if order_type == mt5.ORDER_TYPE_BUY else current_price['bid']

            # --- 3. RECALCULATE SL/TP FOR SCALPING SIGNALS ---
            # For scalping signals, recalculate SL/TP based on current market price
            if 'scalp' in signal_type.lower():
                logger.info(f"Recalculating SL/TP for scalping signal at current market price: {price}")
                
                # Calculate original risk/reward from signal
                original_risk = abs(entry_price - stop_loss)
                original_reward = abs(take_profit - entry_price)
                
                # Use current market price as new entry
                if order_type == mt5.ORDER_TYPE_BUY:
                    stop_loss = price - original_risk
                    take_profit = price + original_reward
                elif order_type == mt5.ORDER_TYPE_SELL:
                    stop_loss = price + original_risk
                    take_profit = price - original_reward
                
                logger.info(f"Updated for scalping - Entry: {price}, SL: {stop_loss}, TP: {take_profit}")
                
                # Additional safety check for recalculated values
                if stop_loss <= 0 or take_profit <= 0:
                    logger.error(f"Invalid recalculated SL/TP values: SL={stop_loss}, TP={take_profit}")
                    return None
                
                # Apply minimum distance requirements for different symbols
                min_distance = self.get_minimum_distance()
                
                # Get spread costs for profit target adjustment
                spread_info = self._get_spread_cost()
                spread_cost = spread_info['estimated_cost_per_lot'] * position_size
                
                # For high-spread instruments like BTC, add extra buffer to TP
                if 'BTC' in self.symbol and spread_info['spread'] > 50:
                    logger.info(f"High spread detected ({spread_info['spread']:.2f}) - adding extra buffer to profit target")
                    min_distance = max(min_distance, spread_info['spread'] * 2)  # 2x spread minimum
                
                logger.info(f"Trading costs - Spread: {spread_info['spread']:.2f}, Est. cost: ${spread_cost:.2f}")
                
                # Check and enforce minimum distances
                if order_type == mt5.ORDER_TYPE_BUY:
                    sl_distance = price - stop_loss
                    tp_distance = take_profit - price
                    
                    if sl_distance < min_distance:
                        stop_loss = price - min_distance
                        logger.info(f"Adjusted SL for minimum distance: {stop_loss} (was too close by {min_distance - sl_distance:.5f})")
                    
                    if tp_distance < min_distance:
                        take_profit = price + min_distance
                        logger.info(f"Adjusted TP for minimum distance: {take_profit} (was too close by {min_distance - tp_distance:.5f})")
                        
                elif order_type == mt5.ORDER_TYPE_SELL:
                    sl_distance = stop_loss - price
                    tp_distance = price - take_profit
                    
                    if sl_distance < min_distance:
                        stop_loss = price + min_distance
                        logger.info(f"Adjusted SL for minimum distance: {stop_loss} (was too close by {min_distance - sl_distance:.5f})")
                    
                    if tp_distance < min_distance:
                        take_profit = price - min_distance
                        logger.info(f"Adjusted TP for minimum distance: {take_profit} (was too close by {min_distance - tp_distance:.5f})")
                
                logger.info(f"Final scalping trade - Entry: {price}, SL: {stop_loss}, TP: {take_profit}")

            # --- 4. VALIDATION: Check Stop Loss and Take Profit ---
            if order_type == mt5.ORDER_TYPE_BUY:
                if stop_loss >= price:
                    logger.error(f"Trade Rejected: For a BUY, Stop Loss ({stop_loss}) must be below the current Ask price ({price}).")
                    return None
                if take_profit <= price:
                    logger.error(f"Trade Rejected: For a BUY, Take Profit ({take_profit}) must be above the current Ask price ({price}).")
                    return None
            elif order_type == mt5.ORDER_TYPE_SELL:
                if stop_loss <= price:
                    logger.error(f"Trade Rejected: For a SELL, Stop Loss ({stop_loss}) must be above the current Bid price ({price}).")
                    return None
                if take_profit >= price:
                    logger.error(f"Trade Rejected: For a SELL, Take Profit ({take_profit}) must be below the current Bid price ({price}).")
                    return None

            # --- 5. Prepare and Send the Order ---
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": float(position_size),
                "type": order_type,
                "price": price,
                "sl": float(stop_loss),
                "tp": float(take_profit),
                "deviation": 20,
                "magic": 234000,
                "comment": f"Py{signal_type}"[:31],
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK, # Using FOK is often more reliable
            }
            
            # --- NEW: Improved Logging ---
            logger.info(f"Sending trade request: {request}")

            result = mt5.order_send(request)
            
            if result is None:
                logger.error(f"Failed to execute trade: order_send returned None, error code: {mt5.last_error()}")
                return None
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                # This is where your error 10019 is caught
                logger.error(f"Trade execution FAILED. Code: {result.retcode}, Comment: {result.comment}, Request: {request}")
                return None
             # Get order details
            order_id = result.order
            filled_price = result.price
            
            # Store trade information
            trade_info = {
                'id': order_id,
                'symbol': self.symbol,
                'side': 'buy' if signal > 0 else 'sell',
                'entry_price': filled_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'position_size': position_size,
                'signal_type': signal_type,
                'entry_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self.open_trades[order_id] = trade_info
            
            logger.info(f"Trade executed: {'BUY' if signal > 0 else 'SELL'} {self.symbol} at {filled_price}, SL: {stop_loss}, TP: {take_profit}, Size: {position_size}")
            
            return order_id
            
        except Exception as e:
            logger.error(f"Failed to execute trade: {str(e)}")
            return None
            
            
        except Exception as e:
            logger.error(f"An unexpected exception occurred in execute_trade: {e}", exc_info=True)
            return None
    # def execute_trade(self, signal, entry_price, stop_loss, take_profit, position_size, signal_type):
        """
        Execute a trade based on the signal
        
        Args:
            signal: Trade signal (1 for buy, -1 for sell)
            entry_price: Entry price for the trade
            stop_loss: Stop loss price for the trade
            take_profit: Take profit price for the trade
            position_size: Position size in lots
            signal_type: Type of signal that generated the trade
            
        Returns:
            Trade ID if successful, None otherwise
        """
        if not self.connected:
            if not self._initialize_connection():
                logger.error("Cannot execute trade: Not connected to MT5")
                return None
        
        try:
            # Determine order type
            order_type = mt5.ORDER_TYPE_BUY if signal > 0 else mt5.ORDER_TYPE_SELL

            # Always use the current market price for market orders
            current_price = self.get_current_price()
            if not current_price:
                logger.error("Cannot execute trade: Failed to get current price")
                return None
            price = current_price['ask'] if signal > 0 else current_price['bid']
            
            logger.info(f"signal_type:{signal_type}")
            # Prepare the request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": position_size,
                "type": order_type,
                "price": price,
                "sl": stop_loss,
                "tp": take_profit,
                "deviation": 10,  # Allowed price deviation in points
                "magic": 234000,  # Magic number to identify trades
                "comment": f"Py{signal_type}"[:31],  # Short ASCII comment, max 31 chars
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send the order
            result = mt5.order_send(request)
            if result is None:
                logger.error(f"Failed to execute trade: order_send returned None, error code: {mt5.last_error()}")
                return None
                
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Failed to execute trade: {result.retcode}, {result.comment}")
                return None
            
            # Get order details
            order_id = result.order
            filled_price = result.price
            
            # Store trade information
            trade_info = {
                'id': order_id,
                'symbol': self.symbol,
                'side': 'buy' if signal > 0 else 'sell',
                'entry_price': filled_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'position_size': position_size,
                'signal_type': signal_type,
                'entry_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self.open_trades[order_id] = trade_info
            
            logger.info(f"Trade executed: {'BUY' if signal > 0 else 'SELL'} {self.symbol} at {filled_price}, SL: {stop_loss}, TP: {take_profit}, Size: {position_size}")
            
            return order_id
            
        except Exception as e:
            logger.error(f"Failed to execute trade: {str(e)}")
            return None



    def update_trade_status_mt5(self):
        """
        Fetches all open positions from MT5 for the bot's symbol and updates
        the internal open_trades dictionary. This method completely rebuilds
        the state based on the terminal's data.

        Returns:
            dict: The updated dictionary of open trades, with position tickets as keys.
        """
        try:
            # 1. Fetch all open positions for the specific symbol
            positions = mt5.positions_get(symbol=self.symbol)
            
            # If positions_get returns None, it's an error. If it returns an empty
            # list, there are simply no open trades.
            if positions is None:
                # On error, we don't clear trades, as it might be a temporary network issue.
                # We log the error and return the last known state.
                last_error = mt5.last_error()
                logging.error(f"Failed to get positions, error code: {last_error}")
                return self.open_trades

            # Create a new dictionary to hold the current state.
            # This is safer than modifying the existing one in a loop.
            current_open_trades = {}

            for position in positions:
                # The position ticket is the unique ID for the trade.
                ticket = position.ticket
                
                # Convert position type from integer to a readable string.
                side = 'buy' if position.type == mt5.ORDER_TYPE_BUY else 'sell'
                
                # Populate the dictionary for this specific trade.
                current_open_trades[ticket] = {
                    'id': ticket,
                    'symbol': position.symbol,
                    'side': side,
                    'volume': position.volume,
                    'entry_price': position.price_open,
                    'current_price': position.price_current,
                    'unrealized_pnl': position.profit,
                    'stop_loss': position.sl,
                    'take_profit': position.tp,
                    'entry_time': datetime.fromtimestamp(position.time).strftime("%Y-%m-%d %H:%M:%S"),
                    'updated_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            
            # Atomically update the bot's state with the fresh data.
            self.open_trades = current_open_trades
            
            return self.open_trades

        except Exception as e:
            logging.error(f"An unexpected error occurred while updating trade status: {e}")
            # In case of an unexpected exception, return the last known state
            return self.open_trades
    def close_trade(self, position_id, position_size, signal_type):
        """
        Close a specific position
        
        Args:
            position_id: ID of the position to close
            
        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            if not self._initialize_connection():
                logger.error("Cannot close trade: Not connected to MT5")
                return False
        
        try:
            # Get position info
            positions = mt5.positions_get(ticket=position_id)
            if positions is None or len(positions) == 0:
                logger.error(f"Position ID {position_id} not found")
                return False
            
            position = positions[0]
            
            # Determine order type for closing (opposite of position type)
            close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(position.symbol)
            if not tick:
                logger.error(f"Failed to get tick data for {position.symbol}")
                return False
            price = tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask
            
            # Prepare the request - for closing a position, 'position' ticket must be specified and SL/TP must be 0.0
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": position_id,
                "symbol": position.symbol,
                "volume": float(position_size),
                "type": close_type,
                "price": price,
                "sl": 0.0,
                "tp": 0.0,
                "deviation": 20,
                "magic": 234000,
                "comment": f"PyClose_{signal_type}"[:31],
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send the order with IOC -> FOK fallback
            result = mt5.order_send(request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                request["type_filling"] = mt5.ORDER_FILLING_FOK
                result = mt5.order_send(request)
                
            if result is None:
                logger.error(f"Failed to close position: order_send returned None, error code: {mt5.last_error()}")
                return False
                
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Failed to close position: {result.retcode}, {result.comment}")
                return False
            
            # Remove from open trades
            if position_id in self.open_trades:
                del self.open_trades[position_id]
            
            logger.info(f"Position {position_id} closed at {result.price}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to close position: {str(e)}")
            return False
            
    def partial_close_trade(self, position_id, volume_to_close, reason="Partial TP"):
        """
        Partially close a position on MT5 (e.g. 50% lot booking)
        
        Args:
            position_id: ID/ticket of the position to partially close
            volume_to_close: Volume in lots to close (dynamically calculated)
            reason: Comment/reason for partial close
            
        Returns:
            dict with success (bool), closed_volume (float), remaining_volume (float), close_price (float)
        """
        if not self._ensure_connected():
            logger.error("Cannot partially close trade: Not connected to MT5")
            return {"success": False, "message": "Not connected to MT5"}
            
        try:
            positions = mt5.positions_get(ticket=position_id)
            if positions is None or len(positions) == 0:
                logger.error(f"Position ID {position_id} not found for partial close")
                return {"success": False, "message": "Position not found"}
                
            position = positions[0]
            current_volume = float(position.volume)
            symbol = position.symbol
            
            # Normalize volume to broker's volume step and min/max limits
            sym_info = mt5.symbol_info(symbol)
            vol_min = sym_info.volume_min if sym_info else 0.01
            vol_step = sym_info.volume_step if sym_info else 0.01
            
            # Round volume_to_close to step
            volume_to_close = round(round(float(volume_to_close) / vol_step) * vol_step, 2)
            
            if volume_to_close <= 0:
                logger.warning(f"Volume to close {volume_to_close} is <= 0")
                return {"success": False, "message": "Invalid volume"}
                
            if volume_to_close >= current_volume:
                logger.info(f"Volume to close ({volume_to_close}) >= current volume ({current_volume}). Performing full close.")
                success = self.close_trade(position_id, current_volume, reason)
                return {"success": success, "closed_volume": current_volume, "remaining_volume": 0.0}
                
            # Remaining volume check
            remaining_volume = round(current_volume - volume_to_close, 2)
            if remaining_volume < vol_min:
                logger.warning(f"Remaining volume {remaining_volume} < min volume {vol_min}. Closing full position instead.")
                success = self.close_trade(position_id, current_volume, reason)
                return {"success": success, "closed_volume": current_volume, "remaining_volume": 0.0}
                
            close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                logger.error(f"Failed to get tick for {symbol}")
                return {"success": False, "message": "No tick data"}
                
            price = tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(volume_to_close),
                "type": close_type,
                "position": position_id,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": f"PyPart_{reason}"[:31],
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            if result is None:
                err = mt5.last_error()
                logger.error(f"Partial close order_send returned None, error: {err}")
                return {"success": False, "message": str(err)}
                
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                # Retry with FOK if IOC failed
                if result.retcode in [10030, 10027, 10004]:
                    request["type_filling"] = mt5.ORDER_FILLING_FOK
                    result = mt5.order_send(request)
                    
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Successfully partially booked {volume_to_close} lots on position {position_id} at {result.price}. Remaining: {remaining_volume} lots.")
                if position_id in self.open_trades:
                    self.open_trades[position_id]['volume'] = remaining_volume
                    self.open_trades[position_id]['position_size'] = remaining_volume
                return {
                    "success": True,
                    "closed_volume": volume_to_close,
                    "remaining_volume": remaining_volume,
                    "close_price": result.price
                }
            else:
                ret_code = result.retcode if result else "None"
                ret_comment = result.comment if result else "None"
                logger.error(f"Partial close failed on position {position_id}: code {ret_code}, comment: {ret_comment}")
                return {"success": False, "message": f"Code {ret_code}: {ret_comment}"}
                
        except Exception as e:
            logger.error(f"Exception during partial close of {position_id}: {str(e)}")
            return {"success": False, "message": str(e)}
    
    def get_open_positions(self):
        """
        Get all open positions
        
        Returns:
            List of open positions
        """
        if not self.connected:
            if not self._initialize_connection():
                logger.error("Cannot get open positions: Not connected to MT5")
                return []
        
        try:
            positions = mt5.positions_get(symbol=self.symbol)
            if positions is None:
                err = mt5.last_error()
                if isinstance(err, tuple) and len(err) > 0 and err[0] == -10004:
                    self.connected = False
                    logger.warning("MT5 terminal IPC connection lost (-10004). Please ensure MetaTrader 5 application is open on your desktop.")
                else:
                    logger.error(f"Failed to get positions, error code: {err}")
                return []
            
            return [position._asdict() for position in positions]
            
        except Exception as e:
            logger.error(f"Failed to get open positions: {str(e)}")
            return []
    
    def modify_position(self, position_id, stop_loss=None, take_profit=None):
        """
        Modify stop loss and take profit for a position
        
        Args:
            position_id: ID of the position to modify
            stop_loss: New stop loss price
            take_profit: New take profit price
            
        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            if not self._initialize_connection():
                logger.error("Cannot modify position: Not connected to MT5")
                return False
        
        try:
            # Get position info
            positions = mt5.positions_get(ticket=position_id)
            if positions is None or len(positions) == 0:
                logger.error(f"Position ID {position_id} not found")
                return False
            
            position = positions[0]
            
            # Use current values if not specified
            if stop_loss is None:
                stop_loss = position.sl
            if take_profit is None:
                take_profit = position.tp
                
            # Check if there are actually any changes to make
            current_sl = position.sl
            current_tp = position.tp
            
            # Define a small tolerance for comparing floating point numbers (1 pip for most instruments)
            tolerance = 0.00001  # Adjust based on symbol if needed
            
            sl_changed = abs(float(stop_loss) - current_sl) > tolerance if stop_loss != 0 else (current_sl != 0)
            tp_changed = abs(float(take_profit) - current_tp) > tolerance if take_profit != 0 else (current_tp != 0)
            
            if not sl_changed and not tp_changed:
                logger.debug(f"No changes needed for position {position_id}: SL={stop_loss} (current: {current_sl}), TP={take_profit} (current: {current_tp})")
                return True  # Consider this successful since no change was needed
            
            # Get current market price for validation
            current_price_info = mt5.symbol_info_tick(position.symbol)
            if current_price_info is None:
                logger.error(f"Failed to get current price for {position.symbol}")
                return False
            
            # Use appropriate price for validation based on position type
            current_price = current_price_info.bid if position.type == 0 else current_price_info.ask  # 0 = BUY, 1 = SELL
            
            # Basic validation for SL/TP values
            if stop_loss is not None and stop_loss <= 0:
                logger.error(f"Invalid stop loss value: {stop_loss}")
                return False
            if take_profit is not None and take_profit <= 0:
                logger.error(f"Invalid take profit value: {take_profit}")
                return False
            
            # Prepare the request
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": position.symbol,
                "position": position_id,
                "sl": float(stop_loss) if stop_loss is not None else 0.0,
                "tp": float(take_profit) if take_profit is not None else 0.0
            }
            
            logger.debug(f"Modifying position {position_id}: SL={stop_loss} (was {current_sl}), TP={take_profit} (was {current_tp}), "
                        f"Current price={current_price}, Position type={position.type}")
            logger.debug(f"SL changed: {sl_changed}, TP changed: {tp_changed}")
            
            # Send the order
            result = mt5.order_send(request)
            if result is None:
                logger.error(f"Failed to modify position: order_send returned None, error code: {mt5.last_error()}")
                return False
                
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                # Handle "No changes" error as success
                if result.retcode == 10025:  # MT5 error code for "No changes"
                    logger.debug(f"Position {position_id} modification: No changes needed (MT5 code 10025)")
                    return True
                else:
                    logger.error(f"Failed to modify position: {result.retcode}, {result.comment}")
                    return False
            
            logger.info(f"Position {position_id} modified: SL={stop_loss}, TP={take_profit}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to modify position: {str(e)}")
            return False



    def fetch_historical_data_mt5(self, timeframe='1h', limit=100):
        """
        Fetches historical OHLCV data from the MetaTrader 5 terminal.

        Args:
            symbol (str): The symbol to fetch data for (e.g., "XAUUSDm", "EURUSD").
            timeframe (str): The timeframe for the data. 
                            Accepts strings like '1m', '5m', '15m', '1h', '4h', '1d'.
            limit (int): The number of candles to fetch.

        Returns:
            pd.DataFrame: A DataFrame with OHLCV data, indexed by timestamp, or None on failure.
        """
        # 1. Map string timeframes to MetaTrader 5 constants
        timeframe_mapping = {
            '1m': mt5.TIMEFRAME_M1,
            '5m': mt5.TIMEFRAME_M5,
            '15m': mt5.TIMEFRAME_M15,
            '30m': mt5.TIMEFRAME_M30,
            '1h': mt5.TIMEFRAME_H1,
            '4h': mt5.TIMEFRAME_H4,
            '1d': mt5.TIMEFRAME_D1,
            '1W': mt5.TIMEFRAME_W1,
            '1M': mt5.TIMEFRAME_MN1
        }
        
        mt5_timeframe = timeframe_mapping.get(timeframe)
        if mt5_timeframe is None:
            logging.error(f"Invalid timeframe provided: '{timeframe}'. Please use a valid string like '1h', '4h', etc.")
            return None

        try:
            # 2. Fetch rates from the current bar backwards
            rates = mt5.copy_rates_from_pos(self.symbol, mt5_timeframe, 0, limit)
            
            if rates is None or len(rates) == 0:
                logging.warning(f"No historical data returned for {self.symbol} on timeframe {timeframe}.")
                return None
                
            # 3. Convert the NumPy array returned by MT5 to a DataFrame
            df = pd.DataFrame(rates)
            
            # 4. Convert timestamp from seconds (MT5) to datetime objects
            df['timestamp'] = pd.to_datetime(df['time'], unit='s')
            
            # 5. Select and rename columns to match the original function's output
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'tick_volume']]
            df.rename(columns={'tick_volume': 'volume'}, inplace=True)
            
            # 6. Set the timestamp as the index
            df.set_index('timestamp', inplace=True)
            
            return df
                
        except Exception as e:
            logging.error(f"Failed to fetch historical data from MT5: {str(e)}")
            return None

    def shutdown(self):

        """
        Shutdown connection to MT5
        """
        if mt5.initialize():
            mt5.shutdown()
            self.connected = False
            logger.info("MT5 connection closed")