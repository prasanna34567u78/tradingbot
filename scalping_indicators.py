# Scalping-specific indicators for high-frequency trading

import numpy as np
import pandas as pd
from scipy import stats


class ScalpingIndicators:
    """
    Specialized indicators for scalping strategies on 1m and 5m timeframes
    Focus on momentum, volatility, and quick reversal patterns
    """
    
    @staticmethod
    def apply_scalping_indicators(df):
        """
        Apply all scalping indicators to the dataframe
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with scalping indicators added
        """
        df = df.copy()
        
        # Fast momentum indicators
        df = ScalpingIndicators.fast_rsi(df, period=7)
        df = ScalpingIndicators.stochastic_fast(df, k_period=5, d_period=3)
        df = ScalpingIndicators.macd_fast(df, fast=5, slow=13, signal=4)
        
        # Price velocity and acceleration
        df = ScalpingIndicators.price_velocity(df)
        df = ScalpingIndicators.price_acceleration(df)
        
        # Volatility indicators
        df = ScalpingIndicators.realized_volatility(df)
        df = ScalpingIndicators.bollinger_bands_fast(df, period=10, std_dev=1.5)
        df = ScalpingIndicators.atr_fast(df, period=7)
        
        # Volume indicators
        df = ScalpingIndicators.volume_spike_detector(df)
        df = ScalpingIndicators.volume_weighted_price(df)
        
        # Price action patterns
        df = ScalpingIndicators.detect_micro_patterns(df)
        df = ScalpingIndicators.support_resistance_micro(df)
        df = ScalpingIndicators.momentum_divergence(df)
        
        # Order flow approximation
        df = ScalpingIndicators.order_flow_intensity(df)
        df = ScalpingIndicators.smart_money_tracker(df)
        
        return df
    
    @staticmethod
    def fast_rsi(df, period=7):
        """Fast RSI optimized for scalping"""
        df = df.copy()
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        return df
    
    @staticmethod
    def stochastic_fast(df, k_period=5, d_period=3):
        """Fast stochastic for quick overbought/oversold signals"""
        df = df.copy()
        low_min = df['low'].rolling(window=k_period).min()
        high_max = df['high'].rolling(window=k_period).max()
        df['stoch_k'] = 100 * ((df['close'] - low_min) / (high_max - low_min))
        df['stoch_d'] = df['stoch_k'].rolling(window=d_period).mean()
        return df
    
    @staticmethod
    def macd_fast(df, fast=5, slow=13, signal=4):
        """Fast MACD for quick momentum signals"""
        df = df.copy()
        ema_fast = df['close'].ewm(span=fast).mean()
        ema_slow = df['close'].ewm(span=slow).mean()
        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd'].ewm(span=signal).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        return df
    
    @staticmethod
    def price_velocity(df, period=3):
        """Calculate price velocity for momentum detection"""
        df = df.copy()
        df['price_change'] = df['close'].diff()
        df['price_velocity'] = df['price_change'].rolling(window=period).mean()
        df['velocity_percentile'] = df['price_velocity'].rolling(window=50).rank(pct=True)
        return df
    
    @staticmethod
    def price_acceleration(df, period=3):
        """Calculate price acceleration for momentum changes"""
        df = df.copy()
        if 'price_velocity' not in df.columns:
            df = ScalpingIndicators.price_velocity(df, period)
        df['price_acceleration'] = df['price_velocity'].diff()
        df['acceleration_signal'] = np.where(
            df['price_acceleration'] > df['price_acceleration'].rolling(window=10).std(),
            1, np.where(
                df['price_acceleration'] < -df['price_acceleration'].rolling(window=10).std(),
                -1, 0
            )
        )
        return df
    
    @staticmethod
    def realized_volatility(df, period=10):
        """Calculate realized volatility for scalping conditions"""
        df = df.copy()
        returns = df['close'].pct_change()
        df['realized_vol'] = returns.rolling(window=period).std() * np.sqrt(period)
        df['vol_percentile'] = df['realized_vol'].rolling(window=50).rank(pct=True)
        df['vol_regime'] = np.where(df['vol_percentile'] > 0.8, 'high',
                                   np.where(df['vol_percentile'] < 0.2, 'low', 'normal'))
        return df
    
    @staticmethod
    def bollinger_bands_fast(df, period=10, std_dev=1.5):
        """Fast Bollinger Bands for scalping entries"""
        df = df.copy()
        df['bb_middle'] = df['close'].rolling(window=period).mean()
        bb_std = df['close'].rolling(window=period).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * std_dev)
        df['bb_lower'] = df['bb_middle'] - (bb_std * std_dev)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        df['bb_squeeze'] = (df['bb_upper'] - df['bb_lower']) < df['bb_middle'] * 0.02
        return df
    
    @staticmethod
    def atr_fast(df, period=7):
        """Fast ATR for quick volatility assessment"""
        df = df.copy()
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(window=period).mean()
        df['atr_ratio'] = df['atr'] / df['close']
        return df
    
    @staticmethod
    def volume_spike_detector(df, threshold=2.0):
        """Detect volume spikes for breakout confirmation"""
        df = df.copy()
        if 'volume' in df.columns:
            df['volume_ma'] = df['volume'].rolling(window=20).mean()
            df['volume_spike'] = df['volume'] > (df['volume_ma'] * threshold)
            df['volume_ratio'] = df['volume'] / df['volume_ma']
        else:
            # Simulate volume based on price action
            df['synthetic_volume'] = (df['high'] - df['low']) * abs(df['close'] - df['open'])
            df['volume_ma'] = df['synthetic_volume'].rolling(window=20).mean()
            df['volume_spike'] = df['synthetic_volume'] > (df['volume_ma'] * threshold)
            df['volume_ratio'] = df['synthetic_volume'] / df['volume_ma']
        return df
    
    @staticmethod
    def volume_weighted_price(df):
        """Calculate VWAP approximation for institutional levels"""
        df = df.copy()
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        
        if 'volume' in df.columns:
            df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()
        else:
            # Use tick volume approximation
            df['tick_volume'] = df['high'] - df['low'] + abs(df['close'] - df['open'])
            df['vwap'] = (df['typical_price'] * df['tick_volume']).rolling(window=50).sum() / \
                        df['tick_volume'].rolling(window=50).sum()
        
        df['vwap_distance'] = (df['close'] - df['vwap']) / df['vwap']
        return df
    
    @staticmethod
    def detect_micro_patterns(df):
        """Detect micro price action patterns for scalping"""
        df = df.copy()
        
        # Inside bars
        df['inside_bar'] = (df['high'] < df['high'].shift(1)) & (df['low'] > df['low'].shift(1))
        
        # Outside bars
        df['outside_bar'] = (df['high'] > df['high'].shift(1)) & (df['low'] < df['low'].shift(1))
        
        # Doji patterns
        body_size = abs(df['close'] - df['open'])
        candle_range = df['high'] - df['low']
        df['doji'] = body_size < (candle_range * 0.1)
        
        # Hammer patterns
        lower_shadow = df['low'] - np.minimum(df['open'], df['close'])
        upper_shadow = df['high'] - np.maximum(df['open'], df['close'])
        df['hammer'] = (lower_shadow > body_size * 2) & (upper_shadow < body_size * 0.5)
        df['inverted_hammer'] = (upper_shadow > body_size * 2) & (lower_shadow < body_size * 0.5)
        
        # Pin bars
        df['bullish_pin'] = df['hammer'] & (df['close'] > df['open'])
        df['bearish_pin'] = df['inverted_hammer'] & (df['close'] < df['open'])
        
        return df
    
    @staticmethod
    def support_resistance_micro(df, period=10):
        """Identify micro support/resistance levels"""
        df = df.copy()
        
        # Calculate pivot points
        high_pivot = df['high'].rolling(window=period, center=True).max() == df['high']
        low_pivot = df['low'].rolling(window=period, center=True).min() == df['low']
        
        df['resistance_level'] = np.where(high_pivot, df['high'], np.nan)
        df['support_level'] = np.where(low_pivot, df['low'], np.nan)
        
        # Forward fill the levels
        df['resistance_level'] = df['resistance_level'].fillna(method='ffill')
        df['support_level'] = df['support_level'].fillna(method='ffill')
        
        # Check for breaks
        df['resistance_broken'] = df['close'] > df['resistance_level'].shift(1)
        df['support_broken'] = df['close'] < df['support_level'].shift(1)
        
        # Distance to levels
        df['resistance_distance'] = (df['resistance_level'] - df['close']) / df['close']
        df['support_distance'] = (df['close'] - df['support_level']) / df['close']
        
        return df
    
    @staticmethod
    def momentum_divergence(df):
        """Detect momentum divergence for reversal signals"""
        df = df.copy()
        
        # Ensure we have RSI
        if 'rsi' not in df.columns:
            df = ScalpingIndicators.fast_rsi(df)
        
        # Find recent highs and lows
        price_highs = df['high'].rolling(window=5, center=True).max() == df['high']
        price_lows = df['low'].rolling(window=5, center=True).min() == df['low']
        
        # Check for divergence
        df['bullish_divergence'] = False
        df['bearish_divergence'] = False
        
        for i in range(10, len(df)):
            if price_lows.iloc[i]:
                # Look for previous low
                prev_lows = price_lows.iloc[i-10:i]
                if prev_lows.any():
                    prev_low_idx = prev_lows.idxmax()
                    if (df['low'].iloc[i] < df.loc[prev_low_idx, 'low'] and
                        df['rsi'].iloc[i] > df.loc[prev_low_idx, 'rsi']):
                        df.loc[df.index[i], 'bullish_divergence'] = True
            
            if price_highs.iloc[i]:
                # Look for previous high
                prev_highs = price_highs.iloc[i-10:i]
                if prev_highs.any():
                    prev_high_idx = prev_highs.idxmax()
                    if (df['high'].iloc[i] > df.loc[prev_high_idx, 'high'] and
                        df['rsi'].iloc[i] < df.loc[prev_high_idx, 'rsi']):
                        df.loc[df.index[i], 'bearish_divergence'] = True
        
        return df
    
    @staticmethod
    def order_flow_intensity(df):
        """Approximate order flow intensity for institutional activity"""
        df = df.copy()
        
        # Calculate buying/selling pressure
        df['buying_pressure'] = np.where(df['close'] > df['open'],
                                        (df['close'] - df['low']) / (df['high'] - df['low']),
                                        0.5)
        df['selling_pressure'] = np.where(df['close'] < df['open'],
                                         (df['high'] - df['close']) / (df['high'] - df['low']),
                                         0.5)
        
        # Order flow intensity
        df['order_flow_intensity'] = df['buying_pressure'] - df['selling_pressure']
        df['flow_momentum'] = df['order_flow_intensity'].rolling(window=5).mean()
        
        # Flow regime
        df['flow_regime'] = np.where(df['flow_momentum'] > 0.3, 'buying',
                                    np.where(df['flow_momentum'] < -0.3, 'selling', 'neutral'))
        
        return df
    
    @staticmethod
    def smart_money_tracker(df):
        """Track smart money activity patterns"""
        df = df.copy()
        
        # Large candle detection (potential institutional activity)
        df['candle_size'] = df['high'] - df['low']
        df['avg_candle_size'] = df['candle_size'].rolling(window=20).mean()
        df['large_candle'] = df['candle_size'] > (df['avg_candle_size'] * 2)
        
        # Absorption pattern (price rejection at levels)
        df['upper_wick'] = df['high'] - np.maximum(df['open'], df['close'])
        df['lower_wick'] = np.minimum(df['open'], df['close']) - df['low']
        df['absorption_top'] = df['upper_wick'] > (df['candle_size'] * 0.6)
        df['absorption_bottom'] = df['lower_wick'] > (df['candle_size'] * 0.6)
        
        # Liquidity sweep approximation
        recent_high = df['high'].rolling(window=10).max()
        recent_low = df['low'].rolling(window=10).min()
        df['liquidity_swept'] = (df['high'] > recent_high.shift(1)) | (df['low'] < recent_low.shift(1))
        
        # Smart money confidence
        smart_signals = (df['large_candle'].astype(int) + 
                        df['absorption_top'].astype(int) + 
                        df['absorption_bottom'].astype(int) +
                        df['liquidity_swept'].astype(int))
        df['smart_money_confidence'] = smart_signals.rolling(window=5).sum() / 5
        
        return df
    
    @staticmethod
    def market_microstructure(df):
        """Analyze market microstructure for scalping edges"""
        df = df.copy()
        
        # Bid-ask spread approximation
        df['spread_proxy'] = (df['high'] - df['low']) / df['close']
        df['tight_spread'] = df['spread_proxy'] < df['spread_proxy'].rolling(window=20).quantile(0.25)
        
        # Order book imbalance approximation
        df['price_efficiency'] = abs(df['close'] - df['open']) / (df['high'] - df['low'])
        df['efficient_pricing'] = df['price_efficiency'] > 0.5
        
        # Tick direction
        df['tick_direction'] = np.where(df['close'] > df['close'].shift(1), 1,
                                       np.where(df['close'] < df['close'].shift(1), -1, 0))
        df['tick_momentum'] = df['tick_direction'].rolling(window=5).sum()
        
        return df 