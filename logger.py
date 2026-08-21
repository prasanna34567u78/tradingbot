# Logger module for the Gold Trading Bot

import logging
import os
from datetime import datetime
import config

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure the logger
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('gold_trading_bot')


class TradeLogger:
    """
    Class to handle trade logging and notifications
    """
    def __init__(self, telegram_notifier=None):
        self.logger = logger
        self.telegram = telegram_notifier
        
    def log_trade(self, action, symbol, entry_price, stop_loss, take_profit, position_size, reason=""):
        """
        Log trade details to file and send notification
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        trade_info = f"TRADE: {action} {symbol} at {entry_price}, SL: {stop_loss}, TP: {take_profit}, Size: {position_size}, Reason: {reason}"
        
        # Log to file
        self.logger.info(trade_info)
        
        # Send Telegram notification if configured
        if self.telegram:
            message = f"TRADE EXECUTED\n\n" \
                     f"*Action:* {action}\n" \
                     f"*Symbol:* {symbol}\n" \
                     f"*Entry:* {entry_price}\n" \
                     f"*Stop Loss:* {stop_loss}\n" \
                     f"*Take Profit:* {take_profit}\n" \
                     f"*Position Size:* {position_size}\n" \
                     f"*Reason:* {reason}\n" \
                     f"*Time:* {timestamp}"
            self.telegram.send_message(message)
    
    def log_error(self, error_message, error_details=None):
        """
        Log error details
        """
        self.logger.error(f"ERROR: {error_message}")
        if error_details:
            self.logger.error(f"Details: {error_details}")
            
        # Send Telegram notification for critical errors
        if self.telegram:
            message = f"WARNING - *ERROR ALERT*\n\n" \
                     f"*Error:* {error_message}\n"
            if error_details:
                message += f"*Details:* {error_details}\n"
            self.telegram.send_message(message)
    
    def log_info(self, message):
        """
        Log informational message
        """
        self.logger.info(message)
    
    def log_signal(self, signal_type, symbol, price, details=None):
        """
        Log trading signal
        """
        signal_info = f"SIGNAL: {signal_type} detected on {symbol} at price {price}"
        if details:
            signal_info += f", Details: {details}"
        
        self.logger.info(signal_info)
        
        # Send Telegram notification for signals
        if self.telegram:
            message = f"🔍 *SIGNAL DETECTED*\n\n" \
                     f"*Type:* {signal_type}\n" \
                     f"*Symbol:* {symbol}\n" \
                     f"*Price:* {price}\n"
            if details:
                message += f"*Details:* {details}\n"
            self.telegram.send_message(message)