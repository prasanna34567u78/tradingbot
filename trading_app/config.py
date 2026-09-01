# Configuration settings for the Multi-Symbol Trading Bot
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('EXNESS_API_KEY', '')
API_SECRET = os.getenv('EXNESS_API_SECRET', '')
ACCOUNT_ID = ''

MT5_LOGIN = 463824617
MT5_PASSWORD = 'Prasanna@123'
MT5_SERVER = 'Exness-MT5Trial17'

SYMBOLS = {   'BTCUSDm': {   'correlation_filter': True,
                   'enabled': False,
                   'fixed_lot_size': 0.02,
                   'max_trades': 1,
                   'min_rr_ratio': 1.5,
                   'risk_percent': 1,
                   'scalping_mode': True,
                   'tp_ratio': 2.5,
                   'trailing_settings': {   'breakeven_ratio': 0.5,
                                            'partial_close_pct': 50,
                                            'start_ratio': 0.8,
                                            'trail_sl': True,
                                            'trail_step': 0.3,
                                            'trail_tp': True},
                   'volatility_adj': True},
    'ETHUSDm': {   'correlation_filter': True,
                   'enabled': False,
                   'fixed_lot_size': 0.2,
                   'max_trades': 1,
                   'min_rr_ratio': 1.5,
                   'risk_percent': 1,
                   'scalping_mode': True,
                   'tp_ratio': 2.5,
                   'trailing_settings': {   'breakeven_ratio': 0.5,
                                            'partial_close_pct': 50,
                                            'start_ratio': 0.8,
                                            'trail_sl': True,
                                            'trail_step': 0.2,
                                            'trail_tp': True},
                   'volatility_adj': True},
    'EURUSDm': {   'correlation_filter': True,
                   'enabled': False,
                   'fixed_lot_size': 0.01,
                   'max_trades': 1,
                   'min_rr_ratio': 1,
                   'risk_percent': 0.5,
                   'scalping_mode': True,
                   'tp_ratio': 2,
                   'trailing_settings': {   'breakeven_ratio': 0.5,
                                            'partial_close_pct': 50,
                                            'start_ratio': 0.8,
                                            'trail_sl': True,
                                            'trail_step': 0.2,
                                            'trail_tp': True},
                   'volatility_adj': True},
    'USOILm': {   'correlation_filter': True,
                  'enabled': False,
                  'max_trades': 1,
                  'min_rr_ratio': 1.2,
                  'risk_percent': 1.2,
                  'scalping_mode': False,
                  'tp_ratio': 2,
                  'trailing_settings': {   'breakeven_ratio': 0.5,
                                           'partial_close_pct': 50,
                                           'start_ratio': 0.8,
                                           'trail_sl': True,
                                           'trail_step': 0.4,
                                           'trail_tp': True},
                  'volatility_adj': True},
    'XAUUSDm': {   'correlation_filter': True,
                   'enabled': True,
                   'fixed_lot_size': 0.02,
                   'max_risk_amount': 2000,
                   'max_trades': 1,
                   'min_rr_ratio': 2.1,
                   'risk_percent': 20,
                   'scalping_mode': True,
                   'tp_ratio': 2.5,
                   'trailing_settings': {   'breakeven_ratio': 0.5,
                                            'enable_breakeven': False,
                                            'enable_partial_booking': False,
                                            'full_close_on_be': False,
                                            'partial_close_pct': 50,
                                            'start_ratio': 0.8,
                                            'static_sl': True,
                                            'trail_sl': True,
                                            'trail_step': 0.3,
                                            'trail_tp': True},
                   'volatility_adj': True}}
RISK_MANAGEMENT = {   'consecutive_loss_limit': 3,
    'correlation_threshold': 0.7,
    'daily_loss_limit': 4,
    'dynamic_sizing': True,
    'max_correlated_risk': 39.5,
    'max_daily_trades': 10,
    'max_drawdown_stop': 45,
    'max_total_risk': 76.5,
    'volatility_lookback': 20}
TRAILING_SETTINGS = {   'algorithm': 'enhanced_atr',
    'atr_multiplier': 2,
    'consolidation_filter': True,
    'min_trail_distance': 0.001,
    'trail_frequency': 30,
    'use_swing_levels': True}

SYMBOL = 'XAUUSDm'
RISK_PERCENT = 1
TP_RATIO = 2
SL_PADDING = 5

TIMEFRAMES = {'confirmation': ['15m', '1h'], 'precision': ['5m', '1m'], 'primary': '1m'}
ICT_SETTINGS = {   'fvg_min_size': 0.0005,
    'liquidity_sweep_tolerance': 0.0001,
    'order_block_lookback': 20,
    'power_of_three': {   'accumulation': '20:00-02:00',
                          'distribution': '08:00-17:00',
                          'manipulation': '02:00-05:00'},
    'premium_discount_levels': [0.618, 0.705, 0.79, 0.886],
    'session_times': {   'asian': {'end': '09:00', 'start': '00:00'},
                         'london': {'end': '17:00', 'start': '08:00'},
                         'new_york': {'end': '22:00', 'start': '13:00'}}}

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = 'gpt-4o-mini'
OPENAI_MAX_TOKENS = 500
OPENAI_TEMPERATURE = 0.3
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL = 'gemini-1.5-pro'

STRATEGY_MODE = 'scalping'
PDE_SETTINGS = {   'atr_period': 14,
    'cooldown_bars': 48,
    'discount_threshold': 0.382,
    'ema_trend_period': 200,
    'enabled': True,
    'max_zone_touches': 3,
    'min_atr_pct': 0.0002,
    'min_rr': 1.5,
    'premium_threshold': 0.618,
    'require_confirmation': True,
    'rsi_buy_threshold': 42,
    'rsi_period': 14,
    'rsi_sell_threshold': 58,
    'sl_atr_mult': 0.5,
    'swing_lookback': 50,
    'timeframe': '1m',
    'tp1_close_pct': 0.5,
    'volume_filter': True}

# Trend-Adaptive Liquidity Sweep Structure Settings (v1 - High Alpha Mode)
# 1Y 5M Real MT5 Results: +$3,063 USD (+30.6% on 0.02 lot) / +$46,090 USD (+460.9% compounding)
SWEEP_STRUCTURE_SETTINGS = {
    'enabled':              True,
    'timeframe':            '5m',      # 5-minute primary execution timeframe
    'sweep_lookback':       15,        # 15 bars swing high/low reference lookback
    'min_base_bars':        2,         # Minimum consolidation base bars
    'max_base_bars':        10,        # Maximum consolidation base bars
    'sl_buffer_pts':        0.35,      # Stop loss buffer beyond sweep extreme
    'buy_rr':               3.0,       # 1:3 Risk:Reward on BUY setups in Bullish Trend
    'sell_rr':              2.0,       # 1:2 Risk:Reward on SELL setups in Bearish Trend
    'session_filter':       True,      # Filter to Asian (00-07 UTC) + NY Power (13-18 UTC) + Overnight (18-00 UTC)
    'cooldown_bars':        8,         # 8 bars (40 mins) cooldown between trades
}

MCP_SETTINGS = {   'enable_level2_depth': True,
    'enable_portfolio_correlation': True,
    'enable_spread_protection': True,
    'enabled': True,
    'max_spread_atr_multiplier': 0.25}
AI_SETTINGS = {   'accept_lower_confidence': False,
    'confidence_threshold': 0.55,
    'enable_openai': False,
    'market_condition_weight': 0.3,
    'min_confluence_factors': 2,
    'multi_symbol_analysis': True,
    'scalping_mode': False,
    'sentiment_analysis_weight': 0.1,
    'technical_analysis_weight': 0.6}

WEBHOOK_PORT = 5000
WEBHOOK_HOST = '0.0.0.0'
WEBHOOK_PATH = '/webhook'

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

DB_PATH = 'trades.db'
LOG_LEVEL = 'INFO'
LOG_FILE = 'trading_bot.log'

SCHEDULER_INTERVALS = {   'correlation_update': 300,
    'market_analysis': 45,
    'risk_check': 60,
    'signal_check': 30,
    'trade_monitor': 5}
TRADE_QUALITY = {   'max_spread_multiplier': 2,
    'min_atr_multiplier': 1.5,
    'min_volume_filter': True,
    'news_avoidance_hours': 1,
    'session_filter': False,
    'trend_confirmation': True}
