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
        
        return {
            'session': session,
            'hour': hour,
            'is_overlap': session == 'new_york' and 13 <= hour < 17
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
        
        # Market structure analysis
        trend = self._determine_trend(df)
        structure = self._analyze_market_structure(df)
        
        # Key levels
        key_levels = self._identify_key_levels(df)
        
        # Liquidity analysis
        liquidity = self._analyze_liquidity(df)
        
        # Order flow analysis
        order_flow = self._analyze_order_flow(df)
        
        return {
            'timeframe': timeframe,
            'trend': trend,
            'structure': structure,
            'key_levels': key_levels,
            'liquidity': liquidity,
            'order_flow': order_flow,
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
        
        # Determine trend direction
        ma_trend = 'bullish' if ma_20.iloc[-1] > ma_50.iloc[-1] else 'bearish'
        
        # Momentum analysis
        momentum = df['close'].pct_change(20).iloc[-1]
        
        return {
            'ma_trend': ma_trend,
            'momentum': momentum,
            'strength': abs(momentum) * 100,  # Trend strength as percentage
            'overall': ma_trend
        }
    
    def _analyze_market_structure(self, df: pd.DataFrame) -> Dict:
        """
        Analyze market structure (BOS, ChoCh, etc.)
        """
        recent = df.iloc[-20:]
        
        # Check for Break of Structure (BOS)
        has_bos_bull = recent['bos_bullish'].any()
        has_bos_bear = recent['bos_bearish'].any()
        
        # Market structure shift
        structure_shift = 'none'
        if has_bos_bull and not has_bos_bear:
            structure_shift = 'bullish_bos'
        elif has_bos_bear and not has_bos_bull:
            structure_shift = 'bearish_bos'
        
        return {
            'bos_bullish': has_bos_bull,
            'bos_bearish': has_bos_bear,
            'structure_shift': structure_shift,
        }
    
    def _identify_key_levels(self, df: pd.DataFrame) -> Dict:
        """
        Identify key support/resistance levels
        """
        # Order blocks
        bullish_obs = df[df['bullish_ob'] == True].tail(3)
        bearish_obs = df[df['bearish_ob'] == True].tail(3)
        
        # Fair Value Gaps
        bullish_fvgs = df[df['bullish_fvg'] == True].tail(3)
        bearish_fvgs = df[df['bearish_fvg'] == True].tail(3)
        
        return {
            'bullish_order_blocks': len(bullish_obs),
            'bearish_order_blocks': len(bearish_obs),
            'bullish_fvgs': len(bullish_fvgs),
            'bearish_fvgs': len(bearish_fvgs)
        }
    
    def _analyze_liquidity(self, df: pd.DataFrame) -> Dict:
        """
        Analyze liquidity levels and sweeps
        """
        recent = df.iloc[-20:]
        
        # Liquidity sweeps
        sweep_high = recent['sweep_high'].any()
        sweep_low = recent['sweep_low'].any()
        
        return {
            'recent_sweep_high': sweep_high,
            'recent_sweep_low': sweep_low,
        }
    
    def _analyze_order_flow(self, df: pd.DataFrame) -> Dict:
        """
        Analyze order flow and smart money movements
        """
        recent = df.iloc[-10:]
        
        # Bullish/Bearish order blocks
        bullish_obs = recent['bullish_ob'].sum()
        bearish_obs = recent['bearish_ob'].sum()
        
        # Order flow bias
        order_flow_bias = 'neutral'
        if bullish_obs > bearish_obs:
            order_flow_bias = 'bullish'
        elif bearish_obs > bullish_obs:
            order_flow_bias = 'bearish'
        
        return {
            'bullish_order_blocks': int(bullish_obs),
            'bearish_order_blocks': int(bearish_obs),
            'order_flow_bias': order_flow_bias,
        }
    
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
                ai_validation = self.ai_analyzer.validate_trade(
                    self._prepare_df_for_ai(mtf_analysis),
                    signals['signal']
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
            session = session_context.get('session', 'asian')
            if session not in ['london', 'new_york']:
                signals['reasoning'].append('Unfavorable trading session')
                return signals
            
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
        
        # Setup 1: Multi-timeframe BOS with Order Block
        bos_setup = self._check_bos_ob_setup(mtf_analysis)
        if bos_setup['signal'] != 0:
            setup.update(bos_setup)
            return setup
        
        # Setup 2: Liquidity Sweep with Structure Break
        sweep_setup = self._check_sweep_setup(mtf_analysis)
        if sweep_setup['signal'] != 0:
            setup.update(sweep_setup)
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
    
    def _check_sweep_setup(self, mtf_analysis: Dict) -> Dict:
        """
        Check for Liquidity Sweep setup
        """
        setup = {'signal': 0, 'signal_type': 'none', 'confidence': 0, 'reasoning': []}
        
        primary_tf = config.TIMEFRAMES['primary']
        if primary_tf not in mtf_analysis:
            return setup
        
        primary_analysis = mtf_analysis[primary_tf]
        liquidity = primary_analysis.get('liquidity', {})
        
        # Check for recent liquidity sweep
        if liquidity.get('recent_sweep_low'):
            setup.update({
                'signal': 1,
                'signal_type': 'sweep_bullish',
                'confidence': 0.7,
                'reasoning': ['Liquidity Sweep Low']
            })
        elif liquidity.get('recent_sweep_high'):
            setup.update({
                'signal': -1,
                'signal_type': 'sweep_bearish',
                'confidence': 0.7,
                'reasoning': ['Liquidity Sweep High']
            })
        
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
                'bullish_fvg': [False],
                'bearish_fvg': [False]
            })
            
            return df
        
        # Return empty DataFrame if no data available
        return pd.DataFrame()
