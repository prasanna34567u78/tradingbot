"""
Trade Quality Improvement Module
Focuses on improving signal quality and reducing false signals
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, time
import config

logger = logging.getLogger(__name__)

class TradeQualityFilter:
    """
    Advanced trade quality filtering system to improve success rate
    """
    
    def __init__(self):
        self.quality_config = getattr(config, 'TRADE_QUALITY', {})
        
    def validate_signal_quality(self, df, signal_data, symbol):
        """
        Comprehensive signal quality validation
        
        Args:
            df: Market data DataFrame
            signal_data: Signal information
            symbol: Trading symbol
            
        Returns:
            dict: Validation result with score and reasons
        """
        quality_score = 0
        max_score = 100
        reasons = []
        
        try:
            # 1. ATR-based volatility check (20 points)
            atr = df['atr'].iloc[-1] if 'atr' in df.columns else None
            if atr and atr > 0:
                entry_price = signal_data.get('entry_price', 0)
                stop_distance = abs(entry_price - signal_data.get('stop_loss', entry_price))
                atr_multiple = stop_distance / atr if atr > 0 else 0
                
                min_atr_mult = self.quality_config.get('min_atr_multiplier', 1.5)
                if atr_multiple >= min_atr_mult:
                    quality_score += 20
                    reasons.append(f"Good ATR multiple: {atr_multiple:.2f}")
                else:
                    reasons.append(f"Low ATR multiple: {atr_multiple:.2f} < {min_atr_mult}")
            
            trend_confirmation = self.quality_config.get('trend_confirmation', True)
            # 2. Trend confirmation (25 points)
            if trend_confirmation and self._check_trend_alignment(df):
                quality_score += 25
                reasons.append("Strong trend alignment")
            else:
                reasons.append("Weak or conflicting trend")
            
            # 3. Market session check (15 points)
            session_filter = self.quality_config.get('session_filter', True)
            if session_filter and self._is_active_session():
                quality_score += 15
                reasons.append("Active trading session (High Liquidity)")
            else:
                reasons.append("Inactive trading session (Low Liquidity)")
            
            # 4. Momentum confirmation (20 points)
            momentum_score = self._check_momentum(df)
            quality_score += momentum_score
            if momentum_score > 15:
                reasons.append("Strong momentum alignment")
            elif momentum_score > 10:
                reasons.append("Moderate momentum")
            else:
                reasons.append("Weak momentum")
            
            # 5. Structure break confirmation (20 points - Required for SMC/Scalp)
            has_structure_break = self._check_structure_break(df, signal_data)
            if has_structure_break:
                quality_score += 20
                reasons.append("Clear structure break / FVG Order Block confirmed")
            else:
                reasons.append("No clear structure break / FVG")
            
            # Calculate final quality percentage
            quality_percentage = (quality_score / max_score) * 100
            
            # Quality thresholds
            if quality_percentage >= 80:
                quality_level = "EXCELLENT"
            elif quality_percentage >= 65:
                quality_level = "GOOD"
            elif quality_percentage >= 50:
                quality_level = "FAIR"
            else:
                quality_level = "POOR"
            
            # Adjust minimum quality threshold based on AI settings
            ai_settings = getattr(config, 'AI_SETTINGS', {})
            scalping_mode = ai_settings.get('scalping_mode', False)
            min_quality_threshold = 35 if scalping_mode else 50  # Lower threshold for scalping
            
            return {
                'valid': quality_percentage >= min_quality_threshold,
                'score': quality_percentage,
                'level': quality_level,
                'reasons': reasons,
                'scalping_mode': scalping_mode,
                'threshold_used': min_quality_threshold,
                'details': {
                    'atr_check': atr_multiple if atr else None,
                    'trend_score': 25 if self._check_trend_alignment(df) else 0,
                    'session_score': 15 if self._is_active_session() else 0,
                    'momentum_score': momentum_score,
                    'structure_score': 20 if self._check_structure_break(df, signal_data) else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error in quality validation: {str(e)}")
            return {
                'valid': False,
                'score': 0,
                'level': "ERROR",
                'reasons': [f"Validation error: {str(e)}"],
                'details': {}
            }
    
    def _check_trend_alignment(self, df):
        """Check if multiple timeframe trends are aligned"""
        try:
            # Short-term trend (last 10 candles)
            short_ma = df['close'].rolling(10).mean()
            short_trend = short_ma.iloc[-1] > short_ma.iloc[-5]
            
            # Medium-term trend (last 20 candles)
            med_ma = df['close'].rolling(20).mean()
            med_trend = med_ma.iloc[-1] > med_ma.iloc[-10]
            
            # Long-term trend (last 50 candles)
            if len(df) >= 50:
                long_ma = df['close'].rolling(50).mean()
                long_trend = long_ma.iloc[-1] > long_ma.iloc[-25]
                
                # All three trends should align
                return short_trend == med_trend == long_trend
            else:
                # If not enough data, check short and medium term
                return short_trend == med_trend
                
        except Exception:
            return False
    
    def _is_active_session(self):
        """Check if we're in an active institutional trading session using UTC"""
        try:
            # Active institutional liquidity window: 07:00 UTC to 21:30 UTC (London + NY)
            now_utc = datetime.utcnow().time()
            session_start = time(7, 0)   # London Open (7:00 UTC / 12:30 PM IST)
            session_end = time(21, 30)   # NY Close (21:30 UTC / 3:00 AM IST)
            
            return session_start <= now_utc <= session_end
            
        except Exception:
            return True
    
    def _check_momentum(self, df):
        """Check momentum indicators for signal strength"""
        try:
            score = 0
            
            # RSI momentum check
            if 'rsi' in df.columns:
                rsi = df['rsi'].iloc[-1]
                if 30 < rsi < 70:  # Not overbought/oversold
                    score += 5
                if abs(rsi - 50) > 15:  # Strong directional bias
                    score += 5
            
            # MACD momentum check
            if 'macd' in df.columns and 'macd_signal' in df.columns:
                macd = df['macd'].iloc[-1]
                macd_signal = df['macd_signal'].iloc[-1]
                macd_prev = df['macd'].iloc[-2] if len(df) > 1 else macd
                macd_signal_prev = df['macd_signal'].iloc[-2] if len(df) > 1 else macd_signal
                
                # MACD crossover
                if (macd > macd_signal and macd_prev <= macd_signal_prev) or \
                   (macd < macd_signal and macd_prev >= macd_signal_prev):
                    score += 10
            
            return min(score, 20)  # Max 20 points for momentum
            
        except Exception:
            return 10  # Default moderate score
    
    def _check_structure_break(self, df, signal_data):
        """Check for clear market structure breaks"""
        try:
            signal_type = signal_data.get('signal', 0)
            
            if signal_type == 0:
                return False
            
            # Look for break of structure in recent candles
            recent_highs = df['high'].rolling(5).max()
            recent_lows = df['low'].rolling(5).min()
            
            if signal_type > 0:  # Buy signal
                # Check for break above recent highs
                current_high = df['high'].iloc[-1]
                prev_high = recent_highs.iloc[-2] if len(recent_highs) > 1 else current_high
                return current_high > prev_high
            else:  # Sell signal
                # Check for break below recent lows
                current_low = df['low'].iloc[-1]
                prev_low = recent_lows.iloc[-2] if len(recent_lows) > 1 else current_low
                return current_low < prev_low
                
        except Exception:
            return False

class EnhancedSignalGenerator:
    """
    Enhanced signal generation with quality focus
    """
    
    def __init__(self, quality_filter):
        self.quality_filter = quality_filter
        
    def generate_high_quality_signals(self, df, symbol, strategy,confluence):
        """
        Generate only high-quality signals
        
        Args:
            df: Market data DataFrame
            symbol: Trading symbol
            strategy: Trading strategy instance
            
        Returns:
            dict: Signal data if high quality, None otherwise
        """
        try:
            # Generate base signals using existing strategy
            df_with_signals = strategy.generate_scalping_signals_with_confluence(df, confluence, strategy,symbol)
            
            latest = df_with_signals.iloc[-1]
            
            if latest['signal'] == 0:
                return None
            
            # Prepare signal data for quality check
            signal_data = {
                'signal': latest['signal'],
                'entry_price': latest['entry_price'],
                'stop_loss': latest['stop_loss'],
                'take_profit': latest['take_profit'],
                'signal_type': latest['signal_type']
            }
            
            # Validate signal quality
            quality_result = self.quality_filter.validate_signal_quality(df, signal_data, symbol)
            
            # Log quality assessment
            logger.info(f"{symbol} Signal Quality Assessment:")
            logger.info(f"  Quality Score: {quality_result['score']:.1f}%")
            logger.info(f"  Quality Level: {quality_result['level']}")
            logger.info(f"  Valid: {quality_result['valid']}")
            
            for reason in quality_result['reasons']:
                logger.info(f"  - {reason}")
            
            # Only return signal if quality is good enough
            if quality_result['valid'] and quality_result['score'] >= 65:
                signal_data['quality_score'] = quality_result['score']
                signal_data['quality_level'] = quality_result['level']
                return signal_data
            else:
                logger.info(f"{symbol} signal rejected due to low quality ({quality_result['score']:.1f}%)")
                return None
                
        except Exception as e:
            logger.error(f"Error generating quality signals for {symbol}: {str(e)}")
            return None 