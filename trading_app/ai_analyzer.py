import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib
import logging
import os
import json
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
import config

# Add OpenAI import with error handling
try:
    from openai import OpenAI, AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI package not available. OpenAI features will be disabled.")

logger = logging.getLogger('gold_trading_bot')

class OpenAIAnalyzer:
    """
    OpenAI-powered market analysis and trade suggestions
    """
    def __init__(self):
        self.enabled = (OPENAI_AVAILABLE and 
                       bool(config.OPENAI_API_KEY) and 
                       config.AI_SETTINGS.get('enable_openai', False))
        if self.enabled:
            self.client = OpenAI(api_key=config.OPENAI_API_KEY)
            self.async_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            logger.info("OpenAI analyzer initialized")
        else:
            self.client = None
            self.async_client = None
            logger.warning("OpenAI analyzer disabled - API key not configured, package unavailable, or disabled in config")
    
    async def analyze_market_sentiment(self, market_data, timeframe_analysis):
        """
        Analyze market sentiment using OpenAI
        
        Args:
            market_data: Current market data
            timeframe_analysis: Multi-timeframe analysis results
            
        Returns:
            dict with sentiment analysis
        """
        if not self.enabled:
            return {'sentiment': 'neutral', 'confidence': 0.5, 'reasoning': 'OpenAI not available'}
        
        try:
            # Prepare market summary for OpenAI
            market_summary = self._prepare_market_summary(market_data, timeframe_analysis)
            
            prompt = f"""
            As an expert ICT/SMC trader, analyze the following gold market data and provide sentiment analysis:

            Market Summary:
            {market_summary}

            Provide analysis in JSON format with:
            1. sentiment: 'bullish', 'bearish', or 'neutral'
            2. confidence: 0.0-1.0
            3. key_factors: list of key factors influencing sentiment
            4. risk_assessment: 'low', 'medium', 'high'
            5. time_horizon: suggested time horizon for the sentiment
            6. reasoning: brief explanation of the analysis

            Focus on ICT concepts like liquidity sweeps, order blocks, fair value gaps, and market structure.
            """
            
            # Try primary model first, then fallback models
            models_to_try = [config.OPENAI_MODEL, 'gpt-4o-mini', 'gpt-3.5-turbo']
            response = None
            
            for model in models_to_try:
                try:
                    response = await self.async_client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": "You are an expert ICT/SMC forex trader specializing in gold trading."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=config.OPENAI_MAX_TOKENS,
                        temperature=config.OPENAI_TEMPERATURE
                    )
                    break
                except Exception as model_error:
                    logger.warning(f"Async model {model} failed: {str(model_error)}")
                    continue
            
            if response is None:
                raise Exception("All async OpenAI models failed")
            
            analysis = json.loads(response.choices[0].message.content)
            logger.info(f"OpenAI sentiment analysis: {analysis['sentiment']} (confidence: {analysis['confidence']})")
            return analysis
            
        except Exception as e:
            logger.error(f"Error in OpenAI sentiment analysis: {str(e)}")
            return {'sentiment': 'neutral', 'confidence': 0.5, 'reasoning': f'Analysis error: {str(e)}'}
    
    async def get_trade_suggestion(self, market_data, timeframe_analysis, current_position=None):
        """
        Get trade suggestion from OpenAI based on market analysis
        
        Args:
            market_data: Current market data
            timeframe_analysis: Multi-timeframe analysis results
            current_position: Current open position if any
            
        Returns:
            dict with trade suggestion
        """
        if not self.enabled:
            return {'action': 'hold', 'confidence': 0.5, 'reasoning': 'OpenAI not available'}
        
        try:
            market_summary = self._prepare_market_summary(market_data, timeframe_analysis)
            position_info = f"Current Position: {current_position}" if current_position else "No current position"
            
            prompt = f"""
            As an expert ICT/SMC trader, analyze this gold market data and provide a trade suggestion:

            {market_summary}
            {position_info}

            Consider:
            - Market structure (BOS, ChoCh)
            - Liquidity levels and sweeps
            - Order blocks and fair value gaps
            - Premium/discount areas
            - Market sessions and time of day
            - Risk management

            Provide response in JSON format:
            {{
                "action": "buy|sell|hold|close",
                "confidence": 0.0-1.0,
                "entry_zone": [price_low, price_high],
                "stop_loss": price,
                "take_profit": [tp1, tp2, tp3],
                "risk_reward": ratio,
                "reasoning": "detailed explanation",
                "confluence_factors": ["factor1", "factor2", ...],
                "session_bias": "london|new_york|asian",
                "time_sensitivity": "immediate|wait_for_confirmation|end_of_session"
            }}
            """
            
            # Try primary model first, then fallback models
            models_to_try = [config.OPENAI_MODEL, 'gpt-4o-mini', 'gpt-3.5-turbo']
            response = None
            
            for model in models_to_try:
                try:
                    response = await self.async_client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": "You are an expert ICT/SMC forex trader with 10+ years experience trading gold. Focus on high-probability setups with proper risk management."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=config.OPENAI_MAX_TOKENS,
                        temperature=config.OPENAI_TEMPERATURE
                    )
                    break
                except Exception as model_error:
                    logger.warning(f"Async model {model} failed: {str(model_error)}")
                    continue
            
            if response is None:
                raise Exception("All async OpenAI models failed")
            
            suggestion = json.loads(response.choices[0].message.content)
            logger.info(f"OpenAI trade suggestion: {suggestion['action']} (confidence: {suggestion['confidence']})")
            return suggestion
            
        except Exception as e:
            logger.error(f"Error in OpenAI trade suggestion: {str(e)}")
            return {'action': 'hold', 'confidence': 0.5, 'reasoning': f'Suggestion error: {str(e)}'}
    
    def analyze_market_sentiment_sync(self, market_data, timeframe_analysis):
        """
        Synchronous version of market sentiment analysis using OpenAI
        
        Args:
            market_data: Current market data
            timeframe_analysis: Multi-timeframe analysis results
            
        Returns:
            dict with sentiment analysis
        """
        if not self.enabled:
            logger.debug("OpenAI sentiment analysis skipped - not enabled")
            return {'sentiment': 'neutral', 'confidence': 0.5, 'reasoning': 'OpenAI not available'}
        
        try:
            logger.info("Starting OpenAI sentiment analysis...")
            
            # Prepare market summary for OpenAI
            market_summary = self._prepare_market_summary(market_data, timeframe_analysis)
            logger.debug(f"Market summary prepared for OpenAI: {len(market_summary)} characters")
            
            prompt = f"""
            As an expert ICT/SMC trader, analyze the following gold market data and provide sentiment analysis:

            Market Summary:
            {market_summary}

            Provide analysis in JSON format with:
            1. sentiment: 'bullish', 'bearish', or 'neutral'
            2. confidence: 0.0-1.0
            3. key_factors: list of key factors influencing sentiment
            4. risk_assessment: 'low', 'medium', 'high'
            5. time_horizon: suggested time horizon for the sentiment
            6. reasoning: brief explanation of the analysis

            Focus on ICT concepts like liquidity sweeps, order blocks, fair value gaps, and market structure.
            """
            
            logger.debug("Sending request to OpenAI for sentiment analysis...")
            
            # Try primary model first, then fallback models
            models_to_try = [config.OPENAI_MODEL, 'gpt-4o-mini', 'gpt-3.5-turbo']
            response = None
            
            for model in models_to_try:
                try:
                    logger.debug(f"Trying OpenAI model: {model}")
                    response = self.client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": "You are an expert ICT/SMC forex trader specializing in gold trading."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=config.OPENAI_MAX_TOKENS,
                        temperature=config.OPENAI_TEMPERATURE
                    )
                    logger.debug(f"Successfully used model: {model}")
                    break
                except Exception as model_error:
                    logger.warning(f"Model {model} failed: {str(model_error)}")
                    continue
            
            if response is None:
                raise Exception("All OpenAI models failed")
            
            logger.debug("Received response from OpenAI, parsing analysis...")
            
            analysis = json.loads(response.choices[0].message.content)
            logger.info(f"OpenAI sentiment analysis completed: {analysis['sentiment']} "
                       f"(confidence: {analysis['confidence']:.2f}, risk: {analysis.get('risk_assessment', 'unknown')})")
            logger.debug(f"OpenAI reasoning: {analysis.get('reasoning', 'No reasoning provided')}")
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI sentiment response as JSON: {str(e)}")
            return {'sentiment': 'neutral', 'confidence': 0.5, 'reasoning': f'JSON parse error: {str(e)}'}
        except Exception as e:
            logger.error(f"Error in OpenAI sentiment analysis: {str(e)}")
            return {'sentiment': 'neutral', 'confidence': 0.5, 'reasoning': f'Analysis error: {str(e)}'}
    
    def get_trade_suggestion_sync(self, market_data, timeframe_analysis, current_position=None):
        """
        Synchronous version of trade suggestion from OpenAI
        
        Args:
            market_data: Current market data
            timeframe_analysis: Multi-timeframe analysis results
            current_position: Current open position if any
            
        Returns:
            dict with trade suggestion
        """
        if not self.enabled:
            return {'action': 'hold', 'confidence': 0.5, 'reasoning': 'OpenAI not available'}
        
        try:
            market_summary = self._prepare_market_summary(market_data, timeframe_analysis)
            position_info = f"Current Position: {current_position}" if current_position else "No current position"
            
            prompt = f"""
            As an expert ICT/SMC trader, analyze this gold market data and provide a trade suggestion:

            {market_summary}
            {position_info}

            Consider:
            - Market structure (BOS, ChoCh)
            - Liquidity levels and sweeps
            - Order blocks and fair value gaps
            - Premium/discount areas
            - Market sessions and time of day
            - Risk management

            Provide response in JSON format:
            {{
                "action": "buy|sell|hold|close",
                "confidence": 0.0-1.0,
                "entry_zone": [price_low, price_high],
                "stop_loss": price,
                "take_profit": [tp1, tp2, tp3],
                "risk_reward": ratio,
                "reasoning": "detailed explanation",
                "confluence_factors": ["factor1", "factor2", ...],
                "session_bias": "london|new_york|asian",
                "time_sensitivity": "immediate|wait_for_confirmation|end_of_session"
            }}
            """
            
            # Try primary model first, then fallback models
            models_to_try = [config.OPENAI_MODEL, 'gpt-4o-mini', 'gpt-3.5-turbo']
            response = None
            
            for model in models_to_try:
                try:
                    logger.debug(f"Trying OpenAI model: {model}")
                    response = self.client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": "You are an expert ICT/SMC forex trader with 10+ years experience trading gold. Focus on high-probability setups with proper risk management."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=config.OPENAI_MAX_TOKENS,
                        temperature=config.OPENAI_TEMPERATURE
                    )
                    logger.debug(f"Successfully used model: {model}")
                    break
                except Exception as model_error:
                    logger.warning(f"Model {model} failed: {str(model_error)}")
                    continue
            
            if response is None:
                raise Exception("All OpenAI models failed")
            
            suggestion = json.loads(response.choices[0].message.content)
            logger.info(f"OpenAI trade suggestion: {suggestion['action']} (confidence: {suggestion['confidence']})")
            return suggestion
            
        except Exception as e:
            logger.error(f"Error in OpenAI trade suggestion: {str(e)}")
            return {'action': 'hold', 'confidence': 0.5, 'reasoning': f'Suggestion error: {str(e)}'}
    
    def _prepare_market_summary(self, market_data, timeframe_analysis):
        """
        Prepare a comprehensive market summary for OpenAI analysis
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            # Determine trading session
            hour = current_time.hour
            if 8 <= hour < 17:
                session = "London"
            elif 13 <= hour < 22:
                session = "New York" if hour >= 13 else "London/NY Overlap"
            else:
                session = "Asian"
            
            summary = f"""
            Current Time: {current_time.strftime('%Y-%m-%d %H:%M UTC')}
            Trading Session: {session}
            
            Current Price Data:
            - Price: {market_data.get('current_price', 'N/A')}
            - High: {market_data.get('high', 'N/A')}
            - Low: {market_data.get('low', 'N/A')}
            - ATR: {market_data.get('atr', 'N/A')}
            
            Multi-Timeframe Analysis:
            """
            
            for tf, data in timeframe_analysis.items():
                summary += f"""
            {tf.upper()} Timeframe:
            - Trend: {data.get('trend', 'N/A')}
            - Structure: {data.get('structure', 'N/A')}
            - Key Levels: {data.get('key_levels', 'N/A')}
            - Signals: {data.get('signals', 'N/A')}
            """
            
            return summary
            
        except Exception as e:
            logger.error(f"Error preparing market summary: {str(e)}")
            return "Market data unavailable"


class AITradeAnalyzer:
    """
    Enhanced AI-based trade analyzer with real historical data training
    """
    def __init__(self, mt5_executor=None):
        self.model = None
        self.scaler = StandardScaler()
        self.model_path = 'models/trade_validator.joblib'
        self.scaler_path = 'models/scaler.joblib'
        self.training_data_path = 'models/training_data.csv'
        self.is_model_trained = False
        self.openai_analyzer = OpenAIAnalyzer()
        self.mt5_executor = mt5_executor
        
        # Initialize MT5 MCP Engine
        try:
            from mt5_mcp_server import MT5MCPEngine
            self.mcp_engine = MT5MCPEngine(self.mt5_executor)
        except Exception as e:
            logger.warning(f"Could not initialize MT5MCPEngine: {e}")
            self.mcp_engine = None
        
        # Define consistent feature names (14 features to match requirements)
        self.feature_names = [
            'price_range', 'body_size', 'upper_wick', 'lower_wick',
            'atr', 'momentum', 'has_bos_bullish', 'has_bos_bearish',
            'has_ob_bullish', 'has_ob_bearish', 'has_fvg_bullish',
            'has_fvg_bearish', 'volatility', 'avg_range'
        ]
        
        self.initialize_model()

    def initialize_model(self):
        """Initialize or load the AI model with proper error handling"""
        try:
            # Create models directory
            os.makedirs('models', exist_ok=True)
            
            # Try to load existing model and scaler
            if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
                try:
                    self.model = joblib.load(self.model_path)
                    self.scaler = joblib.load(self.scaler_path)
                    self.is_model_trained = True
                    logger.info("Loaded existing AI model and scaler")
                    return
                except Exception as e:
                    logger.warning(f"Error loading existing model: {e}. Creating new model.")
            
            # Create new model
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
            
            # Train with historical data if MT5 executor is available
            if self.mt5_executor and self.mt5_executor.connected:
                logger.info("Training model with real historical data...")
                self._train_with_historical_data()
            else:
                logger.warning("MT5 executor not available, using synthetic training data")
                self._create_synthetic_training_data()
            
        except Exception as e:
            logger.error(f"Error initializing AI model: {str(e)}")
            # Fallback to basic model
            self.model = RandomForestClassifier(
                n_estimators=50,
                max_depth=8,
                random_state=42
            )
            self._create_synthetic_training_data()

    def _train_with_historical_data(self):
        """Train model with real historical data from the last month"""
        try:
            logger.info("Fetching historical data for model training...")
            
            # Fetch 1 month of 15-minute data
            timeframes = ['15m', '1h', '4h']
            all_features = []
            all_targets = []
            
            for timeframe in timeframes:
                # Calculate days needed for 1 month of data
                days = 30 if timeframe == '15m' else 60
                limit = 2880 if timeframe == '15m' else (720 if timeframe == '1h' else 180)
                
                df = self.mt5_executor.fetch_historical_data_mt5(timeframe, limit)
                if df is None or len(df) < 100:
                    logger.warning(f"Insufficient data for {timeframe}")
                    continue
                
                # Apply indicators (assuming strategy has analyze_market method)
                try:
                    from strategy import SMCStrategy
                    strategy = SMCStrategy()
                    df = strategy.analyze_market(df)
                except Exception as e:
                    logger.warning(f"Could not apply indicators: {e}")
                    # Add basic indicators manually
                    df = self._add_basic_indicators(df)
                
                # Prepare features
                features = self._prepare_training_features(df)
                
                # Create targets based on future price movement
                targets = self._create_training_targets(df)
                
                # Filter valid data
                valid_indices = ~(features.isna().any(axis=1) | pd.isna(targets))
                features = features[valid_indices]
                targets = targets[valid_indices]
                
                if len(features) > 0:
                    all_features.append(features)
                    all_targets.extend(targets)
                    logger.info(f"Added {len(features)} training samples from {timeframe}")
            
            if not all_features:
                raise ValueError("No valid training data available")
            
            # Combine all features
            combined_features = pd.concat(all_features, ignore_index=True)
            combined_targets = np.array(all_targets)
            
            # Save training data
            training_data = combined_features.copy()
            training_data['target'] = combined_targets
            training_data.to_csv(self.training_data_path, index=False)
            logger.info(f"Saved training data: {len(training_data)} samples")
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                combined_features, combined_targets, 
                test_size=0.2, random_state=42, stratify=combined_targets
            )
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train model
            logger.info("Training AI model...")
            self.model.fit(X_train_scaled, y_train)
            
            # Evaluate model
            train_score = self.model.score(X_train_scaled, y_train)
            test_score = self.model.score(X_test_scaled, y_test)
            
            logger.info(f"Model training completed:")
            logger.info(f"Training accuracy: {train_score:.3f}")
            logger.info(f"Testing accuracy: {test_score:.3f}")
            logger.info(f"Training samples: {len(X_train)}")
            
            # Save model and scaler
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            
            self.is_model_trained = True
            logger.info("Model and scaler saved successfully")
            
        except Exception as e:
            logger.error(f"Error training with historical data: {str(e)}")
            logger.info("Falling back to synthetic data training")
            self._create_synthetic_training_data()

    def _add_basic_indicators(self, df):
        """Add basic indicators if strategy indicators are not available"""
        try:
            # Calculate ATR
            df['atr'] = self._calculate_atr(df, period=14)
            
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

    def _calculate_atr(self, df, period=14):
        """Calculate Average True Range"""
        try:
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = np.max(ranges, axis=1)
            
            return true_range.rolling(period).mean()
        except Exception:
            return pd.Series([1.0] * len(df), index=df.index)

    def _prepare_training_features(self, df):
        """Prepare features for training using the consistent feature set"""
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
            
            # Market structure features (use simple boolean conversion)
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
            logger.error(f"Error preparing training features: {e}")
            # Return empty DataFrame with correct columns
            return pd.DataFrame(columns=self.feature_names)

    def _create_training_targets(self, df, future_periods=10):
        """Create training targets based on future price movement"""
        try:
            # Look ahead to see if price moves favorably
            future_high = df['high'].shift(-future_periods).rolling(future_periods).max()
            future_low = df['low'].shift(-future_periods).rolling(future_periods).min()
            current_close = df['close']
            
            # Define successful trade conditions (simplified)
            # Bullish: price moves up significantly
            bullish_target = (future_high > current_close * 1.001).astype(int)
            
            # Create binary target (1 for profitable, 0 for not profitable)
            targets = bullish_target.fillna(0).astype(int)
            
            return targets.values
            
        except Exception as e:
            logger.error(f"Error creating training targets: {e}")
            return np.zeros(len(df))

    def _create_synthetic_training_data(self):
        """Create synthetic training data as fallback"""
        try:
            logger.info("Creating synthetic training data...")
            
            n_samples = 1000
            np.random.seed(42)
            
            # Generate synthetic features
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
            
            # Create synthetic targets
            targets = np.zeros(n_samples)
            for i in range(n_samples):
                score = 0
                # Simple scoring based on feature combinations
                if features.loc[i, 'momentum'] > 0 and features.loc[i, 'has_bos_bullish']:
                    score += 2
                if features.loc[i, 'has_ob_bullish'] and features.loc[i, 'momentum'] > 0:
                    score += 2
                if 0.01 < features.loc[i, 'volatility'] < 0.03:
                    score += 1
                
                targets[i] = 1 if score >= 3 else 0
            
            # Train model
            X_train, X_test, y_train, y_test = train_test_split(
                features, targets, test_size=0.2, random_state=42
            )
            
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            self.model.fit(X_train_scaled, y_train)
            
            # Save model and scaler
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            
            self.is_model_trained = True
            logger.info(f"Synthetic model training completed. Accuracy: {self.model.score(X_test_scaled, y_test):.3f}")
            
        except Exception as e:
            logger.error(f"Error creating synthetic training data: {str(e)}")
            self.is_model_trained = False

    def prepare_features(self, df, session_info=None):
        """
        Prepare feature set for AI analysis (consistent with training)
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
            features['has_bos_bullish'] = df.get('bos_bullish', False).astype(int)
            features['has_bos_bearish'] = df.get('bos_bearish', False).astype(int)
            features['has_ob_bullish'] = df.get('bullish_ob', False).astype(int)
            features['has_ob_bearish'] = df.get('bearish_ob', False).astype(int)
            features['has_fvg_bullish'] = df.get('bullish_fvg', False).astype(int)
            features['has_fvg_bearish'] = df.get('bearish_fvg', False).astype(int)
            
            # Enhanced features
            features['volatility'] = features['atr'] / df['close']
            features['avg_range'] = features['price_range'].rolling(10).mean()
            
            # Ensure correct order and fill missing values
            features = features[self.feature_names].fillna(0)
            
            return features
            
        except Exception as e:
            logger.error(f"Error preparing features: {str(e)}")
            # Return DataFrame with correct structure
            return pd.DataFrame(0, index=df.index, columns=self.feature_names)

    def enhanced_validate_trade(self, df, signal, timeframe_analysis=None):
        """
        Enhanced trade validation with OpenAI integration (synchronous version)
        """
        try:
            # Get traditional ML validation
            ml_validation = self.validate_trade(df, signal)
            
            # Get OpenAI analysis if available and timeframe analysis provided
            if self.openai_analyzer.enabled:
                logger.info("Running OpenAI enhanced analysis...")
                
                market_data = {
                    'current_price': df['close'].iloc[-1],
                    'high': df['high'].iloc[-1],
                    'low': df['low'].iloc[-1],
                    'atr': df.get('atr', [1.0]).iloc[-1]
                }
                
                # Get sentiment and trade suggestion using synchronous calls
                sentiment_analysis = self.openai_analyzer.analyze_market_sentiment_sync(market_data, timeframe_analysis)
                trade_suggestion = self.openai_analyzer.get_trade_suggestion_sync(market_data, timeframe_analysis)
                
                # Combine ML and OpenAI analysis
                combined_confidence = (
                    ml_validation['confidence'] * 0.4 +
                    sentiment_analysis.get('confidence', 0.5) * 0.3 +
                    trade_suggestion.get('confidence', 0.5) * 0.3
                )
                
                # Check confluence factors
                confluence_count = len(trade_suggestion.get('confluence_factors', []))
                
                # Enhanced validation logic
                openai_agrees = False
                if signal == 1:  # Buy signal
                    openai_agrees = (sentiment_analysis.get('sentiment') == 'bullish' and 
                                   trade_suggestion.get('action') in ['buy', 'hold'])
                elif signal == -1:  # Sell signal
                    openai_agrees = (sentiment_analysis.get('sentiment') == 'bearish' and 
                                   trade_suggestion.get('action') in ['sell', 'hold'])
                
                # Final validation requires both ML confidence and OpenAI agreement
                enhanced_valid = (
                    ml_validation['valid'] and
                    combined_confidence >= 0.6 and
                    confluence_count >= 2 and
                    openai_agrees
                )
                
                logger.info(f"OpenAI Enhanced Analysis - Sentiment: {sentiment_analysis.get('sentiment')}, "
                           f"Action: {trade_suggestion.get('action')}, "
                           f"Combined Confidence: {combined_confidence:.2f}, "
                           f"Confluence Factors: {confluence_count}")
                
                return {
                    'valid': enhanced_valid,
                    'confidence': combined_confidence,
                    'ml_confidence': ml_validation['confidence'],
                    'sentiment': sentiment_analysis,
                    'trade_suggestion': trade_suggestion,
                    'confluence_factors': confluence_count,
                    'market_conditions': ml_validation['market_conditions'],
                    'openai_agrees': openai_agrees
                }
            else:
                # Fallback to ML validation only
                return ml_validation
                
        except Exception as e:
            logger.error(f"Error in enhanced trade validation: {str(e)}")
            return self.validate_trade(df, signal)

    def mcp_validate_trade(self, df, signal, symbol='XAUUSDm'):
        """
        MCP-Enhanced Trade Validation Engine
        Combines 14-Feature ML Model + Live MCP OrderBook Depth + Spread ATR Filter + Portfolio Risk Metrics
        """
        try:
            # 1. Get base ML prediction & confidence
            base_validation = self.validate_trade(df, signal)
            
            if self.mcp_engine is None:
                return base_validation
                
            # 2. Get live MCP telemetry & risk checks
            spread_info = self.mcp_engine.mcp_get_spread_and_volatility(symbol, df)
            risk_info = self.mcp_engine.mcp_check_portfolio_risk(symbol)
            smc_confluence = self.mcp_engine.mcp_validate_smc_confluence(symbol, df)
            depth_info = self.mcp_engine.mcp_get_market_depth(symbol)
            
            # 3. Calculate MCP Enhanced Confidence Score
            ml_conf = base_validation.get('confidence', 0.5)
            smc_conf = smc_confluence.get('confluence_score', 0.5)
            
            # Bonus for favorable orderbook depth
            ob_bias = depth_info.get('orderbook_bias', 'neutral')
            ob_bonus = 0.05 if (signal == 1 and ob_bias == 'bullish') or (signal == -1 and ob_bias == 'bearish') else 0.0
            
            combined_confidence = (ml_conf * 0.5) + (smc_conf * 0.45) + ob_bonus
            combined_confidence = min(0.99, max(0.1, combined_confidence))
            
            # 4. Master MCP Decision Check
            spread_ok = spread_info.get('spread_acceptable', True)
            risk_ok = risk_info.get('risk_passed', True)
            min_threshold = getattr(config, 'AI_SETTINGS', {}).get('confidence_threshold', 0.45)
            
            is_valid = (
                base_validation.get('valid', True) and
                combined_confidence >= min_threshold and
                spread_ok and
                risk_ok
            )
            
            reasons = []
            if not spread_ok:
                reasons.append(f"Spread expanded: {spread_info.get('spread_pips')} pips > max allowed")
            if not risk_ok:
                reasons.append("Portfolio correlation or total risk limit exceeded")
            if combined_confidence < min_threshold:
                reasons.append(f"Confidence {combined_confidence:.2f} < threshold {min_threshold}")
            if is_valid:
                reasons.append(f"Passed all MCP checks (Confidence: {combined_confidence:.2f}, SMC Factors: {smc_confluence.get('factor_count')})")

            logger.info(f"MCP Trade Validation [{symbol}] -> Valid: {is_valid}, "
                        f"Confidence: {combined_confidence:.2f}, Spread: {spread_info.get('spread_pips')} pips, "
                        f"OrderBook: {ob_bias}")

            return {
                'valid': is_valid,
                'confidence': round(combined_confidence, 2),
                'ml_confidence': round(ml_conf, 2),
                'smc_confluence_score': smc_conf,
                'reasons': reasons,
                'spread_info': spread_info,
                'risk_info': risk_info,
                'market_depth': depth_info,
                'confluence_factors': smc_confluence.get('confluence_factors', []),
                'market_conditions': base_validation.get('market_conditions', {})
            }
        except Exception as e:
            logger.error(f"Error in MCP trade validation: {str(e)}")
            return self.validate_trade(df, signal)

    def validate_trade(self, df, signal):
        """
        Validate a trade signal using AI analysis
        """
        try:
            if not self.is_model_trained:
                logger.warning("Model not trained yet, using default validation")
                return {
                    'valid': True,
                    'confidence': 0.6,
                    'market_conditions': {
                        'trend_strength': 0,
                        'volatility_state': 'normal',
                        'momentum': 'neutral',
                        'risk_level': 'medium'
                    }
                }
            
            # Prepare features for the latest market conditions
            features = self.prepare_features(df)
            if features.empty:
                raise ValueError("No features could be prepared from the data")
                
            latest_features = features.iloc[-1:].copy()
            
            # Scale features
            scaled_features = self.scaler.transform(latest_features)
            
            # Get model prediction and confidence
            prediction = self.model.predict(scaled_features)[0]
            probabilities = self.model.predict_proba(scaled_features)[0]
            logger.info(f"Prediction: {prediction}, Probabilities: {probabilities}")
            # Calculate confidence score
            confidence = max(probabilities)  # Use the maximum probability as confidence
            valid = prediction == 1  # 1 indicates profitable trade
            
            # Add market condition analysis
            market_conditions = self.analyze_market_conditions(df)
            
            return {
                'valid': valid and confidence >= 0.6,
                'confidence': confidence,
                'market_conditions': market_conditions
            }
            
        except Exception as e:
            logger.error(f"Error in AI trade validation: {str(e)}")
            # Return a conservative default response
            return {
                'valid': False,
                'confidence': 0.0,
                'market_conditions': {
                    'trend_strength': 0,
                    'volatility_state': 'normal',
                    'momentum': 'neutral',
                    'risk_level': 'high'
                }
            }

    def analyze_market_conditions(self, df):
        """
        Analyze current market conditions for additional insights
        """
        try:
            latest = df.iloc[-10:]  # Look at last 10 candles
            
            conditions = {
                'trend_strength': 0,
                'volatility_state': 'normal',
                'momentum': 'neutral',
                'risk_level': 'medium'
            }
            
            # Analyze trend strength
            price_change = (latest['close'].iloc[-1] - latest['close'].iloc[0]) / latest['close'].iloc[0]
            if price_change > 0.01:
                conditions['trend_strength'] = 1  # Strong uptrend
            elif price_change < -0.01:
                conditions['trend_strength'] = -1  # Strong downtrend
                
            # Analyze volatility
            atr_values = latest.get('atr', pd.Series([1.0] * len(latest)))
            avg_atr = atr_values.mean()
            current_atr = atr_values.iloc[-1]
            
            if current_atr > avg_atr * 1.5:
                conditions['volatility_state'] = 'high'
            elif current_atr < avg_atr * 0.5:
                conditions['volatility_state'] = 'low'
                
            # Analyze momentum
            momentum = (latest['close'].iloc[-1] - latest['close'].iloc[-5]) / latest['close'].iloc[-5]
            if momentum > 0.002:  # 0.2% change
                conditions['momentum'] = 'bullish'
            elif momentum < -0.002:
                conditions['momentum'] = 'bearish'
                
            # Calculate risk level
            risk_factors = 0
            if conditions['volatility_state'] == 'high':
                risk_factors += 1
            if abs(conditions['trend_strength']) < 0.5:
                risk_factors += 1
            if conditions['momentum'] == 'neutral':
                risk_factors += 1
                
            if risk_factors >= 2:
                conditions['risk_level'] = 'high'
            elif risk_factors == 0:
                conditions['risk_level'] = 'low'
                
            return conditions
            
        except Exception as e:
            logger.error(f"Error analyzing market conditions: {e}")
            return {
                'trend_strength': 0,
                'volatility_state': 'normal',
                'momentum': 'neutral',
                'risk_level': 'medium'
            }

    def update_model(self, trade_result):
        """
        Update the AI model with the results of a completed trade
        """
        try:
            if self.model is None or not self.is_model_trained:
                logger.warning("Model not available for updating")
                return
                
            # Prepare training data from trade result
            market_data = trade_result.get('market_data')
            if market_data is None:
                logger.error("No market data in trade result")
                return
                
            features = self.prepare_features(market_data)
            if features.empty:
                logger.error("Could not prepare features from trade result")
                return
                
            latest_features = features.iloc[-1:].copy()
            target = [1 if trade_result['profitable'] else 0]
            
            # Scale features
            scaled_features = self.scaler.transform(latest_features)
            
            # Update model (simple online learning)
            # Note: RandomForest doesn't support incremental learning, so we just log the result
            logger.info(f"Trade result recorded: {'Profitable' if target[0] else 'Loss'}")
            
            # For more sophisticated updating, you would need to:
            # 1. Load all previous training data
            # 2. Add new sample
            # 3. Retrain model
            # This is left as a future enhancement
            
        except Exception as e:
            logger.error(f"Error updating AI model: {str(e)}")

    def retrain_model(self):
        """
        Retrain the model with fresh historical data
        """
        try:
            logger.info("Retraining model with fresh data...")
            
            if self.mt5_executor and self.mt5_executor.connected:
                self._train_with_historical_data()
            else:
                logger.warning("MT5 executor not available for retraining")
                
        except Exception as e:
            logger.error(f"Error retraining model: {str(e)}")

    def get_model_info(self):
        """
        Get information about the current model
        """
        try:
            info = {
                'is_trained': self.is_model_trained,
                'model_type': type(self.model).__name__ if self.model else 'None',
                'feature_count': len(self.feature_names),
                'features': self.feature_names,
                'model_exists': os.path.exists(self.model_path),
                'scaler_exists': os.path.exists(self.scaler_path),
                'training_data_exists': os.path.exists(self.training_data_path)
            }
            
            if self.is_model_trained and hasattr(self.model, 'n_estimators'):
                info['n_estimators'] = self.model.n_estimators
                
            return info
            
        except Exception as e:
            logger.error(f"Error getting model info: {e}")
            return {'error': str(e)}
