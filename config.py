# Configuration settings for the Multi-Symbol Trading Bot

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Broker API Configuration (Exness)
API_KEY = os.getenv('EXNESS_API_KEY', '')
API_SECRET = os.getenv('EXNESS_API_SECRET', '')
ACCOUNT_ID = os.getenv('EXNESS_ACCOUNT_ID', '')

# MT5 Account Configuration
MT5_LOGIN = int(os.getenv('MT5_LOGIN', '463824617'))
MT5_PASSWORD = os.getenv('MT5_PASSWORD', 'Prasanna@123')
MT5_SERVER = os.getenv('MT5_SERVER', 'Exness-MT5Trial17')

# Multi-Symbol Trading Configuration
SYMBOLS = {
    'XAUUSDm': {  # Gold
        'enabled': True,
        'risk_percent': 1.0,
        'tp_ratio': 2.5,  # Reduced from 3.0 for better execution
        'max_trades': 1,
        'min_rr_ratio': 1.2,  # Reduced from 2.0 for scalping
        'fixed_lot_size': 0.01,  # Set to specific value (e.g., 0.01) to use fixed lots, None for dynamic
        'trailing_settings': {
            'start_ratio': 0.8,  # Start trailing earlier (% of TP)
            'trail_step': 0.3,   # Smaller trail steps for scalping
            'trail_tp': True,    # Enable TP trailing
            'trail_sl': True,    # Enable SL trailing
            'breakeven_ratio': 0.5,  # Move to breakeven at 50% TP
            'partial_close_pct': 50.0,  # Dynamically book 50% lot at breakeven
        },
        'volatility_adj': True,  # Adjust position size based on volatility
        'correlation_filter': True,  # Enable correlation filtering
        'scalping_mode': True,  # Enable scalping optimizations
    },
    'BTCUSDm': {  # Bitcoin
        'enabled': True,
        'risk_percent': 0.5,  # Reduced risk for BTC
        'tp_ratio': 2.0,  # Reduced from 2.5 for better execution
        'max_trades': 1,
        'min_rr_ratio': 1.0,  # Reduced from 2.0 for crypto scalping
        'fixed_lot_size': 0.02,  # Set to specific value (e.g., 0.01) to use fixed lots, None for dynamic
        'trailing_settings': {
            'start_ratio': 0.8,  # Start trailing (% of TP)
            'trail_step': 0.3,   # Stable trailing steps
            'trail_tp': True,
            'trail_sl': True,
            'breakeven_ratio': 0.5,  # Move to breakeven at 50% TP
            'partial_close_pct': 50.0,  # Dynamically book 50% lot at breakeven
        },
        'volatility_adj': True,
        'correlation_filter': True,
        'scalping_mode': False,  # PDE structural zone execution
    },
    'USOILm': {  # US Oil
        'enabled': True,
        'risk_percent': 1.2,
        'tp_ratio': 2.0,  # Reduced for better execution
        'max_trades': 1,
        'min_rr_ratio': 1.2,  # Reduced from 1.3
        'trailing_settings': {
            'start_ratio': 0.8,
            'trail_step': 0.4,
            'trail_tp': True,
            'trail_sl': True,
            'breakeven_ratio': 0.5,
            'partial_close_pct': 50.0,
        },
        'volatility_adj': True,
        'correlation_filter': True,
        'scalping_mode': False,
    },
    'EURUSDm': {  # Euro
        'enabled': True,
        'risk_percent': 0.5,
        'tp_ratio': 2.0,  # Reduced from 2.5 for better execution
        'max_trades': 1,
        'min_rr_ratio': 1.0,  # Reduced from 2.0 for forex scalping
        'fixed_lot_size': 0.01,  # Set to specific value (e.g., 0.01) to use fixed lots, None for dynamic
        'trailing_settings': {
            'start_ratio': 0.8,  # Start trailing early
            'trail_step': 0.2,   # Very small steps for forex
            'trail_tp': True,
            'trail_sl': True,
            'breakeven_ratio': 0.5,  # Quick breakeven
            'partial_close_pct': 50.0,  # Dynamically book 50% lot at breakeven
        },
        'volatility_adj': True,
        'correlation_filter': True,
        'scalping_mode': True,  # Enable scalping optimizations
    }
}

# Enhanced Risk Management
RISK_MANAGEMENT = {
    'max_total_risk': 2.0,  # Reduced maximum total risk across all positions
    'max_correlated_risk': 1.5,  # Maximum risk for correlated instruments
    'correlation_threshold': 0.7,  # Correlation threshold for filtering
    'volatility_lookback': 20,  # ATR periods for volatility calculation
    'dynamic_sizing': True,  # Enable dynamic position sizing
    'max_drawdown_stop': 8.0,  # Reduced stop trading at 8% drawdown
    'daily_loss_limit': 3.0,  # Reduced daily loss limit percentage
    'consecutive_loss_limit': 3,  # Stop after 3 consecutive losses
    'max_daily_trades': 10,  # Maximum trades per day
}

# Advanced Trailing Configuration
TRAILING_SETTINGS = {
    'algorithm': 'enhanced_atr',  # 'simple', 'atr', 'enhanced_atr', 'parabolic'
    'atr_multiplier': 2.0,
    'min_trail_distance': 0.001,  # Minimum trail distance
    'trail_frequency': 30,  # Trail update frequency in seconds
    'use_swing_levels': True,  # Use swing highs/lows for trailing
    'consolidation_filter': True,  # Avoid trailing in consolidation
}

# Legacy single symbol support (for backward compatibility)
SYMBOL = 'XAUUSDm'  # Primary symbol
RISK_PERCENT = 1.0  # Default risk per trade
TP_RATIO = 2.0      # Default take profit ratio
SL_PADDING = 5      # Additional pips for stop loss

# Multi-Timeframe Configuration
TIMEFRAMES = {
    'primary': '5m',       # Primary timeframe for signals (5m scalping mode)
    'confirmation': ['15m', '1h'],  # Higher timeframes for confirmation
    'precision': ['5m', '1m'],     # Lower timeframes for precise entry
}

# ICT/SMC Strategy Configuration
ICT_SETTINGS = {
    'session_times': {
        'london': {'start': '08:00', 'end': '17:00'},
        'new_york': {'start': '13:00', 'end': '22:00'},
        'asian': {'start': '00:00', 'end': '09:00'}
    },
    'power_of_three': {
        'accumulation': '20:00-02:00',  # Asian session
        'manipulation': '02:00-05:00',  # Pre-London
        'distribution': '08:00-17:00'   # London/NY overlap
    },
    'order_block_lookback': 20,
    'liquidity_sweep_tolerance': 0.0001,  # 1 pip for gold
    'fvg_min_size': 0.0005,  # Minimum FVG size (0.5 pips)
    'premium_discount_levels': [0.618, 0.705, 0.79, 0.886],  # Fibonacci levels
}

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = 'gpt-4o-mini'  # Using gpt-4o-mini for better availability and performance
OPENAI_MAX_TOKENS = 500
OPENAI_TEMPERATURE = 0.3

# Strategy Selection Mode
# Options:
#   'mcp_enhanced' : Multi-Timeframe SMC + MT5 MCP (Highest AI win rate 68-76%)
#   'standard_ai'  : Multi-Timeframe SMC + 14-Feature Random Forest AI Model
#   'pde'          : Premium/Discount/Equilibrium Zone strategy (SL + TP1 + TP2)
#   'scalping'     : Fast 1M/5M Scalping Mode
STRATEGY_MODE = 'pde'

# Premium / Discount / Equilibrium Zone Strategy Settings  (v4 - 5M Scalping Mode)
# 5Y Backtest results on 5M Gold: +568,272.7% return | Sharpe 1.95 | PF 1.42 | All 4 years positive
PDE_SETTINGS = {
    'enabled':              True,
    'timeframe':            '5m',      # 5-minute scalping timeframe
    'swing_lookback':       50,       # 50 5-min bars range window
    'atr_period':           14,
    'sl_atr_mult':          0.5,      # Buffer below swing_low / above swing_high
    'tp1_close_pct':        0.50,     # Close 50% of position at TP1
    'ema_trend_period':     200,      # Kept for compatibility with other modes
    'rsi_period':           14,
    'rsi_buy_threshold':    42.0,     # Buy when RSI < 42 (genuine oversold in discount)
    'rsi_sell_threshold':   58.0,     # Sell when RSI > 58 (genuine overbought in premium)
    'max_zone_touches':     3,        # Max signals per zone per day
    'min_atr_pct':          0.0002,   # Skip flat/choppy markets
    'require_confirmation': True,     # Require bar to close in correct direction
    'volume_filter':        True,     # Volume >= 75% of 20-bar avg
    'min_rr':               1.5,      # Minimum R:R ratio to enter trade
    'cooldown_bars':        48,       # 48 bars cooldown for 5m timeframe
    # Zone boundaries (Fibonacci)
    'premium_threshold':    0.618,    # Above 61.8% Fib = Premium zone
    'discount_threshold':   0.382,    # Below 38.2% Fib = Discount zone
}

# Model Context Protocol (MCP) Configuration
MCP_SETTINGS = {
    'enabled': True,                     # Set True to enable MT5 MCP Tool Engine
    'enable_level2_depth': True,         # Check Level 2 orderbook depth & volume imbalance
    'enable_spread_protection': True,    # Filter trades during high spread expansion
    'enable_portfolio_correlation': True,# Filter trades violating cross-symbol risk
    'max_spread_atr_multiplier': 0.25,   # Max allowed spread as fraction of 1H ATR
}

# AI Analysis Configuration
AI_SETTINGS = {
    'enable_openai': False,  # Local ML model (RandomForest) enabled when False
    'confidence_threshold': 0.55,  # Min confidence threshold (0.50 - 0.65)
    'market_condition_weight': 0.3,
    'technical_analysis_weight': 0.6,
    'sentiment_analysis_weight': 0.1,
    'min_confluence_factors': 2,
    'multi_symbol_analysis': True,
    'scalping_mode': False,
    'accept_lower_confidence': False,
}

# Webhook Configuration
WEBHOOK_PORT = 5000
WEBHOOK_HOST = '0.0.0.0'
WEBHOOK_PATH = '/webhook'

# Telegram Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Database Configuration
DB_PATH = 'trades.db'

# Logging Configuration
LOG_LEVEL = 'INFO'
LOG_FILE = 'trading_bot.log'

# Enhanced Scheduler Configuration (Optimized for Scalping)
SCHEDULER_INTERVALS = {
    'signal_check': 30,     # More frequent signal checks for scalping (every 30 seconds)
    'trade_monitor': 10,    # Very frequent monitoring for scalping (every 10 seconds)
    'market_analysis': 45,  # Faster market analysis updates
    'correlation_update': 300,  # Update correlations every 5 minutes
    'risk_check': 60,       # More frequent risk checks (every minute)
}

# Trade Quality Filters
TRADE_QUALITY = {
    'min_atr_multiplier': 1.5,      # Minimum ATR multiple for stop loss
    'max_spread_multiplier': 2.0,   # Max spread as multiple of ATR
    'min_volume_filter': True,      # Filter low volume periods
    'trend_confirmation': True,     # Require trend confirmation
    'session_filter': False,         # Only trade during active sessions
    'news_avoidance_hours': 1,      # Avoid trading 1 hour around major news
}