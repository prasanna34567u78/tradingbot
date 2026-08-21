# Trade execution module for the Gold Trading Bot

import ccxt
import time
import config
import logging
from datetime import datetime

logger = logging.getLogger('gold_trading_bot')


class TradeExecutor:
    """
    Class to handle trade execution with Exness broker
    """
    
    def __init__(self, api_key=config.API_KEY, api_secret=config.API_SECRET, account_id=config.ACCOUNT_ID):
        self.api_key = api_key
        self.api_secret = api_secret
        self.account_id = account_id
        self.symbol = config.SYMBOL
        self.exchange = None
        self.connected = False
        self.open_trades = {}
        
        # Initialize connection to Exness
        self._initialize_connection()
    
    def _initialize_connection(self):
        """
        Initialize connection to Exness via CCXT
        """
        try:
            # Initialize exchange
            self.exchange = ccxt.exness({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',  # Use 'future' for futures trading
                }
            })
            
            # Load markets
            self.exchange.load_markets()
            
            # Check if symbol exists
            if self.symbol not in self.exchange.markets:
                logger.error(f"Symbol {self.symbol} not found in available markets")
                return False
            
            # Test connection
            self.exchange.fetch_balance()
            self.connected = True
            logger.info("Successfully connected to Exness")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize connection to Exness: {str(e)}")
            self.connected = False
            return False
    
    def get_account_balance(self):
        """
        Get account balance
        
        Returns:
            Account balance in USD
        """
        try:
            balance = self.exchange.fetch_balance()
            return balance['total']['USD']
        except Exception as e:
            logger.error(f"Failed to fetch account balance: {str(e)}")
            return None
    
    def get_current_price(self):
        """
        Get current price for the symbol
        
        Returns:
            Current bid and ask prices
        """
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return {
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'last': ticker['last']
            }
        except Exception as e:
            logger.error(f"Failed to fetch current price: {str(e)}")
            return None
    
    def execute_trade(self, signal, entry_price, stop_loss, take_profit, position_size, signal_type):
        """
        Execute a trade based on the signal
        
        Args:
            signal: Trade signal (1 for buy, -1 for sell)
            entry_price: Entry price for the trade
            stop_loss: Stop loss price for the trade
            take_profit: Take profit price for the trade
            position_size: Position size in lots
            signal_type: Type of signal that generated the trade
            
        Returns:
            Trade ID if successful, None otherwise
        """
        if not self.connected:
            if not self._initialize_connection():
                logger.error("Cannot execute trade: Not connected to Exness")
                return None
        
        try:
            # Determine order type
            side = 'buy' if signal > 0 else 'sell'
            
            # Get current market price
            current_price = self.get_current_price()
            if not current_price:
                logger.error("Cannot execute trade: Failed to get current price")
                return None
            
            # Use market order for entry
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='market',
                side=side,
                amount=position_size
            )
            
            # Get order details
            order_id = order['id']
            filled_price = float(order['price']) if 'price' in order else entry_price
            
            # Place stop loss order
            sl_order = self.exchange.create_order(
                symbol=self.symbol,
                type='stop',
                side='sell' if side == 'buy' else 'buy',
                amount=position_size,
                price=stop_loss,
                params={
                    'stopPrice': stop_loss,
                    'reduceOnly': True
                }
            )
            
            # Place take profit order
            tp_order = self.exchange.create_order(
                symbol=self.symbol,
                type='limit',
                side='sell' if side == 'buy' else 'buy',
                amount=position_size,
                price=take_profit,
                params={
                    'reduceOnly': True
                }
            )
            
            # Store trade information
            trade_info = {
                'id': order_id,
                'symbol': self.symbol,
                'side': side,
                'entry_price': filled_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'position_size': position_size,
                'signal_type': signal_type,
                'entry_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'sl_order_id': sl_order['id'],
                'tp_order_id': tp_order['id']
            }
            
            self.open_trades[order_id] = trade_info
            
            logger.info(f"Trade executed: {side.upper()} {self.symbol} at {filled_price}, SL: {stop_loss}, TP: {take_profit}, Size: {position_size}")
            
            return order_id
            
        except Exception as e:
            logger.error(f"Failed to execute trade: {str(e)}")
            return None
    
    def close_trade(self, trade_id):
        """
        Close a specific trade
        
        Args:
            trade_id: ID of the trade to close
            
        Returns:
            True if successful, False otherwise
        """
        if trade_id not in self.open_trades:
            logger.error(f"Trade ID {trade_id} not found in open trades")
            return False
        
        try:
            trade = self.open_trades[trade_id]
            
            # Create market order to close position
            close_side = 'sell' if trade['side'] == 'buy' else 'buy'
            
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='market',
                side=close_side,
                amount=trade['position_size'],
                params={
                    'reduceOnly': True
                }
            )
            
            # Cancel stop loss and take profit orders
            try:
                self.exchange.cancel_order(trade['sl_order_id'], self.symbol)
                self.exchange.cancel_order(trade['tp_order_id'], self.symbol)
            except Exception as e:
                logger.warning(f"Failed to cancel SL/TP orders: {str(e)}")
            
            # Remove from open trades
            del self.open_trades[trade_id]
            
            logger.info(f"Trade closed: {trade_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to close trade {trade_id}: {str(e)}")
            return False
    
    def close_all_trades(self):
        """
        Close all open trades
        
        Returns:
            Number of trades closed successfully
        """
        closed_count = 0
        trade_ids = list(self.open_trades.keys())  # Create a copy of keys
        
        for trade_id in trade_ids:
            if self.close_trade(trade_id):
                closed_count += 1
        
        return closed_count
    
    def get_open_trades(self):
        """
        Get all open trades
        
        Returns:
            Dictionary of open trades
        """
        return self.open_trades
    
    def update_trade_status(self):
        """
        Update the status of all open trades
        
        Returns:
            Updated open trades dictionary
        """
        try:
            # Fetch open positions
            positions = self.exchange.fetch_positions([self.symbol])
            
            # Update trade information based on current positions
            for position in positions:
                if float(position['contracts']) > 0:  # Position is open
                    # Find corresponding trade in open_trades
                    for trade_id, trade in self.open_trades.items():
                        if trade['symbol'] == position['symbol'] and trade['side'] == position['side']:
                            # Update trade information
                            trade['current_price'] = float(position['markPrice'])
                            trade['unrealized_pnl'] = float(position['unrealizedPnl'])
                            trade['updated_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            return self.open_trades
            
        except Exception as e:
            logger.error(f"Failed to update trade status: {str(e)}")
            return self.open_trades
    
    def fetch_historical_data(self, timeframe=config.TIMEFRAME, limit=100):
        """
        Fetch historical OHLCV data
        
        Args:
            timeframe: Timeframe for the data (e.g., '1h', '4h', '1d')
            limit: Number of candles to fetch
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Fetch OHLCV data
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe, limit=limit)
            
            # Convert to DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch historical data: {str(e)}")
            return None