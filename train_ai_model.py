#!/usr/bin/env python3
"""
AI Model Training Script for Gold Trading Bot

This script trains the AI model with real historical data from the last month
and saves the trained model and scaler for use by the trading bot.

Usage: python train_ai_model.py
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib

# Import our modules
from mt5_executor import MT5Executor
from indicators import SMCIndicators
import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('model_training.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('ai_model_trainer')

class AIModelTrainer:
    """
    Standalone AI model trainer for gold trading bot
    """
    
    def __init__(self):
        self.feature_names = [
            'price_range', 'body_size', 'upper_wick', 'lower_wick',
            'atr', 'momentum', 'has_bos_bullish', 'has_bos_bearish',
            'has_ob_bullish', 'has_ob_bearish', 'has_fvg_bullish',
            'has_fvg_bearish', 'volatility', 'avg_range'
        ]
        
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        
        self.scaler = StandardScaler()
        self.indicators = SMCIndicators()
        
        # Paths
        self.model_path = 'models/trade_validator.joblib'
        self.scaler_path = 'models/scaler.joblib'
        self.training_data_path = 'models/training_data.csv'
        
        # Create models directory
        os.makedirs('models', exist_ok=True)
        
    def fetch_historical_data(self, mt5_executor):
        """
        Fetch historical data for multiple timeframes
        """
        logger.info("Fetching historical data for model training...")
        
        timeframes = {
            '15m': 2880,  # 30 days of 15-minute data
            '1h': 720,    # 30 days of hourly data  
            '4h': 180     # 30 days of 4-hour data
        }
        
        all_data = {}
        
        for tf, limit in timeframes.items():
            logger.info(f"Fetching {tf} data ({limit} candles)...")
            
            df = mt5_executor.fetch_historical_data_mt5(tf, limit)
            if df is not None and len(df) >= 100:
                logger.info(f"Successfully fetched {len(df)} candles for {tf}")
                all_data[tf] = df
            else:
                logger.warning(f"Insufficient data for {tf} timeframe")
        
        return all_data
    
    def add_technical_indicators(self, df):
        """
        Add technical indicators to the dataframe
        """
        try:
            # Apply SMC indicators
            df = self.indicators.apply_all_indicators(df)
            
            # Calculate ATR
            df['tr'] = np.maximum(
                df['high'] - df['low'],
                np.maximum(
                    abs(df['high'] - df['close'].shift(1)),
                    abs(df['low'] - df['close'].shift(1))
                )
            )
            df['atr'] = df['tr'].rolling(window=14).mean()
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding indicators: {e}")
            # Add basic indicators as fallback
            return self._add_basic_indicators(df)
    
    def _add_basic_indicators(self, df):
        """
        Add basic indicators as fallback
        """
        try:
            # Calculate ATR
            df['tr'] = np.maximum(
                df['high'] - df['low'],
                np.maximum(
                    abs(df['high'] - df['close'].shift(1)),
                    abs(df['low'] - df['close'].shift(1))
                )
            )
            df['atr'] = df['tr'].rolling(window=14).mean()
            
            # Add basic structure indicators (simplified)
            df['bos_bullish'] = (df['close'] > df['high'].shift(5)).astype(int)
            df['bos_bearish'] = (df['close'] < df['low'].shift(5)).astype(int)
            
            # Simple order block detection
            df['bullish_ob'] = ((df['close'] > df['open']) & 
                               (df['close'].shift(1) < df['open'].shift(1))).astype(int)
            df['bearish_ob'] = ((df['close'] < df['open']) & 
                               (df['close'].shift(1) > df['open'].shift(1))).astype(int)
            
            # Simple FVG detection
            df['bullish_fvg'] = (df['low'] > df['high'].shift(2)).astype(int)
            df['bearish_fvg'] = (df['high'] < df['low'].shift(2)).astype(int)
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding basic indicators: {e}")
            return df
    
    def prepare_features(self, df):
        """
        Prepare features for training
        """
        try:
            features = pd.DataFrame(index=df.index)
            
            # Price action features
            features['price_range'] = df['high'] - df['low']
            features['body_size'] = abs(df['close'] - df['open'])
            features['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
            features['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
            
            # Technical indicators
            features['atr'] = df.get('atr', 1.0)
            features['momentum'] = df['close'] - df['close'].shift(5)
            
            # Market structure features
            features['has_bos_bullish'] = df.get('bos_bullish', 0).astype(int)
            features['has_bos_bearish'] = df.get('bos_bearish', 0).astype(int)
            features['has_ob_bullish'] = df.get('bullish_ob', 0).astype(int)
            features['has_ob_bearish'] = df.get('bearish_ob', 0).astype(int)
            features['has_fvg_bullish'] = df.get('bullish_fvg', 0).astype(int)
            features['has_fvg_bearish'] = df.get('bearish_fvg', 0).astype(int)
            
            # Enhanced features
            features['volatility'] = features['atr'] / df['close']
            features['avg_range'] = features['price_range'].rolling(10).mean()
            
            # Ensure all features are present and in correct order
            features = features[self.feature_names].fillna(0)
            
            return features
            
        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            return pd.DataFrame(columns=self.feature_names)
    
    def create_targets(self, df, future_periods=10):
        """
        Create training targets based on future price movement
        """
        try:
            # Look ahead to see if price moves favorably
            future_high = df['high'].shift(-future_periods).rolling(future_periods).max()
            future_low = df['low'].shift(-future_periods).rolling(future_periods).min()
            current_close = df['close']
            
            # Calculate ATR for dynamic thresholds
            atr = df.get('atr', pd.Series([1.0] * len(df), index=df.index))
            
            # Define successful trade conditions
            # For bullish trades: price moves up by at least 1x ATR
            bullish_success = (future_high > current_close + atr * 1.0)
            
            # For bearish trades: price moves down by at least 1x ATR  
            bearish_success = (future_low < current_close - atr * 1.0)
            
            # Combine into binary target (1 for any profitable direction, 0 for no clear direction)
            targets = (bullish_success | bearish_success).astype(int)
            
            return targets.fillna(0).values
            
        except Exception as e:
            logger.error(f"Error creating targets: {e}")
            return np.zeros(len(df))
    
    def train_model(self, historical_data):
        """
        Train the AI model with historical data
        """
        logger.info("Starting model training...")
        
        all_features = []
        all_targets = []
        
        # Process each timeframe
        for tf, df in historical_data.items():
            logger.info(f"Processing {tf} data...")
            
            # Add indicators
            df = self.add_technical_indicators(df)
            
            # Prepare features
            features = self.prepare_features(df)
            
            # Create targets
            targets = self.create_targets(df)
            
            # Filter valid data (remove rows with NaN)
            valid_indices = ~(features.isna().any(axis=1) | pd.isna(targets))
            features_clean = features[valid_indices]
            targets_clean = targets[valid_indices]
            
            if len(features_clean) > 0:
                all_features.append(features_clean)
                all_targets.extend(targets_clean)
                logger.info(f"Added {len(features_clean)} training samples from {tf}")
        
        if not all_features:
            raise ValueError("No valid training data available")
        
        # Combine all data
        combined_features = pd.concat(all_features, ignore_index=True)
        combined_targets = np.array(all_targets)
        
        logger.info(f"Total training samples: {len(combined_features)}")
        logger.info(f"Positive samples: {sum(combined_targets)}")
        logger.info(f"Negative samples: {len(combined_targets) - sum(combined_targets)}")
        
        # Save training data
        training_data = combined_features.copy()
        training_data['target'] = combined_targets
        training_data.to_csv(self.training_data_path, index=False)
        logger.info(f"Training data saved to {self.training_data_path}")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            combined_features, combined_targets,
            test_size=0.2, random_state=42, stratify=combined_targets
        )
        
        # Scale features
        logger.info("Scaling features...")
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        logger.info("Training Random Forest model...")
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate model
        train_score = self.model.score(X_train_scaled, y_train)
        test_score = self.model.score(X_test_scaled, y_test)
        
        # Predictions for detailed evaluation
        y_pred = self.model.predict(X_test_scaled)
        
        logger.info("=" * 50)
        logger.info("MODEL TRAINING RESULTS")
        logger.info("=" * 50)
        logger.info(f"Training accuracy: {train_score:.3f}")
        logger.info(f"Testing accuracy: {test_score:.3f}")
        logger.info(f"Training samples: {len(X_train)}")
        logger.info(f"Testing samples: {len(X_test)}")
        
        # Print classification report
        logger.info("\nClassification Report:")
        logger.info(f"\n{classification_report(y_test, y_pred)}")
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        logger.info("\nTop 10 Feature Importances:")
        for _, row in feature_importance.head(10).iterrows():
            logger.info(f"{row['feature']}: {row['importance']:.4f}")
        
        # Save model and scaler
        logger.info(f"\nSaving model to {self.model_path}")
        joblib.dump(self.model, self.model_path)
        
        logger.info(f"Saving scaler to {self.scaler_path}")
        joblib.dump(self.scaler, self.scaler_path)
        
        logger.info("Model training completed successfully!")
        
        return {
            'train_accuracy': train_score,
            'test_accuracy': test_score,
            'feature_importance': feature_importance
        }

def main():
    """
    Main training function
    """
    print("[TRAINING] AI Model Training Script for Gold Trading Bot")
    print("=" * 60)
    
    trainer = AIModelTrainer()
    
    # Initialize MT5 connection
    logger.info("Connecting to MT5...")
    try:
        mt5_executor = MT5Executor(
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER,
            symbol=config.SYMBOL
        )
        
        if not mt5_executor.connected:
            logger.error("Failed to connect to MT5. Please check your credentials.")
            return False
            
        logger.info("Successfully connected to MT5")
        
    except Exception as e:
        logger.error(f"Error connecting to MT5: {e}")
        return False
    
    try:
        # Fetch historical data
        historical_data = trainer.fetch_historical_data(mt5_executor)
        
        if not historical_data:
            logger.error("No historical data available for training")
            return False
        
        # Train model
        results = trainer.train_model(historical_data)
        
        print("\n🎉 Training completed successfully!")
        print(f"📊 Test Accuracy: {results['test_accuracy']:.3f}")
        print(f"💾 Model saved: {trainer.model_path}")
        print(f"📏 Scaler saved: {trainer.scaler_path}")
        print(f"[INFO] Training data: {trainer.training_data_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        return False
    
    finally:
        # Cleanup MT5 connection
        try:
            mt5_executor.shutdown()
        except:
            pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 