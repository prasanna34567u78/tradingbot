# Scalping Bot Configuration
# Optimized for high-frequency gold trading

import os

# MT5 Connection Settings
MT5_LOGIN = int(os.getenv('MT5_LOGIN', '0'))
MT5_PASSWORD = os.getenv('MT5_PASSWORD', 'password')
MT5_SERVER = os.getenv('MT5_SERVER', 'MetaQuotes-Demo')

# Primary scalping symbol
SYMBOL = 'BTCUSDm'  # Gold in USD

# Scalping Risk Management
RISK_PERCENT = 0.5  # Lower risk per trade for scalping
TP_RATIO = 2.0      # 2:1 risk reward for scalping
SCALP_TARGET_PIPS = 8   # Quick 8 pip targets
SCALP_STOP_PIPS = 4     # Tight 4 pip stops
MAX_SPREAD_PIPS = 3.0   # Maximum spread for scalping entry

# Position Sizing for Scalping
MIN_LOT_SIZE = 0.01
MAX_LOT_SIZE = 1.0  # Conservative for scalping
SCALP_POSITION_MULTIPLIER = 0.8  # Use smaller positions for scalping

# Scalping Timeframes (focus on very short term)
SCALPING_TIMEFRAMES = {
    'primary': '1m',    # Primary scalping timeframe
    'secondary': '5m'   # Secondary confirmation timeframe
}

# High-Frequency Scheduler Intervals (in seconds)
SCALPING_SCHEDULER_INTERVALS = {
    'signal_check': 5,      # Check for signals every 5 seconds
    'trade_monitor': 2,     # Monitor trades every 2 seconds  
    'risk_check': 30,       # Check risk every 30 seconds
    'session_check': 60     # Check trading session every minute
}

# Scalping Session Management
ACTIVE_SCALPING_SESSIONS = {
    'london': {'start': 7, 'end': 10},      # London session
    'ny_overlap': {'start': 13, 'end': 16}, # NY-London overlap
    'asian': {'start': 20, 'end': 24}       # Asian session start
}

# Daily Scalping Limits
MAX_DAILY_TRADES = 50       # Maximum trades per day
MAX_DAILY_LOSS_USD = 200    # Maximum daily loss in USD
DAILY_PROFIT_TARGET = 500   # Daily profit target in USD

# Scalping Indicator Settings
SCALPING_INDICATORS = {
    'rsi_period': 7,            # Fast RSI for scalping
    'stoch_k_period': 5,        # Fast stochastic
    'stoch_d_period': 3,
    'macd_fast': 5,             # Very fast MACD
    'macd_slow': 13,
    'macd_signal': 4,
    'bb_period': 10,            # Short Bollinger Bands
    'bb_std': 1.5,
    'atr_period': 7,            # Fast ATR
    'velocity_period': 3        # Price velocity period
}

# Scalping Entry Conditions
SCALPING_ENTRY = {
    'min_momentum_threshold': 0.5,      # Minimum momentum for entry
    'max_momentum_threshold': 3.0,      # Maximum to avoid excessive volatility
    'rsi_oversold': 25,                 # Oversold level for mean reversion
    'rsi_overbought': 75,               # Overbought level for mean reversion
    'confluence_threshold': 0.4,        # Lower threshold for scalping
    'breakout_confirmation_bars': 2     # Bars to confirm breakout
}

# Aggressive Trailing Stop Settings for Scalping
SCALPING_TRAILING = {
    'breakeven_pips': 2,        # Move to breakeven after 2 pips
    'trailing_start_pips': 4,   # Start trailing after 4 pips
    'trailing_step_pips': 1,    # Trail every 1 pip
    'max_adverse_pips': 2,      # Exit if goes 2 pips against after breakeven
}

# Scalping Exit Conditions
SCALPING_EXIT = {
    'quick_exit_on_reversal': True,     # Exit quickly on reversal signals
    'time_based_exit_minutes': 30,     # Exit after 30 minutes max
    'profit_protection_pips': 3,       # Protect profit after 3 pips
    'momentum_reversal_threshold': 0.3  # Exit if momentum reverses
}

# Telegram Notifications (Enhanced for Scalping)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
SCALPING_NOTIFICATIONS = {
    'trade_opened': True,
    'trade_closed': True,
    'daily_summary': True,
    'risk_alerts': True,
    'session_changes': False,   # Too frequent for scalping
    'minor_updates': False      # Only important notifications
}

# Database Settings
DB_PATH = 'scalping_trades.db'

# Logging Settings
LOG_LEVEL = 'INFO'
LOG_FILE = 'scalping_bot.log'
SCALPING_LOG_FORMAT = '%(asctime)s - SCALP - %(levelname)s - %(message)s'

# Market Microstructure Settings for Scalping
MICROSTRUCTURE = {
    'tick_analysis_enabled': True,
    'order_flow_weight': 0.3,
    'volume_spike_threshold': 2.0,
    'liquidity_sweep_detection': True,
    'smart_money_tracking': True
}

# Performance Tracking
SCALPING_METRICS = {
    'track_pips_per_trade': True,
    'track_win_rate': True,
    'track_avg_hold_time': True,
    'track_session_performance': True,
    'track_hourly_pnl': True
}

# Emergency Stop Conditions
EMERGENCY_STOP = {
    'consecutive_losses': 5,        # Stop after 5 consecutive losses
    'drawdown_percent': 3.0,        # Stop if 3% drawdown  
    'daily_loss_limit': 200,        # USD daily loss limit
    'connection_loss_seconds': 30   # Stop if connection lost for 30 seconds
}

print("Scalping configuration loaded successfully!")
print(f"Primary symbol: {SYMBOL}")
print(f"Target: {SCALP_TARGET_PIPS} pips, Stop: {SCALP_STOP_PIPS} pips")
print(f"Max daily trades: {MAX_DAILY_TRADES}")
print(f"Signal check interval: {SCALPING_SCHEDULER_INTERVALS['signal_check']} seconds")
print(f"Trade monitor interval: {SCALPING_SCHEDULER_INTERVALS['trade_monitor']} seconds") 