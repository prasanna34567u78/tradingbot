#!/usr/bin/env python3
"""
Simple AI Model Training Script - Fix session_bias error
"""

import os
import logging
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib

from mt5_executor import MT5Executor
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('model_trainer')

def main():
    """Train AI model with real historical data"""
    print("[TRAINING] AI Model with Historical Data")
    print("=" * 50)
    
    # Create models directory
    os.makedirs('models', exist_ok=True)
    
    # Feature names (14 features only - no session_bias)
    feature_names = [
        'price_range', 'body_size', 'upper_wick', 'lower_wick',
        'atr', 'momentum', 'has_bos_bullish', 'has_bos_bearish',
        'has_ob_bullish', 'has_ob_bearish', 'has_fvg_bullish',
        'has_fvg_bearish', 'volatility', 'avg_range'
    ]
    
    try:
        # Connect to MT5
        logger.info("Connecting to MT5...")
        mt5 = MT5Executor(
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD, 
            server=config.MT5_SERVER,
            symbol=config.SYMBOL
        )
        
        if not mt5.connected:
            logger.warning("MT5 not connected, using synthetic data")
            # Create synthetic training data
            n_samples = 1000
            np.random.seed(42)
            
            features_data = {
                'price_range': np.random.uniform(0.1, 2.0, n_samples),
                'body_size': np.random.uniform(0.05, 1.5, n_samples),
                'upper_wick': np.random.uniform(0, 0.5, n_samples),
                'lower_wick': np.random.uniform(0, 0.5, n_samples),
                'atr': np.random.uniform(0.1, 1.0, n_samples),
                'momentum': np.random.uniform(-1.0, 1.0, n_samples),
                'has_bos_bullish': np.random.randint(0, 2, n_samples),
                'has_bos_bearish': np.random.randint(0, 2, n_samples),
                'has_ob_bullish': np.random.randint(0, 2, n_samples),
                'has_ob_bearish': np.random.randint(0, 2, n_samples),
                'has_fvg_bullish': np.random.randint(0, 2, n_samples),
                'has_fvg_bearish': np.random.randint(0, 2, n_samples),
                'volatility': np.random.uniform(0.001, 0.05, n_samples),
                'avg_range': np.random.uniform(0.1, 2.0, n_samples)
            }
            
            features = pd.DataFrame(features_data)
            
            # Create targets
            targets = np.zeros(n_samples)
            for i in range(n_samples):
                score = 0
                if features.loc[i, 'momentum'] > 0 and features.loc[i, 'has_ob_bullish']:
                    score += 2
                if 0.01 < features.loc[i, 'volatility'] < 0.03:
                    score += 1
                targets[i] = 1 if score >= 2 else 0
                
        else:
            logger.info("Fetching historical data...")
            # Get 1 month of 15m data
            df = mt5.fetch_historical_data_mt5('15m', 2880)
            if df is None:
                raise ValueError("No historical data available")
            
            # Calculate basic features
            features = pd.DataFrame()
            features['price_range'] = df['high'] - df['low']
            features['body_size'] = abs(df['close'] - df['open'])
            features['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
            features['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
            
            # ATR
            tr = np.maximum(df['high'] - df['low'],
                          np.maximum(abs(df['high'] - df['close'].shift(1)),
                                   abs(df['low'] - df['close'].shift(1))))
            features['atr'] = tr.rolling(14).mean()
            features['momentum'] = df['close'] - df['close'].shift(5)
            
            # Basic structure indicators
            features['has_bos_bullish'] = (df['close'] > df['high'].shift(5)).astype(int)
            features['has_bos_bearish'] = (df['close'] < df['low'].shift(5)).astype(int)
            features['has_ob_bullish'] = ((df['close'] > df['open']) & 
                                        (df['close'].shift(1) < df['open'].shift(1))).astype(int)
            features['has_ob_bearish'] = ((df['close'] < df['open']) & 
                                        (df['close'].shift(1) > df['open'].shift(1))).astype(int)
            features['has_fvg_bullish'] = (df['low'] > df['high'].shift(2)).astype(int)
            features['has_fvg_bearish'] = (df['high'] < df['low'].shift(2)).astype(int)
            
            features['volatility'] = features['atr'] / df['close']
            features['avg_range'] = features['price_range'].rolling(10).mean()
            
            # Ensure correct order and clean data
            features = features[feature_names].fillna(0).dropna()
            
            # Create targets based on future price movement
            future_high = df['high'].shift(-10).rolling(10).max()
            current_close = df['close']
            atr = features['atr']
            
            targets = (future_high > current_close + atr * 1.0).astype(int)
            targets = targets.fillna(0).iloc[:len(features)]
        
        # Train model
        logger.info("Training model...")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features, targets, test_size=0.2, random_state=42
        )
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train model
        model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
        model.fit(X_train_scaled, y_train)
        
        # Evaluate
        train_score = model.score(X_train_scaled, y_train)
        test_score = model.score(X_test_scaled, y_test)
        
        logger.info(f"Training accuracy: {train_score:.3f}")
        logger.info(f"Testing accuracy: {test_score:.3f}")
        
        # Save model and scaler
        model_path = 'models/trade_validator.joblib'
        scaler_path = 'models/scaler.joblib'
        
        joblib.dump(model, model_path)
        joblib.dump(scaler, scaler_path)
        
        print(f"[SUCCESS] Model trained and saved successfully!")
        print(f"📊 Test Accuracy: {test_score:.3f}")
        print(f"💾 Model: {model_path}")
        print(f"📏 Scaler: {scaler_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        return False
    
    finally:
        try:
            if 'mt5' in locals():
                mt5.shutdown()
        except:
            pass

if __name__ == "__main__":
    main() 