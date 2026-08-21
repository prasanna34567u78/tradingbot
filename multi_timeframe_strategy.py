# Multi-Timeframe ICT/SMC Strategy Implementation

import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
import config
from indicators import SMCIndicators
from ai_analyzer import AITradeAnalyzer

logger = logging.getLogger('gold_trading_bot')


class MultiTimeframeAnalyzer:
    """
    Advanced multi-timeframe analyzer using ICT/SMC concepts
    """
    
    def __init__(self, mt5_executor):
        self.mt5_executor = mt5_executor
        self.indicators = SMCIndicators()
        self.ai_analyzer = AITradeAnalyzer()
        
        # Timeframe hierarchy (most important to least important for confluence)
        self.timeframe_hierarchy = ['4h', '1h', '15m', '5m', '1m']
        
        # Session times in UTC
        self.session_times = {
            'asian': {'start': 0, 'end': 9},
            'london': {'start': 8, 'end': 17},
            'new_york': {'start': 13, 'end': 22}
        }
        
        # Power of Three phases
        self.pot_phases = {
            'accumulation': {'asian': (0, 2), 'london': (8, 10), 'new_york': (13, 15)},
            'manipulation': {'asian': (2, 5), 'london': (10, 13), 'new_york': (15, 18)},
            'distribution': {'asian': (5, 9), 'london': (13, 17), 'new_york': (18, 22)}
        }
    
    def get_current_session(self) -> Dict:
        """
        Determine current trading session and Power of Three phase
        """
        current_time = datetime.now(timezone.utc)
        hour = current_time.hour
        
        # Determine session
        session = 'asian'
        if 8 <= hour < 17:
            session = 'london'
        elif 13 <= hour < 22:
            session = 'new_york'
        
        # Determine Power of Three phase
        pot_phase = 'accumulation'
        for phase, sessions in self.pot_phases.items():
            if session in sessions:
                start_hour, end_hour = sessions[session]
                if start_hour <= hour < end_hour:
                    pot_phase = phase
                    break
        
        return {
            'session': session,
            'pot_phase': pot_phase,
            'hour': hour,
            'is_overlap': session == 'new_york' and 13 <= hour < 17  # London/NY overlap
        }
    
    async def analyze_all_timeframes(self) -> Dict:
        """
        Analyze all timeframes and create comprehensive market view
        """
        analysis = {}
        
        # Analyze each timeframe
        for tf in self.timeframe_hierarchy:
            try:
                # Fetch data for this timeframe
                candle_count = 200 if tf in ['4h', '1h'] else 300
                df = self.mt5_executor.fetch_historical_data_mt5(tf, candle_count)
                
                if df is not None:
                    # Apply all indicators
                    df = self.indicators.apply_all_indicators(df)
                    
                    # Analyze this timeframe
                    analysis[tf] = self._analyze_timeframe(df, tf)
                else:
                    logger.warning(f"Failed to fetch data for {tf} timeframe")
                    analysis[tf] = self._get_empty_analysis()
                    
            except Exception as e:
                logger.error(f"Error analyzing {tf} timeframe: {str(e)}")
                analysis[tf] = self._get_empty_analysis()
        
        # Create confluence analysis
        analysis['confluence'] = self._create_confluence_analysis(analysis)
        
        # Add session context
        analysis['session_context'] = self.get_current_session()
        
        return analysis
    
    def _analyze_timeframe(self, df: pd.DataFrame, timeframe: str) -> Dict:
        """
        Analyze a single timeframe for ICT/SMC concepts
        """
        latest = df.iloc[-1]
        recent = df.iloc[-10:]  # Last 10 candles for trend analysis
        
        # Market structure analysis
        trend = self._determine_trend(df)
        structure = self._analyze_market_structure(df)
        
        # Key levels
        key_levels = self._identify_key_levels(df)
        
        # Liquidity analysis
        liquidity = self._analyze_liquidity(df)
        
        # Order flow analysis
        order_flow = self._analyze_order_flow(df)
        
        # Premium/Discount analysis
        premium_discount = self._analyze_premium_discount(df)
        
        # Volatility analysis
        volatility = self._analyze_volatility(df)
        
        return {
            'timeframe': timeframe,
            'trend': trend,
            'structure': structure,
            'key_levels': key_levels,
            'liquidity': liquidity,
            'order_flow': order_flow,
            'premium_discount': premium_discount,
            'volatility': volatility,
            'current_price': latest['close'],
            'atr': latest.get('atr', 0),
            'signals': self._get_timeframe_signals(df)
        }
    
    def _determine_trend(self, df: pd.DataFrame) -> Dict:
        """
        Determine trend using multiple methods
        """
        # Moving average trend
        ma_20 = df['close'].rolling(20).mean()
        ma_50 = df['close'].rolling(50).mean()
        
        # Structure trend (based on swing points)
        swing_highs = df[df['swing_high'] == True]['high'].tail(3)
        swing_lows = df[df['swing_low'] == True]['low'].tail(3)
        
        # Determine trend direction
        ma_trend = 'bullish' if ma_20.iloc[-1] > ma_50.iloc[-1] else 'bearish'
        
        structure_trend = 'neutral'
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            if swing_highs.iloc[-1] > swing_highs.iloc[-2] and swing_lows.iloc[-1] > swing_lows.iloc[-2]:
                structure_trend = 'bullish'
            elif swing_highs.iloc[-1] < swing_highs.iloc[-2] and swing_lows.iloc[-1] < swing_lows.iloc[-2]:
                structure_trend = 'bearish'
        
        # Momentum analysis
        momentum = df['close'].pct_change(20).iloc[-1]
        
        return {
            'ma_trend': ma_trend,
            'structure_trend': structure_trend,
            'momentum': momentum,
            'strength': abs(momentum) * 100,  # Trend strength as percentage
            'overall': ma_trend if ma_trend == structure_trend else 'neutral'
        }
    
    def _analyze_market_structure(self, df: pd.DataFrame) -> Dict:
        """
        Analyze market structure (BOS, ChoCh, etc.)
        """
        latest = df.iloc[-1]
        recent = df.iloc[-20:]
        
        # Check for Break of Structure (BOS)
        has_bos_bull = recent['bos_bullish'].any()
        has_bos_bear = recent['bos_bearish'].any()
        
        # Check for Change of Character (ChoCh)
        choch_bull = self._detect_choch(df, 'bullish')
        choch_bear = self._detect_choch(df, 'bearish')
        
        # Market structure shift
        structure_shift = 'none'
        if has_bos_bull and not has_bos_bear:
            structure_shift = 'bullish_bos'
        elif has_bos_bear and not has_bos_bull:
            structure_shift = 'bearish_bos'
        elif choch_bull:
            structure_shift = 'bullish_choch'
        elif choch_bear:
            structure_shift = 'bearish_choch'
        
        return {
            'bos_bullish': has_bos_bull,
            'bos_bearish': has_bos_bear,
            'choch_bullish': choch_bull,
            'choch_bearish': choch_bear,
            'structure_shift': structure_shift,
            'last_swing_high': df[df['swing_high'] == True]['high'].iloc[-1] if df['swing_high'].any() else None,
            'last_swing_low': df[df['swing_low'] == True]['low'].iloc[-1] if df['swing_low'].any() else None
        }
    
    def _detect_choch(self, df: pd.DataFrame, direction: str) -> bool:
        """
        Detect Change of Character (ChoCh)
        """
        try:
            if direction == 'bullish':
                # Look for lower high followed by higher high
                swing_highs = df[df['swing_high'] == True]['high'].tail(3)
                if len(swing_highs) >= 3:
                    return swing_highs.iloc[-3] > swing_highs.iloc[-2] < swing_highs.iloc[-1]
            else:
                # Look for higher low followed by lower low
                swing_lows = df[df['swing_low'] == True]['low'].tail(3)
                if len(swing_lows) >= 3:
                    return swing_lows.iloc[-3] < swing_lows.iloc[-2] > swing_lows.iloc[-1]
        except Exception:
            pass
        return False
    
    def _identify_key_levels(self, df: pd.DataFrame) -> Dict:
        """
        Identify key support/resistance levels
        """
        # Previous day high/low
        daily_high = df['high'].rolling(24).max().iloc[-1] if len(df) >= 24 else df['high'].max()
        daily_low = df['low'].rolling(24).min().iloc[-1] if len(df) >= 24 else df['low'].min()
        
        # Weekly high/low (approximate)
        weekly_high = df['high'].rolling(168).max().iloc[-1] if len(df) >= 168 else df['high'].max()
        weekly_low = df['low'].rolling(168).min().iloc[-1] if len(df) >= 168 else df['low'].min()
        
        # Order blocks
        bullish_obs = df[df['bullish_ob'] == True][['bullish_ob_high', 'bullish_ob_low']].tail(3)
        bearish_obs = df[df['bearish_ob'] == True][['bearish_ob_high', 'bearish_ob_low']].tail(3)
        
        # Fair Value Gaps
        bullish_fvgs = df[df['bullish_fvg'] == True][['bullish_fvg_high', 'bullish_fvg_low']].tail(3)
        bearish_fvgs = df[df['bearish_fvg'] == True][['bearish_fvg_high', 'bearish_fvg_low']].tail(3)
        
        return {
            'daily_high': daily_high,
            'daily_low': daily_low,
            'weekly_high': weekly_high,
            'weekly_low': weekly_low,
            'bullish_order_blocks': bullish_obs.to_dict('records') if not bullish_obs.empty else [],
            'bearish_order_blocks': bearish_obs.to_dict('records') if not bearish_obs.empty else [],
            'bullish_fvgs': bullish_fvgs.to_dict('records') if not bullish_fvgs.empty else [],
            'bearish_fvgs': bearish_fvgs.to_dict('records') if not bearish_fvgs.empty else []
        }
    
    def _analyze_liquidity(self, df: pd.DataFrame) -> Dict:
        """
        Analyze liquidity levels and sweeps
        """
        recent = df.iloc[-20:]
        
        # Liquidity sweeps
        sweep_high = recent['sweep_high'].any()
        sweep_low = recent['sweep_low'].any()
        
        # Equal highs/lows (liquidity pools)
        equal_highs = self._find_equal_levels(df, 'high')
        equal_lows = self._find_equal_levels(df, 'low')
        
        # Liquidity zones
        liquidity_zones = self._identify_liquidity_zones(df)
        
        return {
            'recent_sweep_high': sweep_high,
            'recent_sweep_low': sweep_low,
            'equal_highs': equal_highs,
            'equal_lows': equal_lows,
            'liquidity_zones': liquidity_zones,
            'untested_highs': self._find_untested_levels(df, 'high'),
            'untested_lows': self._find_untested_levels(df, 'low')
        }
    
    def _find_equal_levels(self, df: pd.DataFrame, level_type: str, tolerance: float = 0.0002) -> List[float]:
        """
        Find equal highs or lows (liquidity pools)
        """
        levels = []
        try:
            if level_type == 'high':
                swing_levels = df[df['swing_high'] == True]['high'].tail(10)
            else:
                swing_levels = df[df['swing_low'] == True]['low'].tail(10)
            
            for i, level in enumerate(swing_levels):
                similar_levels = swing_levels[abs(swing_levels - level) / level < tolerance]
                if len(similar_levels) >= 2:
                    levels.append(level)
        except Exception:
            pass
        
        return levels
    
    def _find_untested_levels(self, df: pd.DataFrame, level_type: str) -> List[float]:
        """
        Find untested swing levels that could act as liquidity
        """
        levels = []
        try:
            if level_type == 'high':
                swing_levels = df[df['swing_high'] == True]['high'].tail(5)
                current_price = df['close'].iloc[-1]
                levels = [level for level in swing_levels if level > current_price]
            else:
                swing_levels = df[df['swing_low'] == True]['low'].tail(5)
                current_price = df['close'].iloc[-1]
                levels = [level for level in swing_levels if level < current_price]
        except Exception:
            pass
        
        return levels
    
    def _identify_liquidity_zones(self, df: pd.DataFrame) -> List[Dict]:
        """
        Identify zones with high liquidity concentration
        """
        zones = []
        try:
            # High volume areas
            volume_ma = df.get('volume', pd.Series([0]*len(df))).rolling(20).mean()
            high_volume_areas = df[df.get('volume', pd.Series([0]*len(df))) > volume_ma * 1.5]
            
            for _, candle in high_volume_areas.tail(5).iterrows():
                zones.append({
                    'high': candle['high'],
                    'low': candle['low'],
                    'type': 'high_volume',
                    'timestamp': candle.name
                })
        except Exception:
            pass
        
        return zones
    
    def _analyze_order_flow(self, df: pd.DataFrame) -> Dict:
        """
        Analyze order flow and smart money movements
        """
        recent = df.iloc[-10:]
        
        # Bullish/Bearish order blocks
        bullish_obs = recent['bullish_ob'].sum()
        bearish_obs = recent['bearish_ob'].sum()
        
        # Imbalances (FVGs)
        bullish_fvgs = recent['bullish_fvg'].sum()
        bearish_fvgs = recent['bearish_fvg'].sum()
        
        # Order flow bias
        order_flow_bias = 'neutral'
        if bullish_obs > bearish_obs and bullish_fvgs >= bearish_fvgs:
            order_flow_bias = 'bullish'
        elif bearish_obs > bullish_obs and bearish_fvgs >= bullish_fvgs:
            order_flow_bias = 'bearish'
        
        return {
            'bullish_order_blocks': int(bullish_obs),
            'bearish_order_blocks': int(bearish_obs),
            'bullish_imbalances': int(bullish_fvgs),
            'bearish_imbalances': int(bearish_fvgs),
            'order_flow_bias': order_flow_bias,
            'smart_money_activity': 'high' if (bullish_obs + bearish_obs) > 2 else 'low'
        }
    
    def _analyze_premium_discount(self, df: pd.DataFrame) -> Dict:
        """
        Analyze premium/discount areas using Fibonacci levels
        """
        try:
            # Find recent significant swing high and low
            swing_high = df[df['swing_high'] == True]['high'].tail(1).iloc[0] if df['swing_high'].any() else df['high'].max()
            swing_low = df[df['swing_low'] == True]['low'].tail(1).iloc[0] if df['swing_low'].any() else df['low'].min()
            
            current_price = df['close'].iloc[-1]
            
            # Calculate Fibonacci levels
            fib_range = swing_high - swing_low
            fib_levels = {}
            
            for level in config.ICT_SETTINGS['premium_discount_levels']:
                fib_levels[f'fib_{level}'] = swing_low + (fib_range * level)
            
            # Determine if we're in premium or discount
            mid_point = swing_low + (fib_range * 0.5)
            
            if current_price > mid_point:
                area = 'premium'
            else:
                area = 'discount'
            
            # Find closest level
            closest_level = min(fib_levels.values(), key=lambda x: abs(x - current_price))
            
            return {
                'area': area,
                'swing_high': swing_high,
                'swing_low': swing_low,
                'current_price': current_price,
                'mid_point': mid_point,
                'fib_levels': fib_levels,
                'closest_level': closest_level,
                'distance_to_closest': abs(current_price - closest_level)
            }
            
        except Exception as e:
            logger.error(f"Error in premium/discount analysis: {str(e)}")
            return {'area': 'unknown', 'error': str(e)}
    
    def _analyze_volatility(self, df: pd.DataFrame) -> Dict:
        """
        Analyze volatility conditions
        """
        try:
            atr = df.get('atr', pd.Series([0]*len(df)))
            atr_ma = atr.rolling(20).mean()
            
            current_atr = atr.iloc[-1]
            avg_atr = atr_ma.iloc[-1]
            
            # Volatility state
            volatility_ratio = current_atr / avg_atr if avg_atr > 0 else 1
            
            if volatility_ratio > 1.5:
                volatility_state = 'high'
            elif volatility_ratio < 0.7:
                volatility_state = 'low'
            else:
                volatility_state = 'normal'
            
            return {
                'current_atr': current_atr,
                'average_atr': avg_atr,
                'volatility_ratio': volatility_ratio,
                'volatility_state': volatility_state,
                'range_expansion': volatility_ratio > 1.2,
                'range_contraction': volatility_ratio < 0.8
            }
            
        except Exception as e:
            logger.error(f"Error in volatility analysis: {str(e)}")
            return {'volatility_state': 'unknown', 'error': str(e)}
    
    def _get_timeframe_signals(self, df: pd.DataFrame) -> Dict:
        """
        Get trading signals for this timeframe
        """
        latest = df.iloc[-1]
        
        # Basic signals
        signals = {
            'bullish_signals': 0,
            'bearish_signals': 0,
            'signal_strength': 0,
            'signal_types': []
        }
        
        # Check various signal types
        if latest.get('bos_bullish', False):
            signals['bullish_signals'] += 2
            signals['signal_types'].append('bullish_bos')
        
        if latest.get('bos_bearish', False):
            signals['bearish_signals'] += 2
            signals['signal_types'].append('bearish_bos')
        
        if latest.get('bullish_ob', False):
            signals['bullish_signals'] += 1
            signals['signal_types'].append('bullish_ob')
        
        if latest.get('bearish_ob', False):
            signals['bearish_signals'] += 1
            signals['signal_types'].append('bearish_ob')
        
        if latest.get('bullish_fvg', False):
            signals['bullish_signals'] += 1
            signals['signal_types'].append('bullish_fvg')
        
        if latest.get('bearish_fvg', False):
            signals['bearish_signals'] += 1
            signals['signal_types'].append('bearish_fvg')
        
        # Calculate overall signal strength
        total_signals = signals['bullish_signals'] + signals['bearish_signals']
        if total_signals > 0:
            if signals['bullish_signals'] > signals['bearish_signals']:
                signals['signal_strength'] = signals['bullish_signals']
                signals['direction'] = 'bullish'
            else:
                signals['signal_strength'] = signals['bearish_signals']
                signals['direction'] = 'bearish'
        else:
            signals['direction'] = 'neutral'
        
        return signals
    
    def _create_confluence_analysis(self, timeframe_analysis: Dict) -> Dict:
        """
        Create confluence analysis across all timeframes
        """
        confluence = {
            'bullish_confluence': 0,
            'bearish_confluence': 0,
            'confirming_timeframes': [],
            'conflicting_timeframes': [],
            'overall_bias': 'neutral',
            'confluence_strength': 0
        }
        
        # Weight factors for different timeframes
        weights = {'4h': 4, '1h': 3, '15m': 2, '5m': 1, '1m': 0.5}
        
        for tf in self.timeframe_hierarchy:
            if tf in timeframe_analysis:
                tf_data = timeframe_analysis[tf]
                weight = weights.get(tf, 1)
                
                # Analyze trend confluence
                trend = tf_data.get('trend', {})
                if trend.get('overall') == 'bullish':
                    confluence['bullish_confluence'] += weight
                    confluence['confirming_timeframes'].append(f"{tf}_bullish")
                elif trend.get('overall') == 'bearish':
                    confluence['bearish_confluence'] += weight
                    confluence['confirming_timeframes'].append(f"{tf}_bearish")
                else:
                    confluence['conflicting_timeframes'].append(f"{tf}_neutral")
                
                # Analyze structure confluence
                structure = tf_data.get('structure', {})
                if structure.get('bos_bullish'):
                    confluence['bullish_confluence'] += weight * 0.5
                if structure.get('bos_bearish'):
                    confluence['bearish_confluence'] += weight * 0.5
        
        # Determine overall bias
        total_confluence = confluence['bullish_confluence'] + confluence['bearish_confluence']
        if total_confluence > 0:
            if confluence['bullish_confluence'] > confluence['bearish_confluence']:
                confluence['overall_bias'] = 'bullish'
                confluence['confluence_strength'] = confluence['bullish_confluence'] / total_confluence
            else:
                confluence['overall_bias'] = 'bearish'
                confluence['confluence_strength'] = confluence['bearish_confluence'] / total_confluence
        
        return confluence
    
    def _get_empty_analysis(self) -> Dict:
        """
        Return empty analysis structure for failed timeframe analysis
        """
        return {
            'trend': {'overall': 'neutral'},
            'structure': {'structure_shift': 'none'},
            'key_levels': {},
            'liquidity': {},
            'order_flow': {'order_flow_bias': 'neutral'},
            'premium_discount': {'area': 'unknown'},
            'volatility': {'volatility_state': 'unknown'},
            'signals': {'direction': 'neutral', 'signal_strength': 0}
        }


class AdvancedICTStrategy:
    """
    Advanced ICT/SMC strategy with multi-timeframe analysis and AI integration
    """
    
    def __init__(self, mt5_executor):
        self.mt5_executor = mt5_executor
        self.mtf_analyzer = MultiTimeframeAnalyzer(mt5_executor)
        self.ai_analyzer = AITradeAnalyzer()
        self.current_trade = None
        
    async def analyze_and_generate_signals(self) -> Dict:
        """
        Main method to analyze market and generate trading signals
        """
        try:
            # Get multi-timeframe analysis
            mtf_analysis = await self.mtf_analyzer.analyze_all_timeframes()
            
            # Generate trading signals based on analysis
            signals = await self._generate_advanced_signals(mtf_analysis)
            
            # Get AI validation
            if signals['signal'] != 0:
                ai_validation = self.ai_analyzer.enhanced_validate_trade(
                    self._prepare_df_for_ai(mtf_analysis),
                    signals['signal'],
                    mtf_analysis
                )
                signals['ai_validation'] = ai_validation
            
            return {
                'mtf_analysis': mtf_analysis,
                'signals': signals,
                'session_context': mtf_analysis.get('session_context', {})
            }
            
        except Exception as e:
            logger.error(f"Error in advanced strategy analysis: {str(e)}")
            return {'error': str(e)}
    
    async def _generate_advanced_signals(self, mtf_analysis: Dict) -> Dict:
        """
        Generate advanced trading signals based on multi-timeframe analysis
        """
        signals = {
            'signal': 0,
            'entry_price': 0,
            'stop_loss': 0,
            'take_profit': 0,
            'signal_type': 'none',
            'confidence': 0,
            'reasoning': []
        }
        
        try:
            confluence = mtf_analysis.get('confluence', {})
            session_context = mtf_analysis.get('session_context', {})
            
            # Check confluence strength
            if confluence.get('confluence_strength', 0) < 0.6:
                signals['reasoning'].append('Insufficient confluence across timeframes')
                return signals
            
            # Check session context
            if not self._is_good_trading_session(session_context):
                signals['reasoning'].append('Unfavorable trading session')
                return signals
            
            # Get primary timeframe analysis
            primary_tf = config.TIMEFRAMES['primary']
            primary_analysis = mtf_analysis.get(primary_tf, {})
            
            # Check for high-probability setups
            signal_info = self._identify_high_probability_setup(mtf_analysis)
            
            if signal_info['signal'] != 0:
                # Calculate entry, stop loss, and take profit
                entry_info = self._calculate_entry_levels(signal_info, mtf_analysis)
                
                signals.update({
                    'signal': signal_info['signal'],
                    'signal_type': signal_info['signal_type'],
                    'confidence': signal_info['confidence'],
                    'reasoning': signal_info['reasoning'],
                    **entry_info
                })
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating advanced signals: {str(e)}")
            signals['reasoning'].append(f'Error: {str(e)}')
            return signals
    
    def _is_good_trading_session(self, session_context: Dict) -> bool:
        """
        Check if current session is favorable for trading
        """
        session = session_context.get('session', 'asian')
        pot_phase = session_context.get('pot_phase', 'accumulation')
        
        # Prefer London and NY sessions
        if session in ['london', 'new_york']:
            return True
        
        # Asian session is OK during distribution phase
        if session == 'asian' and pot_phase == 'distribution':
            return True
        
        return False
    
    def _identify_high_probability_setup(self, mtf_analysis: Dict) -> Dict:
        """
        Identify high-probability trading setups
        """
        setup = {
            'signal': 0,
            'signal_type': 'none',
            'confidence': 0,
            'reasoning': []
        }
        
        confluence = mtf_analysis.get('confluence', {})
        
        # Setup 1: Multi-timeframe BOS with Order Block
        bos_setup = self._check_bos_ob_setup(mtf_analysis)
        if bos_setup['signal'] != 0:
            setup.update(bos_setup)
            return setup
        
        # Setup 2: Liquidity Sweep with FVG
        sweep_setup = self._check_sweep_fvg_setup(mtf_analysis)
        if sweep_setup['signal'] != 0:
            setup.update(sweep_setup)
            return setup
        
        # Setup 3: Premium/Discount Reversal
        reversal_setup = self._check_premium_discount_reversal(mtf_analysis)
        if reversal_setup['signal'] != 0:
            setup.update(reversal_setup)
            return setup
        
        return setup
    
    def _check_bos_ob_setup(self, mtf_analysis: Dict) -> Dict:
        """
        Check for Break of Structure + Order Block setup
        """
        setup = {'signal': 0, 'signal_type': 'none', 'confidence': 0, 'reasoning': []}
        
        # Check higher timeframes for BOS
        higher_tf_bos = False
        for tf in ['4h', '1h']:
            if tf in mtf_analysis:
                structure = mtf_analysis[tf].get('structure', {})
                if structure.get('bos_bullish') or structure.get('bos_bearish'):
                    higher_tf_bos = True
                    break
        
        if not higher_tf_bos:
            return setup
        
        # Check primary timeframe for Order Block
        primary_tf = config.TIMEFRAMES['primary']
        if primary_tf in mtf_analysis:
            primary_analysis = mtf_analysis[primary_tf]
            order_flow = primary_analysis.get('order_flow', {})
            
            if order_flow.get('order_flow_bias') == 'bullish':
                setup.update({
                    'signal': 1,
                    'signal_type': 'bos_ob_bullish',
                    'confidence': 0.75,
                    'reasoning': ['Higher TF BOS', 'Bullish Order Block']
                })
            elif order_flow.get('order_flow_bias') == 'bearish':
                setup.update({
                    'signal': -1,
                    'signal_type': 'bos_ob_bearish',
                    'confidence': 0.75,
                    'reasoning': ['Higher TF BOS', 'Bearish Order Block']
                })
        
        return setup
    
    def _check_sweep_fvg_setup(self, mtf_analysis: Dict) -> Dict:
        """
        Check for Liquidity Sweep + Fair Value Gap setup
        """
        setup = {'signal': 0, 'signal_type': 'none', 'confidence': 0, 'reasoning': []}
        
        primary_tf = config.TIMEFRAMES['primary']
        if primary_tf not in mtf_analysis:
            return setup
        
        primary_analysis = mtf_analysis[primary_tf]
        liquidity = primary_analysis.get('liquidity', {})
        
        # Check for recent liquidity sweep
        if liquidity.get('recent_sweep_low'):
            # Look for bullish FVG after sweep
            key_levels = primary_analysis.get('key_levels', {})
            if key_levels.get('bullish_fvgs'):
                setup.update({
                    'signal': 1,
                    'signal_type': 'sweep_fvg_bullish',
                    'confidence': 0.7,
                    'reasoning': ['Liquidity Sweep Low', 'Bullish FVG']
                })
        
        elif liquidity.get('recent_sweep_high'):
            # Look for bearish FVG after sweep
            key_levels = primary_analysis.get('key_levels', {})
            if key_levels.get('bearish_fvgs'):
                setup.update({
                    'signal': -1,
                    'signal_type': 'sweep_fvg_bearish',
                    'confidence': 0.7,
                    'reasoning': ['Liquidity Sweep High', 'Bearish FVG']
                })
        
        return setup
    
    def _check_premium_discount_reversal(self, mtf_analysis: Dict) -> Dict:
        """
        Check for Premium/Discount area reversal setup
        """
        setup = {'signal': 0, 'signal_type': 'none', 'confidence': 0, 'reasoning': []}
        
        # Check higher timeframe premium/discount
        for tf in ['4h', '1h']:
            if tf in mtf_analysis:
                pd_analysis = mtf_analysis[tf].get('premium_discount', {})
                
                if pd_analysis.get('area') == 'discount':
                    # Look for bullish reversal in discount
                    primary_tf = config.TIMEFRAMES['primary']
                    if primary_tf in mtf_analysis:
                        primary_structure = mtf_analysis[primary_tf].get('structure', {})
                        if primary_structure.get('bos_bullish'):
                            setup.update({
                                'signal': 1,
                                'signal_type': 'discount_reversal_bullish',
                                'confidence': 0.65,
                                'reasoning': ['In Discount Area', 'Bullish Reversal']
                            })
                            break
                
                elif pd_analysis.get('area') == 'premium':
                    # Look for bearish reversal in premium
                    primary_tf = config.TIMEFRAMES['primary']
                    if primary_tf in mtf_analysis:
                        primary_structure = mtf_analysis[primary_tf].get('structure', {})
                        if primary_structure.get('bos_bearish'):
                            setup.update({
                                'signal': -1,
                                'signal_type': 'premium_reversal_bearish',
                                'confidence': 0.65,
                                'reasoning': ['In Premium Area', 'Bearish Reversal']
                            })
                            break
        
        return setup
    
    def _calculate_entry_levels(self, signal_info: Dict, mtf_analysis: Dict) -> Dict:
        """
        Calculate entry, stop loss, and take profit levels
        """
        entry_levels = {
            'entry_price': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        
        try:
            # Get current price from primary timeframe
            primary_tf = config.TIMEFRAMES['primary']
            if primary_tf in mtf_analysis:
                current_price = mtf_analysis[primary_tf].get('current_price', 0)
                atr = mtf_analysis[primary_tf].get('atr', 0.001)
                
                if signal_info['signal'] == 1:  # Buy signal
                    entry_levels['entry_price'] = current_price
                    entry_levels['stop_loss'] = current_price - (atr * 2)
                    entry_levels['take_profit'] = current_price + (atr * 4)
                
                elif signal_info['signal'] == -1:  # Sell signal
                    entry_levels['entry_price'] = current_price
                    entry_levels['stop_loss'] = current_price + (atr * 2)
                    entry_levels['take_profit'] = current_price - (atr * 4)
            
        except Exception as e:
            logger.error(f"Error calculating entry levels: {str(e)}")
        
        return entry_levels
    
    def _prepare_df_for_ai(self, mtf_analysis: Dict) -> pd.DataFrame:
        """
        Prepare a DataFrame for AI analysis from multi-timeframe analysis
        """
        # Create a simple DataFrame with the most recent data
        primary_tf = config.TIMEFRAMES['primary']
        
        if primary_tf in mtf_analysis:
            data = mtf_analysis[primary_tf]
            
            # Create a minimal DataFrame for AI analysis
            df = pd.DataFrame({
                'close': [data.get('current_price', 0)],
                'high': [data.get('current_price', 0)],
                'low': [data.get('current_price', 0)],
                'atr': [data.get('atr', 0)],
                'bos_bullish': [data.get('structure', {}).get('bos_bullish', False)],
                'bos_bearish': [data.get('structure', {}).get('bos_bearish', False)],
                'bullish_ob': [data.get('order_flow', {}).get('bullish_order_blocks', 0) > 0],
                'bearish_ob': [data.get('order_flow', {}).get('bearish_order_blocks', 0) > 0],
                'bullish_fvg': [data.get('order_flow', {}).get('bullish_imbalances', 0) > 0],
                'bearish_fvg': [data.get('order_flow', {}).get('bearish_imbalances', 0) > 0]
            })
            
            return df
        
        # Return empty DataFrame if no data available
        return pd.DataFrame() 