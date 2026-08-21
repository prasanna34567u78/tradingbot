# Custom SMC/ICT indicators for the Gold Trading Bot

import numpy as np
import pandas as pd


class SMCIndicators:
    """
    Class containing Smart Money Concepts (SMC) and ICT indicators
    """
    
    @staticmethod
    def identify_swing_points(df, window=5):
        """
        Identify swing high and swing low points
        
        Args:
            df: DataFrame with OHLC data
            window: Window size for identifying swings
            
        Returns:
            DataFrame with swing high and swing low columns
        """
        df = df.copy()
        
        # Initialize swing columns
        df['swing_high'] = False
        df['swing_low'] = False
        
        # Identify swing highs
        for i in range(window, len(df) - window):
            if all(df['high'].iloc[i] > df['high'].iloc[i-window:i]) and \
               all(df['high'].iloc[i] > df['high'].iloc[i+1:i+window+1]):
                df.loc[df.index[i], 'swing_high'] = True
        
        # Identify swing lows
        for i in range(window, len(df) - window):
            if all(df['low'].iloc[i] < df['low'].iloc[i-window:i]) and \
               all(df['low'].iloc[i] < df['low'].iloc[i+1:i+window+1]):
                df.loc[df.index[i], 'swing_low'] = True
        
        return df
    
    @staticmethod
    def identify_market_structure(df):
        """
        Identify market structure (higher highs, lower lows, etc.)
        
        Args:
            df: DataFrame with swing points identified
            
        Returns:
            DataFrame with market structure columns
        """
        df = df.copy()
        
        # Initialize market structure columns
        df['higher_high'] = False
        df['lower_high'] = False
        df['higher_low'] = False
        df['lower_low'] = False
        df['bos_bullish'] = False  # Break of structure (bullish)
        df['bos_bearish'] = False  # Break of structure (bearish)
        
        # Find consecutive swing highs and lows
        swing_highs = df[df['swing_high']].index
        swing_lows = df[df['swing_low']].index
        
        # Analyze swing highs
        for i in range(1, len(swing_highs)):
            current_idx = swing_highs[i]
            prev_idx = swing_highs[i-1]
            
            if df.loc[current_idx, 'high'] > df.loc[prev_idx, 'high']:
                df.loc[current_idx, 'higher_high'] = True
            else:
                df.loc[current_idx, 'lower_high'] = True
        
        # Analyze swing lows
        for i in range(1, len(swing_lows)):
            current_idx = swing_lows[i]
            prev_idx = swing_lows[i-1]
            
            if df.loc[current_idx, 'low'] > df.loc[prev_idx, 'low']:
                df.loc[current_idx, 'higher_low'] = True
            else:
                df.loc[current_idx, 'lower_low'] = True
        
        # Identify break of structure
        for i in range(1, len(df)):
            # Bullish BOS: price breaks above a significant swing high after making lower lows
            if df.iloc[i-1]['lower_low'] and df.iloc[i]['close'] > df.iloc[i-1]['high']:
                df.loc[df.index[i], 'bos_bullish'] = True
            
            # Bearish BOS: price breaks below a significant swing low after making higher highs
            if df.iloc[i-1]['higher_high'] and df.iloc[i]['close'] < df.iloc[i-1]['low']:
                df.loc[df.index[i], 'bos_bearish'] = True
        
        return df
    
    @staticmethod
    def identify_order_blocks(df, window=5):
        """
        Identify bullish and bearish order blocks
        
        Args:
            df: DataFrame with OHLC data
            window: Window size for order block identification
            
        Returns:
            DataFrame with order block columns
        """
        df = df.copy()
        
        # Initialize order block columns
        df['bullish_ob'] = False
        df['bearish_ob'] = False
        df['bullish_ob_high'] = np.nan
        df['bullish_ob_low'] = np.nan
        df['bearish_ob_high'] = np.nan
        df['bearish_ob_low'] = np.nan
        
        # Identify bullish order blocks (last down candle before a strong move up)
        for i in range(window, len(df) - window):
            # Check for a strong bullish move
            if df.iloc[i+1:i+window+1]['close'].max() > df.iloc[i]['high'] * 1.005:  # 0.5% move up
                # Look for the last bearish candle
                for j in range(i, i-window, -1):
                    if df.iloc[j]['close'] < df.iloc[j]['open']:  # Bearish candle
                        df.loc[df.index[j], 'bullish_ob'] = True
                        df.loc[df.index[j], 'bullish_ob_high'] = df.iloc[j]['high']
                        df.loc[df.index[j], 'bullish_ob_low'] = df.iloc[j]['low']
                        break
        
        # Identify bearish order blocks (last up candle before a strong move down)
        for i in range(window, len(df) - window):
            # Check for a strong bearish move
            if df.iloc[i+1:i+window+1]['close'].min() < df.iloc[i]['low'] * 0.995:  # 0.5% move down
                # Look for the last bullish candle
                for j in range(i, i-window, -1):
                    if df.iloc[j]['close'] > df.iloc[j]['open']:  # Bullish candle
                        df.loc[df.index[j], 'bearish_ob'] = True
                        df.loc[df.index[j], 'bearish_ob_high'] = df.iloc[j]['high']
                        df.loc[df.index[j], 'bearish_ob_low'] = df.iloc[j]['low']
                        break
        
        return df
    
    @staticmethod
    def identify_fair_value_gaps(df):
        """
        Identify fair value gaps (FVGs)
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with FVG columns
        """
        df = df.copy()
        
        # Initialize FVG columns
        df['bullish_fvg'] = False
        df['bearish_fvg'] = False
        df['bullish_fvg_high'] = np.nan
        df['bullish_fvg_low'] = np.nan
        df['bearish_fvg_high'] = np.nan
        df['bearish_fvg_low'] = np.nan
        
        # Identify bullish FVGs (gap up)
        for i in range(2, len(df)):
            if df.iloc[i-2]['high'] < df.iloc[i]['low']:  # Gap up
                df.loc[df.index[i-1], 'bullish_fvg'] = True
                df.loc[df.index[i-1], 'bullish_fvg_high'] = df.iloc[i]['low']
                df.loc[df.index[i-1], 'bullish_fvg_low'] = df.iloc[i-2]['high']
        
        # Identify bearish FVGs (gap down)
        for i in range(2, len(df)):
            if df.iloc[i-2]['low'] > df.iloc[i]['high']:  # Gap down
                df.loc[df.index[i-1], 'bearish_fvg'] = True
                df.loc[df.index[i-1], 'bearish_fvg_high'] = df.iloc[i-2]['low']
                df.loc[df.index[i-1], 'bearish_fvg_low'] = df.iloc[i]['high']
        
        return df
    
    @staticmethod
    def identify_liquidity_levels(df, window=10):
        """
        Identify liquidity levels (clusters of swing highs/lows)
        
        Args:
            df: DataFrame with swing points identified
            window: Window size for liquidity level identification
            
        Returns:
            DataFrame with liquidity level columns
        """
        df = df.copy()
        
        # Initialize liquidity level columns
        df['liquidity_high'] = False
        df['liquidity_low'] = False
        
        # Find clusters of swing highs (liquidity above)
        swing_highs = df[df['swing_high']].index
        for i in range(len(swing_highs) - 1):
            current_high = df.loc[swing_highs[i], 'high']
            next_high = df.loc[swing_highs[i+1], 'high']
            
            # If swing highs are within 0.2% of each other, mark as liquidity level
            if abs(current_high - next_high) / current_high < 0.002:
                df.loc[swing_highs[i], 'liquidity_high'] = True
                df.loc[swing_highs[i+1], 'liquidity_high'] = True
        
        # Find clusters of swing lows (liquidity below)
        swing_lows = df[df['swing_low']].index
        for i in range(len(swing_lows) - 1):
            current_low = df.loc[swing_lows[i], 'low']
            next_low = df.loc[swing_lows[i+1], 'low']
            
            # If swing lows are within 0.2% of each other, mark as liquidity level
            if abs(current_low - next_low) / current_low < 0.002:
                df.loc[swing_lows[i], 'liquidity_low'] = True
                df.loc[swing_lows[i+1], 'liquidity_low'] = True
        
        return df
    
    @staticmethod
    def identify_liquidity_sweep(df):
        """
        Identify liquidity sweeps (price taking out liquidity levels and reversing)
        
        Args:
            df: DataFrame with liquidity levels identified
            
        Returns:
            DataFrame with liquidity sweep columns
        """
        df = df.copy()
        
        # Initialize liquidity sweep columns
        df['sweep_high'] = False
        df['sweep_low'] = False
        
        # Identify high sweeps (price takes out liquidity high and reverses down)
        liquidity_highs = df[df['liquidity_high']].index
        for idx in liquidity_highs:
            i = df.index.get_loc(idx)
            if i + 3 < len(df):  # Ensure we have enough bars after the liquidity level
                liq_price = df.loc[idx, 'high']
                
                # Check if price exceeds the liquidity level
                if df.iloc[i+1:i+3]['high'].max() > liq_price:
                    # Check if price reverses down after taking out liquidity
                    if df.iloc[i+3]['close'] < df.iloc[i+2]['low']:
                        df.loc[df.index[i+2], 'sweep_high'] = True
        
        # Identify low sweeps (price takes out liquidity low and reverses up)
        liquidity_lows = df[df['liquidity_low']].index
        for idx in liquidity_lows:
            i = df.index.get_loc(idx)
            if i + 3 < len(df):  # Ensure we have enough bars after the liquidity level
                liq_price = df.loc[idx, 'low']
                
                # Check if price exceeds the liquidity level
                if df.iloc[i+1:i+3]['low'].min() < liq_price:
                    # Check if price reverses up after taking out liquidity
                    if df.iloc[i+3]['close'] > df.iloc[i+2]['high']:
                        df.loc[df.index[i+2], 'sweep_low'] = True
        
        return df
    
    @staticmethod
    def identify_displacement(df, threshold=0.001):
        """
        Identify displacement moves (strong momentum moves)
        """
        df = df.copy()
        
        # Initialize displacement columns
        df['bullish_displacement'] = False
        df['bearish_displacement'] = False
        df['displacement_strength'] = 0.0
        
        # Calculate candle body percentage
        df['body_pct'] = abs(df['close'] - df['open']) / df['open']
        
        # Identify displacement candles
        for i in range(1, len(df)):
            body_pct = df.iloc[i]['body_pct']
            prev_body_pct = df.iloc[i-1]['body_pct']
            
            # Strong bullish displacement
            if (df.iloc[i]['close'] > df.iloc[i]['open'] and 
                body_pct > threshold and 
                body_pct > prev_body_pct * 2):
                df.loc[df.index[i], 'bullish_displacement'] = True
                df.loc[df.index[i], 'displacement_strength'] = body_pct
            
            # Strong bearish displacement
            elif (df.iloc[i]['close'] < df.iloc[i]['open'] and 
                  body_pct > threshold and 
                  body_pct > prev_body_pct * 2):
                df.loc[df.index[i], 'bearish_displacement'] = True
                df.loc[df.index[i], 'displacement_strength'] = body_pct
        
        return df
    
    @staticmethod
    def identify_change_of_character(df, window=20):
        """
        Identify Change of Character (ChoCh) - more subtle than BOS
        """
        df = df.copy()
        
        # Initialize ChoCh columns
        df['choch_bullish'] = False
        df['choch_bearish'] = False
        
        # Get swing points
        swing_highs = df[df['swing_high'] == True]['high']
        swing_lows = df[df['swing_low'] == True]['low']
        
        # Identify bullish ChoCh (failure to make new low)
        for i in range(window, len(df)):
            recent_lows = swing_lows.iloc[-3:] if len(swing_lows) >= 3 else swing_lows
            if len(recent_lows) >= 2:
                if recent_lows.iloc[-1] > recent_lows.iloc[-2]:  # Higher low
                    df.loc[df.index[i], 'choch_bullish'] = True
        
        # Identify bearish ChoCh (failure to make new high)
        for i in range(window, len(df)):
            recent_highs = swing_highs.iloc[-3:] if len(swing_highs) >= 3 else swing_highs
            if len(recent_highs) >= 2:
                if recent_highs.iloc[-1] < recent_highs.iloc[-2]:  # Lower high
                    df.loc[df.index[i], 'choch_bearish'] = True
        
        return df
    
    @staticmethod
    def apply_all_indicators(df):
        """
        Apply all SMC/ICT indicators to the dataframe
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with all indicators applied
        """
        # Apply basic swing points first (required for other indicators)
        df = SMCIndicators.identify_swing_points(df)
        
        # Apply market structure analysis
        df = SMCIndicators.identify_market_structure(df)
        
        # Apply order blocks and fair value gaps
        df = SMCIndicators.identify_order_blocks(df)
        df = SMCIndicators.identify_fair_value_gaps(df)
        
        # Apply liquidity analysis
        df = SMCIndicators.identify_liquidity_levels(df)
        df = SMCIndicators.identify_liquidity_sweep(df)
        
        # Apply enhanced ICT concepts
        df = SMCIndicators.identify_displacement(df)
        df = SMCIndicators.identify_change_of_character(df)
        
        return df