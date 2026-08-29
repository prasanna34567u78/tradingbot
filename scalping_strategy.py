# Advanced Scalping Strategy for Gold Trading Bot

import pandas as pd
import numpy as np
from indicators import SMCIndicators
import config
import logging
from datetime import datetime, time

logger = logging.getLogger('scalping_bot')


class ScalpingStrategy:
    """
    High-frequency scalping strategy optimized for quick 5-20 pip profits
    Focuses on 1m and 5m timeframes with rapid execution
    """
    
    def __init__(self, mt5_executor=None, risk_percent=0.5, tp_pips=8, sl_pips=4):
        # Scalping-specific parameters
        self.risk_percent = risk_percent  # Lower risk per trade for scalping
        self.tp_pips = tp_pips  # Quick profit target (5-20 pips)
        self.sl_pips = sl_pips  # Tight stop loss (3-8 pips)
        
        # Initialize indicators
        self.smc_indicators = SMCIndicators()
        
        # Trade management
        self.current_trade = None
        self.last_signal_time = None
        self.min_signal_interval = 30  # Minimum seconds between signals
        
        # Scalping settings
        self.max_spread = 3.0  # Maximum spread in pips for scalping
        self.min_atr_multiplier = 0.5  # Minimum ATR for volatility
        self.max_atr_multiplier = 3.0  # Maximum ATR to avoid high volatility
        
        # Quick trailing settings
        self.quick_breakeven_pips = 2  # Move to breakeven after 2 pips profit
        self.trailing_start_pips = 5   # Start trailing after 5 pips profit
        self.trailing_step_pips = 1    # Trail every 1 pip
        
        # Store MT5 executor reference
        self.mt5_executor = mt5_executor
        
        logger.info("Scalping strategy initialized - Target: 5-15 pips, Risk: 3-8 pips")
    
    def analyze_scalping_conditions(self, df):
        """
        Analyze if current market conditions are suitable for scalping
        """
        try:
            latest = df.iloc[-1]
            
            # Calculate current spread (simulated)
            spread = (latest['high'] - latest['low']) * 10000  # Convert to pips
            
            # Calculate volatility
            atr_14 = df['atr'].iloc[-1] if 'atr' in df.columns else None
            if atr_14 is None:
                atr_14 = df['high'].rolling(14).max() - df['low'].rolling(14).min()
                atr_14 = atr_14.iloc[-1]
            
            atr_pips = atr_14 * 10000  # Convert to pips
            
            # Check time of day (avoid low volatility periods)
            current_hour = datetime.now().hour
            is_active_session = (
                (7 <= current_hour <= 10) or   # London session
                (13 <= current_hour <= 16) or  # NY session overlap
                (20 <= current_hour <= 24)     # Asian session start
            )
            
            # Market condition assessment
            conditions = {
                'suitable_for_scalping': True,
                'spread_acceptable': spread <= self.max_spread,
                'volatility_good': self.min_atr_multiplier <= atr_pips <= self.max_atr_multiplier,
                'active_session': is_active_session,
                'current_spread': spread,
                'current_atr': atr_pips,
                'session_quality': 'high' if is_active_session else 'low'
            }
            
            # Overall suitability
            conditions['suitable_for_scalping'] = (
                conditions['spread_acceptable'] and 
                conditions['volatility_good'] and 
                conditions['active_session']
            )
            
            return conditions
            
        except Exception as e:
            logger.error(f"Error analyzing scalping conditions: {e}")
            return {'suitable_for_scalping': False}
    
    def apply_scalping_indicators(self, df):
        """Apply scalping-specific indicators"""
        df = df.copy()
        
        # Fast RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=7).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Fast Stochastic
        low_min = df['low'].rolling(window=5).min()
        high_max = df['high'].rolling(window=5).max()
        df['stoch_k'] = 100 * ((df['close'] - low_min) / (high_max - low_min))
        df['stoch_d'] = df['stoch_k'].rolling(window=3).mean()
        
        # Fast MACD
        ema_fast = df['close'].ewm(span=5).mean()
        ema_slow = df['close'].ewm(span=13).mean()
        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd'].ewm(span=4).mean()
        
        # Price velocity
        df['price_change'] = df['close'].diff()
        df['price_velocity'] = df['price_change'].rolling(window=3).mean()
        
        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(window=10).mean()
        bb_std = df['close'].rolling(window=10).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 1.5)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 1.5)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # ATR
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(window=7).mean()
        
        return df
    
    def generate_scalping_signals(self, df):
        """
        Generate high-frequency scalping signals
        """
        try:
            df = df.copy()
            
            # Initialize signal columns
            df['signal'] = 0
            df['entry_price'] = np.nan
            df['stop_loss'] = np.nan
            df['take_profit'] = np.nan
            df['signal_type'] = ''
            df['scalp_confidence'] = 0.0
            
            # Apply scalping indicators
            df = self.apply_scalping_indicators(df)
            df = self.smc_indicators.apply_all_indicators(df)
            
            # Check if conditions are suitable for scalping
            scalping_conditions = self.analyze_scalping_conditions(df)
            if not scalping_conditions['suitable_for_scalping']:
                logger.debug(f"Scalping conditions not suitable: {scalping_conditions}")
                return df
            
            # Only generate signals if no active trade
            if self.current_trade is not None:
                return df
            
            # Apply scalping strategies
            self._apply_momentum_scalping_strategy(df)
            self._apply_mean_reversion_scalping_strategy(df)
            self._apply_breakout_scalping_strategy(df)
            
            return df
            
        except Exception as e:
            logger.error(f"Error generating scalping signals: {e}")
            return df
    
    def _get_pip_multiplier(self, symbol="XAUUSDm"):
        s = str(symbol).upper()
        if 'XAU' in s or 'GOLD' in s:
            return 0.10  # 1 pip on Gold = $0.10
        elif 'BTC' in s:
            return 1.0   # 1 pip on BTC = $1.00
        elif 'JPY' in s:
            return 0.01
        return 0.0001    # Standard Forex pip

    def _apply_momentum_scalping_strategy(self, df, symbol="XAUUSDm"):
        """Apply momentum and CVD orderflow scalping strategy"""
        try:
            latest_idx = df.index[-1]
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            
            rsi = latest.get('rsi', 50)
            macd_signal = latest.get('macd_signal', 0)
            price_velocity = latest.get('price_velocity', 0)
            atr = latest.get('atr', 1.0)
            
            pip_mult = self._get_pip_multiplier(symbol)
            min_sl = 1.20 if ('XAU' in str(symbol).upper() or 'GOLD' in str(symbol).upper()) else (self.sl_pips * pip_mult)
            sl_dist = max(atr * 1.1, min_sl)
            tp_dist = sl_dist * 1.5
            
            # Bullish momentum scalp
            if (price_velocity > 0.3 and macd_signal > 0 and 
                40 < rsi < 75 and latest['close'] > prev['high']):
                
                entry_price = latest['close']
                stop_loss = entry_price - sl_dist
                take_profit = entry_price + tp_dist
                
                df.loc[latest_idx, 'signal'] = 1
                df.loc[latest_idx, 'entry_price'] = entry_price
                df.loc[latest_idx, 'stop_loss'] = stop_loss
                df.loc[latest_idx, 'take_profit'] = take_profit
                df.loc[latest_idx, 'signal_type'] = 'momentum_scalp_buy'
                df.loc[latest_idx, 'scalp_confidence'] = 0.82
                
                logger.info(f"[{symbol}] Momentum scalp BUY signal - Entry: {entry_price:.3f}, SL: {stop_loss:.3f}, TP: {take_profit:.3f}")
            
            # Bearish momentum scalp
            elif (price_velocity < -0.3 and macd_signal < 0 and 
                  25 < rsi < 60 and latest['close'] < prev['low']):
                
                entry_price = latest['close']
                stop_loss = entry_price + sl_dist
                take_profit = entry_price - tp_dist
                
                df.loc[latest_idx, 'signal'] = -1
                df.loc[latest_idx, 'entry_price'] = entry_price
                df.loc[latest_idx, 'stop_loss'] = stop_loss
                df.loc[latest_idx, 'take_profit'] = take_profit
                df.loc[latest_idx, 'signal_type'] = 'momentum_scalp_sell'
                df.loc[latest_idx, 'scalp_confidence'] = 0.82
                
                logger.info(f"[{symbol}] Momentum scalp SELL signal - Entry: {entry_price:.3f}, SL: {stop_loss:.3f}, TP: {take_profit:.3f}")
                
        except Exception as e:
            logger.error(f"Error in momentum scalping strategy: {e}")
    
    def _apply_mean_reversion_scalping_strategy(self, df, symbol="XAUUSDm"):
        """Apply orderflow absorption & mean reversion scalping strategy"""
        try:
            latest_idx = df.index[-1]
            latest = df.iloc[-1]
            
            rsi = latest.get('rsi', 50)
            stoch_k = latest.get('stoch_k', 50)
            bb_position = latest.get('bb_position', 0.5)
            atr = latest.get('atr', 1.0)
            
            pip_mult = self._get_pip_multiplier(symbol)
            min_sl = 1.20 if ('XAU' in str(symbol).upper() or 'GOLD' in str(symbol).upper()) else (self.sl_pips * pip_mult)
            sl_dist = max(atr * 1.1, min_sl)
            tp_dist = sl_dist * 1.5
            
            # Oversold bounce scalp
            if (rsi < 30 and stoch_k < 25 and bb_position < 0.15 and 
                latest['close'] > latest['low']):
                
                entry_price = latest['close']
                stop_loss = entry_price - sl_dist
                take_profit = entry_price + tp_dist
                
                df.loc[latest_idx, 'signal'] = 1
                df.loc[latest_idx, 'entry_price'] = entry_price
                df.loc[latest_idx, 'stop_loss'] = stop_loss
                df.loc[latest_idx, 'take_profit'] = take_profit
                df.loc[latest_idx, 'signal_type'] = 'mean_reversion_buy'
                df.loc[latest_idx, 'scalp_confidence'] = 0.75
            
            # Overbought drop scalp
            elif (rsi > 70 and stoch_k > 75 and bb_position > 0.85 and 
                  latest['close'] < latest['high']):
                
                entry_price = latest['close']
                stop_loss = entry_price + sl_dist
                take_profit = entry_price - tp_dist
                
                df.loc[latest_idx, 'signal'] = -1
                df.loc[latest_idx, 'entry_price'] = entry_price
                df.loc[latest_idx, 'stop_loss'] = stop_loss
                df.loc[latest_idx, 'take_profit'] = take_profit
                df.loc[latest_idx, 'signal_type'] = 'mean_reversion_sell'
                df.loc[latest_idx, 'scalp_confidence'] = 0.75
                
        except Exception as e:
            logger.error(f"Error in mean reversion scalping: {e}")
    
    def _apply_breakout_scalping_strategy(self, df):
        """Apply breakout scalping strategy"""
        try:
            latest_idx = df.index[-1]
            latest = df.iloc[-1]
            
            # Simple breakout detection
            recent_high = df['high'].rolling(window=5).max().iloc[-2]
            recent_low = df['low'].rolling(window=5).min().iloc[-2]
            
            # Bullish breakout scalp
            if latest['close'] > recent_high:
                entry_price = latest['close']
                stop_loss = entry_price - (self.sl_pips * 0.0001)
                take_profit = entry_price + (self.tp_pips * 0.0001)
                
                df.loc[latest_idx, 'signal'] = 1
                df.loc[latest_idx, 'entry_price'] = entry_price
                df.loc[latest_idx, 'stop_loss'] = stop_loss
                df.loc[latest_idx, 'take_profit'] = take_profit
                df.loc[latest_idx, 'signal_type'] = 'breakout_scalp_buy'
                df.loc[latest_idx, 'scalp_confidence'] = 0.75
            
            # Bearish breakdown scalp
            elif latest['close'] < recent_low:
                entry_price = latest['close']
                stop_loss = entry_price + (self.sl_pips * 0.0001)
                take_profit = entry_price - (self.tp_pips * 0.0001)
                
                df.loc[latest_idx, 'signal'] = -1
                df.loc[latest_idx, 'entry_price'] = entry_price
                df.loc[latest_idx, 'stop_loss'] = stop_loss
                df.loc[latest_idx, 'take_profit'] = take_profit
                df.loc[latest_idx, 'signal_type'] = 'breakout_scalp_sell'
                df.loc[latest_idx, 'scalp_confidence'] = 0.75
                
        except Exception as e:
            logger.error(f"Error in breakout scalping: {e}")
    
    def update_scalping_trade(self, df, current_price):
        """Update scalping trade with aggressive trailing and quick exits"""
        try:
            if not self.current_trade:
                return None
            
            trade_info = self.current_trade
            entry_price = trade_info['entry_price']
            side = trade_info['side']
            
            # Calculate current profit in pips
            if side == 'buy':
                profit_pips = (current_price['bid'] - entry_price) * 10000
                current_stop = trade_info.get('stop_loss', entry_price - 0.0004)
            else:
                profit_pips = (entry_price - current_price['ask']) * 10000
                current_stop = trade_info.get('stop_loss', entry_price + 0.0004)
            
            actions = {'stop_loss': None, 'take_profit': None, 'close_trade': False}
            
            # Quick breakeven
            if not trade_info.get('breakeven_set', False) and profit_pips >= self.quick_breakeven_pips:
                actions['stop_loss'] = entry_price
                trade_info['breakeven_set'] = True
                logger.info(f"Scalping trade moved to breakeven after {profit_pips:.1f} pips profit")
            
            # Start trailing
            elif profit_pips >= self.trailing_start_pips:
                if side == 'buy':
                    new_stop = current_price['bid'] - (self.trailing_step_pips * 0.0001)
                    if new_stop > current_stop:
                        actions['stop_loss'] = new_stop
                        logger.debug(f"Trailing stop updated: {new_stop:.5f}")
                else:
                    new_stop = current_price['ask'] + (self.trailing_step_pips * 0.0001)
                    if new_stop < current_stop:
                        actions['stop_loss'] = new_stop
                        logger.debug(f"Trailing stop updated: {new_stop:.5f}")
            
            # Quick exit on reversal signals
            if self._should_exit_scalp_early(df, side):
                actions['close_trade'] = True
                logger.info("Early exit triggered for scalping trade")
            
            return actions
            
        except Exception as e:
            logger.error(f"Error updating scalping trade: {e}")
            return None
    
    def _should_exit_scalp_early(self, df, side):
        """Check if we should exit scalping trade early due to reversal signals"""
        try:
            latest = df.iloc[-1]
            
            # Get momentum indicators
            rsi = latest.get('rsi', 50)
            macd_signal = latest.get('macd_signal', 0)
            price_velocity = latest.get('price_velocity', 0)
            
            # Exit long positions
            if side == 'buy':
                return (rsi > 70 and macd_signal < 0) or price_velocity < -0.3
            
            # Exit short positions
            else:
                return (rsi < 30 and macd_signal > 0) or price_velocity > 0.3
                
        except Exception as e:
            logger.error(f"Error checking early exit: {e}")
            return False
    
    def set_current_trade(self, trade_info):
        """Set current active trade"""
        self.current_trade = trade_info
        if trade_info:
            logger.info(f"Scalping trade set: {trade_info.get('side')} at {trade_info.get('entry_price')}")
    
    def calculate_scalping_position_size(self, account_balance, entry_price, stop_loss, max_risk_amount=None):
        """Calculate position size for scalping with smaller risk per trade"""
        try:
            if max_risk_amount is None:
                risk_amount = account_balance * (self.risk_percent / 100)
            else:
                risk_amount = min(max_risk_amount, account_balance * (self.risk_percent / 100))
            
            stop_distance = abs(entry_price - stop_loss)
            
            if stop_distance == 0:
                return 0.01  # Minimum lot size
            
            # Calculate position size
            position_size = risk_amount / (stop_distance * 100000)  # For gold
            
            # Round to appropriate lot size
            position_size = round(position_size, 2)
            
            # Ensure minimum and maximum limits
            min_lot = 0.01
            max_lot = min(1.0, account_balance / 10000)  # Conservative max for scalping
            
            position_size = max(min_lot, min(position_size, max_lot))
            
            logger.debug(f"Scalping position size calculated: {position_size} lots "
                        f"(Risk: {risk_amount:.2f}, Stop distance: {stop_distance:.5f})")
            
            return position_size
            
        except Exception as e:
            logger.error(f"Error calculating scalping position size: {e}")
            return 0.01 