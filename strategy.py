# Trading strategy implementation based on SMC/ICT concepts

import pandas as pd
import numpy as np
from indicators import SMCIndicators
import config
import logging
from ai_analyzer import AITradeAnalyzer
from pde_strategy import PDEStrategy

logger = logging.getLogger('gold_trading_bot')


class SMCStrategy:
    """
    Smart Money Concepts (SMC) and ICT trading strategy with single trade management
    """
    
    def __init__(self, mt5_executor=None, risk_percent=config.RISK_PERCENT, tp_ratio=config.TP_RATIO):
        self.risk_percent = risk_percent
        self.tp_ratio = tp_ratio
        self.indicators = SMCIndicators()
        # Enhanced single trade management with trailing
        self.current_trade = None
        self.trailing_activated = False
        self.initial_stop_distance = None
        self.initial_tp_distance = None
        self.last_trail_price = None
        self.breakeven_activated = False
        
        # Multi-symbol support
        self.symbol_trades = {}  # Track trades per symbol
        self.trailing_states = {}  # Track trailing states per symbol
        
        # Advanced trailing settings
        self.trailing_algorithm = config.TRAILING_SETTINGS.get('algorithm', 'enhanced_atr')
        self.atr_multiplier = config.TRAILING_SETTINGS.get('atr_multiplier', 2.0)
        self.min_trail_distance = config.TRAILING_SETTINGS.get('min_trail_distance', 0.001)
        self.use_swing_levels = config.TRAILING_SETTINGS.get('use_swing_levels', True)
        
        # Initialize AI analyzer with MT5 executor for historical data training
        self.ai_analyzer = AITradeAnalyzer(mt5_executor)
        
        # Store MT5 executor reference
        self.mt5_executor = mt5_executor

        # Initialize PDE strategy engine from config (v4 — proven profitable)
        pde_cfg = getattr(config, 'PDE_SETTINGS', {})
        self.pde_engine = PDEStrategy(
            swing_lookback       = pde_cfg.get('swing_lookback', 50),
            atr_period           = pde_cfg.get('atr_period', 14),
            sl_atr_mult          = pde_cfg.get('sl_atr_mult', 0.5),
            min_atr_pct          = pde_cfg.get('min_atr_pct', 0.0002),
            rsi_period           = pde_cfg.get('rsi_period', 14),
            rsi_buy_threshold    = pde_cfg.get('rsi_buy_threshold', 42.0),
            rsi_sell_threshold   = pde_cfg.get('rsi_sell_threshold', 58.0),
            max_zone_touches     = pde_cfg.get('max_zone_touches', 3),
            require_confirmation = pde_cfg.get('require_confirmation', True),
            volume_filter        = pde_cfg.get('volume_filter', True),
            min_rr               = pde_cfg.get('min_rr', 1.5),
            cooldown_bars        = pde_cfg.get('cooldown_bars', 48),
        )
    
    def analyze_market(self, df):
        """
        Analyze market data and apply SMC/ICT indicators
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with indicators applied
        """
        # Apply all indicators
        df = self.indicators.apply_all_indicators(df)
        
        # Add ATR for dynamic trailing stop
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(window=14).mean()
        
        return df
    
    def generate_signals(self, df):
        """
        Generate trading signals based on SMC/ICT concepts, only if no active trade
        
        Args:
            df: DataFrame with indicators applied
            
        Returns:
            DataFrame with signals added
        """
        df = df.copy()
        
        # Initialize signal columns
        df['signal'] = 0  # 0: no signal, 1: buy, -1: sell
        df['entry_price'] = np.nan
        df['stop_loss'] = np.nan
        df['take_profit'] = np.nan
        df['risk_reward'] = np.nan
        df['signal_type'] = ''
        df['ai_confidence'] = 0.0
        
        # Only generate signals if we don't have an active trade
        if self.current_trade is None:
            mode = getattr(config, 'STRATEGY_MODE', 'standard_ai')

            # ── PDE Strategy Mode ─────────────────────────────────
            if mode == 'pde' and getattr(config, 'PDE_SETTINGS', {}).get('enabled', False):
                df = self.pde_engine.generate_signals(df)
                # Map PDE columns → standard bot columns expected downstream
                if 'sl' in df.columns:
                    df['stop_loss']  = df['sl']
                if 'tp2' in df.columns:
                    df['take_profit'] = df['tp2']   # main TP target
                if 'tp1' in df.columns:
                    df['take_profit_1'] = df['tp1'] # partial TP
                latest = df.iloc[-1]
                if latest['signal'] != 0:
                    logger.info(
                        f"[PDE] Signal={latest['signal']:+d}  Zone={latest.get('pde_zone','')}  "
                        f"Entry={latest['entry_price']:.3f}  "
                        f"SL={latest['stop_loss']:.3f}  "
                        f"TP1={latest.get('tp1',float('nan')):.3f}  "
                        f"TP2={latest['take_profit']:.3f}  "
                        f"RR_TP2={latest.get('rr_tp2',0):.2f}"
                    )

            else:
                # ── Classic SMC/ICT Strategies ────────────────────
                # Strategy 1: Liquidity Sweep + Break of Structure (BOS)
                self._apply_liquidity_sweep_bos_strategy(df)
                
                # Strategy 2: Return to Order Block or Fair Value Gap
                self._apply_ob_fvg_return_strategy(df)
                
                # AI Validation
                latest = df.iloc[-1]
                if latest['signal'] != 0:
                    logger.info(f"Generated signal: {latest['signal']}, Entry: {latest['entry_price']}, "
                                f"SL: {latest['stop_loss']}, TP: {latest['take_profit']}")
                if latest['signal'] != 0:
                    if mode == 'mcp_enhanced':
                        validation = self.ai_analyzer.mcp_validate_trade(df, latest['signal'])
                    else:
                        validation = self.ai_analyzer.enhanced_validate_trade(df, latest['signal'])
                    
                    logger.info(f"AI validation result [{mode}]: {validation}")
                    if not validation['valid']:
                        df.loc[df.index[-1], 'signal'] = 0
                        logger.info(f"AI rejected trade signal ({mode}): {validation.get('reasons', validation.get('confidence'))}")
                    else:
                        df.loc[df.index[-1], 'ai_confidence'] = validation['confidence']
                        if validation['market_conditions']['volatility_state'] == 'high':
                            risk = abs(latest['entry_price'] - latest['stop_loss'])
                            new_tp = latest['entry_price'] + (risk * self.tp_ratio * 0.8) if latest['signal'] > 0 else \
                                    latest['entry_price'] - (risk * self.tp_ratio * 0.8)
                            df.loc[df.index[-1], 'take_profit'] = new_tp
                        logger.info(f"AI validated trade with {validation['confidence']:.2f} confidence")
                        logger.info(f"Market conditions: {validation['market_conditions']}")
        
        return df
    
    def generate_signals_with_confluence(self, df, confluence, mtf_analysis=None):
        """
        Generate trading signals enhanced with multi-timeframe confluence
        
        Args:
            df: DataFrame with indicators applied
            confluence: Multi-timeframe confluence analysis
            mtf_analysis: Multi-timeframe analysis data for OpenAI integration
            
        Returns:  
            DataFrame with enhanced signals
        """
        # Start with regular signal generation
        df = self.generate_signals(df)
        
        logger.info(f"Confluence analysis - Signal: {confluence['signal']}, "
                   f"Confidence: {confluence['confidence']:.2f}, "
                   f"Bullish votes: {confluence['bullish_votes']}, "
                   f"Bearish votes: {confluence['bearish_votes']}")
        
        # Enhance signals with confluence
        if confluence['signal'] != 0:
            latest_idx = df.index[-1]
            
            # CRITICAL: Check if we have valid market data before creating confluence signals
            current_price = df.loc[latest_idx, 'close']
            atr = df.loc[latest_idx, 'atr'] if 'atr' in df.columns else None
            
            # Validate that we have proper market data
            if pd.isna(current_price) or pd.isna(atr) or atr is None or atr <= 0:
                logger.warning("Invalid market data - skipping confluence signal creation")
                logger.warning(f"Current price: {current_price}, ATR: {atr}")
                return df
            
            # Additional validation: Check if basic indicators are working
            latest = df.iloc[-1]
            
            # Check if we have essential indicator columns
            required_indicators = ['bos_bullish', 'bos_bearish', 'bullish_ob', 'bearish_ob']
            missing_indicators = [ind for ind in required_indicators if ind not in df.columns]
            
            if missing_indicators:
                logger.warning(f"Missing essential indicators: {missing_indicators} - skipping confluence signal")
                return df
            logger.info(f"Latest indicators - BOS Bullish: {latest}")
            # Check if we have valid indicator values (not all NaN)
            has_valid_structure = any([
                not pd.isna(latest.get(ind, np.nan)) and latest.get(ind, False) 
                for ind in required_indicators
            ])
            
            logger.info(f"Valid market structure detected: {has_valid_structure}")
            if not has_valid_structure:
                logger.warning("No valid market structure detected - skipping confluence signal")
                logger.warning(f"Indicator values: BOS Bull: {latest.get('bos_bullish')}, "
                             f"BOS Bear: {latest.get('bos_bearish')}, "
                             f"Bull OB: {latest.get('bullish_ob')}, "
                             f"Bear OB: {latest.get('bearish_ob')}")
                return df
            
            # Only proceed if we have confluence signal AND valid market conditions
            if confluence['confidence'] > 0.6:
                # Adjust signal based on confluence
                if confluence['signal'] == 1 and df.loc[latest_idx, 'signal'] != -1:
                    df.loc[latest_idx, 'signal'] = 1
                    df.loc[latest_idx, 'signal_type'] = 'mtf_confluence_bullish'
                    df.loc[latest_idx, 'ai_confidence'] = confluence['confidence']
                    
                    # Calculate entry levels (using already validated data)
                    entry_price = current_price
                    atr_risk = atr * 2.0  # Use 2x ATR for stop loss
                    stop_loss = entry_price - atr_risk
                    take_profit = entry_price + (atr_risk * self.tp_ratio)
                    
                    df.loc[latest_idx, 'entry_price'] = entry_price
                    df.loc[latest_idx, 'stop_loss'] = stop_loss
                    df.loc[latest_idx, 'take_profit'] = take_profit
                    df.loc[latest_idx, 'risk_reward'] = self.tp_ratio
                    
                    logger.info(f"Multi-timeframe bullish confluence signal created - Entry: {entry_price:.5f}, "
                              f"SL: {stop_loss:.5f}, TP: {take_profit:.5f}")
                
                elif confluence['signal'] == -1 and df.loc[latest_idx, 'signal'] != 1:
                    df.loc[latest_idx, 'signal'] = -1
                    df.loc[latest_idx, 'signal_type'] = 'mtf_confluence_bearish'
                    df.loc[latest_idx, 'ai_confidence'] = confluence['confidence']
                    
                    # Calculate entry levels for bearish signal
                    entry_price = current_price
                    atr_risk = atr * 2.0
                    stop_loss = entry_price + atr_risk
                    take_profit = entry_price - (atr_risk * self.tp_ratio)
                    
                    df.loc[latest_idx, 'entry_price'] = entry_price
                    df.loc[latest_idx, 'stop_loss'] = stop_loss
                    df.loc[latest_idx, 'take_profit'] = take_profit
                    df.loc[latest_idx, 'risk_reward'] = self.tp_ratio
                    
                    logger.info(f"Multi-timeframe bearish confluence signal created - Entry: {entry_price:.5f}, "
                              f"SL: {stop_loss:.5f}, TP: {take_profit:.5f}")
        
        return df
    
    def generate_scalping_signals_with_confluence(self, df, confluence, mtf_analysis=None,symbol='XAUUSDm'):
        """
        Generate scalping signals enhanced with multi-timeframe confluence
        Optimized for 1m and 5m timeframes with quick profit targets
        
        Args:
            df: DataFrame with indicators applied (1m data)
            confluence: Multi-timeframe confluence analysis
            mtf_analysis: Multi-timeframe analysis data
            
        Returns:  
            DataFrame with enhanced scalping signals
        """
        # Start with regular signal generation but with scalping parameters
        df = self.generate_signals(df)
        
        logger.info(f"Scalping confluence - Signal: {confluence['signal']}, "
                   f"Confidence: {confluence['confidence']:.2f}")
        
        # Enhance signals with scalping confluence (more aggressive)
        if confluence['signal'] != 0:
            latest_idx = df.index[-1]
            
            # Get market data for scalping
            current_price = df.loc[latest_idx, 'close']
            atr = df.loc[latest_idx, 'atr'] if 'atr' in df.columns else None
            
            # Validate data
            if pd.isna(current_price) or pd.isna(atr) or atr is None or atr <= 0:
                logger.warning("Invalid market data for scalping - skipping signal")
                return df
            
                    # Lower confidence threshold for scalping (more aggressive)
        if confluence['confidence'] > 0.3:
                # Determine symbol type and set appropriate pip targets
                symbol = symbol
                
                if 'BTC' in symbol:
                    # Bitcoin needs much larger distances (account for high spreads)
                    pip_value = 1.0      # $1 movements for BTC
                    target_pips = 200    # $200 target (improved 1:2.67 ratio)
                    stop_pips = 75       # $75 stop (keeps risk manageable)
                elif 'USD' in symbol and symbol.endswith('m'):
                    # Forex pairs
                    pip_value = 0.0001   # Standard pip size
                    target_pips = 20     # 20 pip target (improved 1:2.5 ratio)
                    stop_pips = 8        # 8 pip stop
                elif 'XAU' in symbol or 'GOLD' in symbol.upper():
                    # Gold
                    pip_value = 0.01     # $0.01 movements
                    target_pips = 20     # $0.20 target (improved 1:2.5 ratio)
                    stop_pips = 8        # $0.08 stop
                else:
                    # Default/conservative
                    pip_value = 0.0001
                    target_pips = 8
                    stop_pips = 4       # Tight 4 pip stop
                
                if confluence['signal'] == 1:
                    df.loc[latest_idx, 'signal'] = 1
                    df.loc[latest_idx, 'signal_type'] = 'scalp_bullish'
                    df.loc[latest_idx, 'ai_confidence'] = confluence['confidence']
                    
                    # Scalping entry levels
                    entry_price = current_price
                    stop_loss = entry_price - (stop_pips * pip_value)
                    take_profit = entry_price + (target_pips * pip_value)
                    
                    # Validate all values are valid numbers
                    if all(not pd.isna(val) and val > 0 for val in [entry_price, stop_loss, take_profit]):
                        df.loc[latest_idx, 'entry_price'] = entry_price
                        df.loc[latest_idx, 'stop_loss'] = stop_loss
                        df.loc[latest_idx, 'take_profit'] = take_profit
                        df.loc[latest_idx, 'risk_reward'] = target_pips / stop_pips
                    else:
                        logger.error(f"Invalid signal values: Entry={entry_price}, SL={stop_loss}, TP={take_profit}")
                        df.loc[latest_idx, 'signal'] = 0  # Cancel signal
                    
                    # Dynamic logging based on symbol type
                    if 'BTC' in symbol:
                        logger.info(f"Scalping BUY signal - Entry: {entry_price:.2f}, "
                                  f"Target: +${target_pips}, Risk: -${stop_pips}")
                    else:
                        logger.info(f"Scalping BUY signal - Entry: {entry_price:.5f}, "
                                  f"Target: +{target_pips} pips, Risk: -{stop_pips} pips")
                
                elif confluence['signal'] == -1:
                    df.loc[latest_idx, 'signal'] = -1
                    df.loc[latest_idx, 'signal_type'] = 'scalp_bearish'
                    df.loc[latest_idx, 'ai_confidence'] = confluence['confidence']
                    
                    # Scalping entry levels for sell
                    entry_price = current_price
                    stop_loss = entry_price + (stop_pips * pip_value)
                    take_profit = entry_price - (target_pips * pip_value)
                    
                    # Validate all values are valid numbers
                    if all(not pd.isna(val) and val > 0 for val in [entry_price, stop_loss, take_profit]):
                        df.loc[latest_idx, 'entry_price'] = entry_price
                        df.loc[latest_idx, 'stop_loss'] = stop_loss
                        df.loc[latest_idx, 'take_profit'] = take_profit
                        df.loc[latest_idx, 'risk_reward'] = target_pips / stop_pips
                    else:
                        logger.error(f"Invalid signal values: Entry={entry_price}, SL={stop_loss}, TP={take_profit}")
                        df.loc[latest_idx, 'signal'] = 0  # Cancel signal
                    
                    # Dynamic logging based on symbol type
                    if 'BTC' in symbol:
                        logger.info(f"Scalping SELL signal - Entry: {entry_price:.2f}, "
                                  f"Target: +${target_pips}, Risk: -${stop_pips}")
                    else:
                        logger.info(f"Scalping SELL signal - Entry: {entry_price:.5f}, "
                                  f"Target: +{target_pips} pips, Risk: -{stop_pips} pips")
        
        return df
    
    def _get_breakeven_buffer(self, symbol, atr):
        """
        Get adaptive, symbol-aware breakeven buffer to ensure SL is locked into profit beyond spread
        """
        if 'BTC' in symbol.upper():
            return max(10.0, atr * 0.1 if atr else 10.0)
        elif 'XAU' in symbol.upper() or 'GOLD' in symbol.upper():
            return max(0.25, atr * 0.1 if atr else 0.25)
        elif 'OIL' in symbol.upper() or 'USOIL' in symbol.upper():
            return max(0.05, atr * 0.1 if atr else 0.05)
        elif 'USD' in symbol.upper() and symbol.endswith('m'):
            return max(0.0001, atr * 0.1 if atr else 0.0001)  # 1 pip
        else:
            return max(0.001, atr * 0.1 if atr else 0.001)

    def set_current_trade(self, trade_info):
        """
        Set or update the active trade state without losing trailing / breakeven memory across polling ticks
        """
        if trade_info:
            current_id = trade_info.get('id')
            prev_id = self.current_trade.get('id') if self.current_trade else None
            
            if prev_id == current_id and self.current_trade is not None:
                # Same active trade — update dynamic fields only, preserve memory!
                self.current_trade.update(trade_info)
            else:
                # Brand new trade detected — initialize fresh tracking
                self.current_trade = dict(trade_info)
                self.trailing_activated = False
                self.breakeven_activated = False
                self.partial_booked = False
                self.initial_stop_distance = abs(trade_info['entry_price'] - trade_info['stop_loss'])
                self.initial_tp_distance = abs(trade_info['entry_price'] - trade_info['take_profit'])
                self.last_trail_price = trade_info.get('stop_loss', trade_info['entry_price'])
                logger.info(f"Initialized active trade tracking for ID {current_id} ({trade_info.get('symbol')}): "
                            f"Entry={trade_info['entry_price']}, SL_Dist={self.initial_stop_distance:.5f}, TP_Dist={self.initial_tp_distance:.5f}")
        else:
            self.current_trade = None
            self.trailing_activated = False
            self.initial_stop_distance = None
            self.initial_tp_distance = None
            self.last_trail_price = None
            self.breakeven_activated = False
            self.partial_booked = False

    def update_trailing_stop(self, df, current_price):
        """
        Enhanced trailing stop with dynamic partial profit booking (e.g. 50% lot) and take profit trailing
        """
        if not self.current_trade:
            return {'stop_loss': None, 'take_profit': None, 'partial_close': False}
        
        try:
            side = self.current_trade['side']
            entry_price = self.current_trade['entry_price']
            current_stop = self.current_trade['stop_loss']
            current_tp = self.current_trade['take_profit']
            symbol = self.current_trade.get('symbol', 'XAUUSDm')
            
            # Get symbol-specific trailing settings
            symbol_config = config.SYMBOLS.get(symbol, {})
            trailing_config = symbol_config.get('trailing_settings', {})
            
            atr = df['atr'].iloc[-1] if 'atr' in df.columns else None
            if atr is None or atr <= 0:
                logger.warning(f"[{symbol}] Invalid ATR value for trailing calculation")
                return {'stop_loss': None, 'take_profit': None, 'partial_close': False}
            
            # Calculate profit in price distance, % of TP distance, and R-multiple
            if side == 'buy':
                profit = current_price - entry_price
            else:
                profit = entry_price - current_price
                
            tp_dist = self.initial_tp_distance if (self.initial_tp_distance and self.initial_tp_distance > 0) else abs(current_tp - entry_price)
            sl_dist = self.initial_stop_distance if (self.initial_stop_distance and self.initial_stop_distance > 0) else abs(entry_price - current_stop)
            
            profit_tp_pct = (profit / tp_dist) if (tp_dist and tp_dist > 0) else 0.0
            profit_r = (profit / sl_dist) if (sl_dist and sl_dist > 0) else 0.0
            
            # Read dynamic UI parameters
            breakeven_ratio = float(trailing_config.get('breakeven_ratio', 0.5))
            start_ratio = float(trailing_config.get('start_ratio', 0.8))
            trail_step = float(trailing_config.get('trail_step', 0.3))
            trail_sl = bool(trailing_config.get('trail_sl', True))
            trail_tp = bool(trailing_config.get('trail_tp', True))
            enable_breakeven = bool(trailing_config.get('enable_breakeven', True))
            enable_partial_booking = bool(trailing_config.get('enable_partial_booking', True))
            full_close_on_be = bool(trailing_config.get('full_close_on_be', False))
            partial_close_pct = float(trailing_config.get('partial_close_pct', 50.0))
            
            result = {
                'stop_loss': None,
                'take_profit': None,
                'partial_close': False,
                'partial_close_pct': partial_close_pct
            }
            
            # 1. Breakeven Logic (Controlled by enable_breakeven toggle)
            if enable_breakeven and not self.breakeven_activated and profit_tp_pct >= breakeven_ratio:
                be_buffer = self._get_breakeven_buffer(symbol, atr)
                be_stop = entry_price + be_buffer if side == 'buy' else entry_price - be_buffer
                
                # Check that BE stop is valid relative to current market price
                valid_be = (be_stop < current_price) if side == 'buy' else (be_stop > current_price)
                if valid_be:
                    result['stop_loss'] = be_stop
                    self.breakeven_activated = True
                    self.last_trail_price = be_stop
                    logger.info(f"[{symbol}] Moving SL to Breakeven at {be_stop:.5f} (+{be_buffer:.4f} buffer, Profit: {profit_tp_pct*100:.1f}% of TP, {profit_r:.2f}R)")

            # 2. Dynamic Partial / 100% Full Close Booking Logic (Triggered at breakeven_ratio)
            if not getattr(self, 'partial_booked', False) and profit_tp_pct >= breakeven_ratio:
                if full_close_on_be:
                    result['partial_close'] = True
                    result['partial_close_pct'] = 100.0
                    self.partial_booked = True
                    logger.info(f"[{symbol}] 🎯 FULL CLOSE Triggered at Breakeven/Target Ratio ({profit_tp_pct*100:.1f}% of TP). Booking 100% full trade.")
                elif enable_partial_booking and partial_close_pct > 0:
                    result['partial_close'] = True
                    result['partial_close_pct'] = partial_close_pct
                    self.partial_booked = True
                    logger.info(f"[{symbol}] 🎯 Dynamic Partial Booking Triggered ({profit_tp_pct*100:.1f}% of TP). Booking {partial_close_pct}% lot.")
            
            # 3. Trailing Stop Loss Logic (Controlled by trail_sl checkbox & start_ratio)
            if trail_sl and profit_tp_pct >= start_ratio:
                self.trailing_activated = True
                new_stop = self._calculate_trailing_stop(df, current_price, current_stop, atr, side)
                if new_stop:
                    # Enforce trail step buffer so stop steps forward cleanly
                    step_distance = max(trail_step * atr, self.min_trail_distance)
                    is_advancing = (new_stop >= (current_stop + step_distance)) if side == 'buy' else (new_stop <= (current_stop - step_distance))
                    if is_advancing:
                        result['stop_loss'] = new_stop
                        self.last_trail_price = new_stop
                        logger.info(f"[{symbol}] Trailing SL Advanced to {new_stop:.5f} (Profit: {profit_tp_pct*100:.1f}% of TP, Trail Step: {trail_step}x ATR)")
            
            # 3. Trailing Take Profit Logic (Controlled by trail_tp checkbox & start_ratio)
            if trail_tp and profit_tp_pct >= start_ratio:
                new_tp = self._calculate_trailing_take_profit(df, current_price, current_tp, atr, side)
                if new_tp and new_tp != current_tp:
                    result['take_profit'] = new_tp
                    logger.info(f"[{symbol}] Trailing TP Extended to {new_tp:.5f} to capture runner move")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in trailing calculation: {str(e)}")
            return {'stop_loss': None, 'take_profit': None, 'partial_close': False}
    
    def _calculate_trailing_stop(self, df, current_price, current_stop, atr, side):
        """
        Calculate new trailing stop using selected algorithm
        """
        try:
            if self.trailing_algorithm == 'simple':
                return self._simple_trailing(current_price, current_stop, atr, side)
            elif self.trailing_algorithm == 'atr':
                return self._atr_trailing(current_price, current_stop, atr, side)
            elif self.trailing_algorithm == 'enhanced_atr':
                return self._enhanced_atr_trailing(df, current_price, current_stop, atr, side)
            elif self.trailing_algorithm == 'parabolic':
                return self._parabolic_trailing(df, current_price, current_stop, side)
            else:
                return self._enhanced_atr_trailing(df, current_price, current_stop, atr, side)
        except Exception as e:
            logger.error(f"Error in trailing stop calculation: {str(e)}")
            return None
    
    def _enhanced_atr_trailing(self, df, current_price, current_stop, atr, side):
        """
        Enhanced ATR-based trailing with volatility adjustment and swing levels
        """
        try:
            # Base trailing distance
            trail_distance = atr * self.atr_multiplier
            
            # Volatility adjustment
            recent_atr = df['atr'].rolling(5).mean().iloc[-1] if len(df) >= 5 else atr
            avg_atr = df['atr'].rolling(20).mean().iloc[-1] if len(df) >= 20 else atr
            
            if recent_atr > 0 and avg_atr > 0:
                volatility_ratio = recent_atr / avg_atr
                if volatility_ratio > 1.3:  # High volatility
                    trail_distance *= 1.2
                elif volatility_ratio < 0.8:  # Low volatility
                    trail_distance *= 0.8
            
            # Swing level adjustment if enabled
            if self.use_swing_levels:
                swing_level = self._find_swing_level(df, current_price, side)
                if swing_level:
                    if side == 'buy':
                        trail_distance = max(trail_distance, current_price - swing_level)
                    else:
                        trail_distance = max(trail_distance, swing_level - current_price)
            
            # Calculate new stop
            if side == 'buy':
                new_stop = current_price - trail_distance
                # Only update if new stop is higher
                if new_stop > current_stop and new_stop > (self.last_trail_price or 0):
                    self.last_trail_price = new_stop
                    return max(new_stop, current_stop + self.min_trail_distance)
            else:
                new_stop = current_price + trail_distance
                # Only update if new stop is lower
                if new_stop < current_stop and new_stop < (self.last_trail_price or float('inf')):
                    self.last_trail_price = new_stop
                    return min(new_stop, current_stop - self.min_trail_distance)
            
            return None
            
        except Exception as e:
            logger.error(f"Error in enhanced ATR trailing: {str(e)}")
            return None
    
    def _simple_trailing(self, current_price, current_stop, atr, side):
        """
        Simple ATR-based trailing stop
        """
        try:
            trail_distance = atr * 1.5  # Fixed multiplier for simple trailing
            
            if side == 'buy':
                new_stop = current_price - trail_distance
                if new_stop > current_stop:
                    return new_stop
            else:
                new_stop = current_price + trail_distance
                if new_stop < current_stop:
                    return new_stop
            
            return None
        except Exception as e:
            logger.error(f"Error in simple trailing: {str(e)}")
            return None
    
    def _atr_trailing(self, current_price, current_stop, atr, side):
        """
        Standard ATR-based trailing stop
        """
        try:
            trail_distance = atr * self.atr_multiplier
            
            if side == 'buy':
                new_stop = current_price - trail_distance
                if new_stop > current_stop:
                    return new_stop
            else:
                new_stop = current_price + trail_distance
                if new_stop < current_stop:
                    return new_stop
            
            return None
        except Exception as e:
            logger.error(f"Error in ATR trailing: {str(e)}")
            return None
    
    def _parabolic_trailing(self, df, current_price, current_stop, side):
        """
        Parabolic SAR-based trailing stop
        """
        try:
            # Simple parabolic SAR calculation
            acceleration = 0.02
            max_acceleration = 0.2
            
            # This is a simplified version - full implementation would track SAR state
            if side == 'buy':
                # Use recent low as reference
                recent_low = df['low'].rolling(5).min().iloc[-1]
                new_stop = recent_low
                if new_stop > current_stop:
                    return new_stop
            else:
                # Use recent high as reference
                recent_high = df['high'].rolling(5).max().iloc[-1]
                new_stop = recent_high
                if new_stop < current_stop:
                    return new_stop
            
            return None
        except Exception as e:
            logger.error(f"Error in parabolic trailing: {str(e)}")
            return None
    
    def _find_swing_level(self, df, current_price, side, lookback=10):
        """
        Find recent swing high/low for better trailing levels
        """
        try:
            if len(df) < lookback + 2:
                return None
            
            recent_data = df.iloc[-lookback:]
            
            if side == 'buy':
                # Find recent swing low
                lows = recent_data['low']
                min_idx = lows.idxmin()
                swing_low = lows.loc[min_idx]
                
                # Validate swing low (should be below current price)
                if swing_low < current_price * 0.99:  # At least 1% below
                    return swing_low
            else:
                # Find recent swing high
                highs = recent_data['high']
                max_idx = highs.idxmax()
                swing_high = highs.loc[max_idx]
                
                # Validate swing high (should be above current price)
                if swing_high > current_price * 1.01:  # At least 1% above
                    return swing_high
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding swing level: {str(e)}")
            return None
    
    def _calculate_trailing_take_profit(self, df, current_price, current_tp, atr, side):
        """
        Calculate trailing take profit to capture extended moves
        """
        try:
            # Use smaller multiplier for TP trailing
            trail_distance = atr * (self.atr_multiplier * 0.6)
            
            if side == 'buy':
                new_tp = current_price + trail_distance
                # Only update if new TP is higher and price has moved significantly
                if new_tp > current_tp and current_price > (current_tp - trail_distance * 0.5):
                    return new_tp
            else:
                new_tp = current_price - trail_distance
                # Only update if new TP is lower and price has moved significantly
                if new_tp < current_tp and current_price < (current_tp + trail_distance * 0.5):
                    return new_tp
            
            return None
            
        except Exception as e:
            logger.error(f"Error in trailing take profit: {str(e)}")
            return None

    def should_exit_trade(self, df):
        """
        Check if we should exit the trade based on market conditions
        Returns True if we should exit, False otherwise
        """
        if not self.current_trade:
            return False
            
        latest = df.iloc[-1]
        
        # Exit if market structure changes against our position
        if self.current_trade['side'] == 'buy':
            if latest['bos_bearish'] or (latest['bearish_ob'] and self.trailing_activated):
                return True
        else:
            if latest['bos_bullish'] or (latest['bullish_ob'] and self.trailing_activated):
                return True
            
        return False
    
    def _apply_liquidity_sweep_bos_strategy(self, df):
        """
        Apply the Liquidity Sweep + Break of Structure strategy
        
        Args:
            df: DataFrame with indicators applied
        """
        # Look for bullish setup: liquidity sweep low + bullish BOS
        for i in range(5, len(df)):
            # Check for liquidity sweep low in the last 3 bars
            sweep_low = df.iloc[i-3:i]['sweep_low'].any()
            
            # Check for bullish break of structure in current bar
            bos_bullish = df.iloc[i]['bos_bullish']
            
            if sweep_low and bos_bullish:
                # Generate buy signal
                df.loc[df.index[i], 'signal'] = 1
                df.loc[df.index[i], 'entry_price'] = df.iloc[i]['close']
                
                # Set stop loss below the swept liquidity level
                sweep_idx = df.iloc[i-3:i][df.iloc[i-3:i]['sweep_low']].index[-1]
                df.loc[df.index[i], 'stop_loss'] = df.loc[sweep_idx, 'low'] - (config.SL_PADDING * 0.0001)
                
                # Calculate take profit based on risk-reward ratio
                risk = df.iloc[i]['entry_price'] - df.iloc[i]['stop_loss']
                df.loc[df.index[i], 'take_profit'] = df.iloc[i]['entry_price'] + (risk * self.tp_ratio)
                df.loc[df.index[i], 'risk_reward'] = self.tp_ratio
                df.loc[df.index[i], 'signal_type'] = 'Liquidity Sweep + BOS (Buy)'
        
        # Look for bearish setup: liquidity sweep high + bearish BOS
        for i in range(5, len(df)):
            # Check for liquidity sweep high in the last 3 bars
            sweep_high = df.iloc[i-3:i]['sweep_high'].any()
            
            # Check for bearish break of structure in current bar
            bos_bearish = df.iloc[i]['bos_bearish']
            
            if sweep_high and bos_bearish:
                # Generate sell signal
                df.loc[df.index[i], 'signal'] = -1
                df.loc[df.index[i], 'entry_price'] = df.iloc[i]['close']
                
                # Set stop loss above the swept liquidity level
                sweep_idx = df.iloc[i-3:i][df.iloc[i-3:i]['sweep_high']].index[-1]
                df.loc[df.index[i], 'stop_loss'] = df.loc[sweep_idx, 'high'] + (config.SL_PADDING * 0.0001)
                
                # Calculate take profit based on risk-reward ratio
                risk = df.iloc[i]['stop_loss'] - df.iloc[i]['entry_price']
                df.loc[df.index[i], 'take_profit'] = df.iloc[i]['entry_price'] - (risk * self.tp_ratio)
                df.loc[df.index[i], 'risk_reward'] = self.tp_ratio
                df.loc[df.index[i], 'signal_type'] = 'Liquidity Sweep + BOS (Sell)'
    
    def _apply_ob_fvg_return_strategy(self, df):
        """
        Apply the Order Block or Fair Value Gap return strategy
        
        Args:
            df: DataFrame with indicators applied
        """
        # Look for bullish setup: price returning to bearish order block or bearish FVG
        for i in range(10, len(df)):
            # Find recent bearish order blocks and FVGs
            recent_bearish_obs = df.iloc[i-10:i-1][df.iloc[i-10:i-1]['bearish_ob']]
            recent_bearish_fvgs = df.iloc[i-10:i-1][df.iloc[i-10:i-1]['bearish_fvg']]
            
            # Check if current price is near any bearish order block
            for ob_idx in recent_bearish_obs.index:
                ob_low = df.loc[ob_idx, 'bearish_ob_low']
                ob_high = df.loc[ob_idx, 'bearish_ob_high']
                
                # Check if price is returning to the order block
                if df.iloc[i]['low'] <= ob_high and df.iloc[i]['high'] >= ob_low:
                    # Check for additional confirmation (e.g., bullish candle)
                    if df.iloc[i]['close'] > df.iloc[i]['open']:
                        # Generate buy signal
                        df.loc[df.index[i], 'signal'] = 1
                        df.loc[df.index[i], 'entry_price'] = df.iloc[i]['close']
                        
                        # Set stop loss below the order block
                        df.loc[df.index[i], 'stop_loss'] = ob_low - (config.SL_PADDING * 0.0001)
                        
                        # Calculate take profit based on risk-reward ratio
                        risk = df.iloc[i]['entry_price'] - df.iloc[i]['stop_loss']
                        df.loc[df.index[i], 'take_profit'] = df.iloc[i]['entry_price'] + (risk * self.tp_ratio)
                        df.loc[df.index[i], 'risk_reward'] = self.tp_ratio
                        df.loc[df.index[i], 'signal_type'] = 'Bearish OB Return (Buy)'
                        break
            
            # Check if current price is near any bearish FVG
            for fvg_idx in recent_bearish_fvgs.index:
                fvg_low = df.loc[fvg_idx, 'bearish_fvg_low']
                fvg_high = df.loc[fvg_idx, 'bearish_fvg_high']
                
                # Check if price is returning to the FVG
                if df.iloc[i]['low'] <= fvg_high and df.iloc[i]['high'] >= fvg_low:
                    # Check for additional confirmation (e.g., bullish candle)
                    if df.iloc[i]['close'] > df.iloc[i]['open']:
                        # Generate buy signal
                        df.loc[df.index[i], 'signal'] = 1
                        df.loc[df.index[i], 'entry_price'] = df.iloc[i]['close']
                        
                        # Set stop loss below the FVG
                        df.loc[df.index[i], 'stop_loss'] = fvg_low - (config.SL_PADDING * 0.0001)
                        
                        # Calculate take profit based on risk-reward ratio
                        risk = df.iloc[i]['entry_price'] - df.iloc[i]['stop_loss']
                        df.loc[df.index[i], 'take_profit'] = df.iloc[i]['entry_price'] + (risk * self.tp_ratio)
                        df.loc[df.index[i], 'risk_reward'] = self.tp_ratio
                        df.loc[df.index[i], 'signal_type'] = 'Bearish FVG Return (Buy)'
                        break
        
        # Look for bearish setup: price returning to bullish order block or bullish FVG
        for i in range(10, len(df)):
            # Find recent bullish order blocks and FVGs
            recent_bullish_obs = df.iloc[i-10:i-1][df.iloc[i-10:i-1]['bullish_ob']]
            recent_bullish_fvgs = df.iloc[i-10:i-1][df.iloc[i-10:i-1]['bullish_fvg']]
            
            # Check if current price is near any bullish order block
            for ob_idx in recent_bullish_obs.index:
                ob_low = df.loc[ob_idx, 'bullish_ob_low']
                ob_high = df.loc[ob_idx, 'bullish_ob_high']
                
                # Check if price is returning to the order block
                if df.iloc[i]['low'] <= ob_high and df.iloc[i]['high'] >= ob_low:
                    # Check for additional confirmation (e.g., bearish candle)
                    if df.iloc[i]['close'] < df.iloc[i]['open']:
                        # Generate sell signal
                        df.loc[df.index[i], 'signal'] = -1
                        df.loc[df.index[i], 'entry_price'] = df.iloc[i]['close']
                        
                        # Set stop loss above the order block
                        df.loc[df.index[i], 'stop_loss'] = ob_high + (config.SL_PADDING * 0.0001)
                        
                        # Calculate take profit based on risk-reward ratio
                        risk = df.iloc[i]['stop_loss'] - df.iloc[i]['entry_price']
                        df.loc[df.index[i], 'take_profit'] = df.iloc[i]['entry_price'] - (risk * self.tp_ratio)
                        df.loc[df.index[i], 'risk_reward'] = self.tp_ratio
                        df.loc[df.index[i], 'signal_type'] = 'Bullish OB Return (Sell)'
                        break
            
            # Check if current price is near any bullish FVG
            for fvg_idx in recent_bullish_fvgs.index:
                fvg_low = df.loc[fvg_idx, 'bullish_fvg_low']
                fvg_high = df.loc[fvg_idx, 'bullish_fvg_high']
                
                # Check if price is returning to the FVG
                if df.iloc[i]['low'] <= fvg_high and df.iloc[i]['high'] >= fvg_low:
                    # Check for additional confirmation (e.g., bearish candle)
                    if df.iloc[i]['close'] < df.iloc[i]['open']:
                        # Generate sell signal
                        df.loc[df.index[i], 'signal'] = -1
                        df.loc[df.index[i], 'entry_price'] = df.iloc[i]['close']
                        
                        # Set stop loss above the FVG
                        df.loc[df.index[i], 'stop_loss'] = fvg_high + (config.SL_PADDING * 0.0001)
                        
                        # Calculate take profit based on risk-reward ratio
                        risk = df.iloc[i]['stop_loss'] - df.iloc[i]['entry_price']
                        df.loc[df.index[i], 'take_profit'] = df.iloc[i]['entry_price'] - (risk * self.tp_ratio)
                        df.loc[df.index[i], 'risk_reward'] = self.tp_ratio
                        df.loc[df.index[i], 'signal_type'] = 'Bullish FVG Return (Sell)'
                        break
    
    def calculate_position_size(self, account_balance, entry_price, stop_loss):
        """
        Calculate position size based on risk percentage
        
        Args:
            account_balance: Current account balance
            entry_price: Entry price for the trade
            stop_loss: Stop loss price for the trade
            
        Returns:
            Position size in lots
        """
        # Calculate risk amount in account currency
        risk_amount = account_balance * (self.risk_percent / 100)
        
        # Calculate risk per pip
        risk_per_pip = abs(entry_price - stop_loss)
        
        # Calculate position size (for XAUUSD, 1 lot = 100 oz)
        # For gold, 1 pip is typically $0.01 per oz
        position_size = risk_amount / (risk_per_pip * 100 * 100)  # Convert to lots
        
        # Round to 2 decimal places (minimum lot size is typically 0.01)
        position_size = round(position_size, 2)
        
        # Ensure minimum position size
        position_size = max(position_size, 0.01)
        
        return position_size