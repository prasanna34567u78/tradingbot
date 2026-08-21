# Webhook listener for TradingView signals

from flask import Flask, request, jsonify
import json
import logging
import threading
import config
from datetime import datetime

logger = logging.getLogger('gold_trading_bot')


class WebhookListener:
    """
    Class to handle webhook signals from TradingView
    """
    
    def __init__(self, signal_handler, host=config.WEBHOOK_HOST, port=config.WEBHOOK_PORT, path=config.WEBHOOK_PATH):
        self.app = Flask(__name__)
        self.host = host
        self.port = port
        self.path = path
        self.signal_handler = signal_handler
        self.server_thread = None
        self.is_running = False
        
        # Register routes
        self._register_routes()
    
    def _register_routes(self):
        """
        Register Flask routes
        """
        @self.app.route(self.path, methods=['POST'])
        def webhook():
            if request.method == 'POST':
                try:
                    # Get data from request
                    data = request.get_json()
                    
                    # Log the received webhook
                    logger.info(f"Received webhook: {json.dumps(data)}")
                    
                    # Process the signal
                    self._process_signal(data)
                    
                    return jsonify({'status': 'success'}), 200
                except Exception as e:
                    logger.error(f"Error processing webhook: {str(e)}")
                    return jsonify({'status': 'error', 'message': str(e)}), 500
            else:
                return jsonify({'status': 'error', 'message': 'Method not allowed'}), 405
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()}), 200
    
    def _process_signal(self, data):
        """
        Process the signal from TradingView
        
        Args:
            data: Signal data from TradingView
        """
        try:
            # Extract signal information
            # The exact structure depends on how you set up your TradingView alerts
            # Here's an example structure:
            # {
            #     "symbol": "XAUUSD",
            #     "action": "buy",  # or "sell"
            #     "price": 1950.25,
            #     "stop_loss": 1945.50,
            #     "take_profit": 1960.00,
            #     "signal_type": "Liquidity Sweep + BOS"
            # }
            
            # Validate required fields
            required_fields = ['symbol', 'action', 'price']
            for field in required_fields:
                if field not in data:
                    logger.error(f"Missing required field in webhook: {field}")
                    return
            
            # Convert action to signal
            signal = 1 if data['action'].lower() == 'buy' else -1 if data['action'].lower() == 'sell' else 0
            
            if signal == 0:
                logger.error(f"Invalid action in webhook: {data['action']}")
                return
            
            # Extract other fields with defaults
            symbol = data['symbol']
            entry_price = float(data['price'])
            stop_loss = float(data.get('stop_loss', 0))
            take_profit = float(data.get('take_profit', 0))
            signal_type = data.get('signal_type', 'TradingView Alert')
            
            # If stop_loss or take_profit are not provided, calculate them based on risk-reward
            if stop_loss == 0 or take_profit == 0:
                # Use default values based on recent price action
                # This is a simplified example - you would need to implement a more sophisticated approach
                if signal == 1:  # Buy
                    stop_loss = entry_price * 0.995  # 0.5% below entry
                    take_profit = entry_price * 1.01  # 1% above entry
                else:  # Sell
                    stop_loss = entry_price * 1.005  # 0.5% above entry
                    take_profit = entry_price * 0.99  # 1% below entry
            
            # Pass the signal to the handler
            self.signal_handler({
                'symbol': symbol,
                'signal': signal,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'signal_type': signal_type,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error processing signal: {str(e)}")
    
    def start(self):
        """
        Start the webhook listener in a separate thread
        """
        if self.is_running:
            logger.warning("Webhook listener is already running")
            return
        
        def run_server():
            self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
        
        self.server_thread = threading.Thread(target=run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        self.is_running = True
        logger.info(f"Webhook listener started on {self.host}:{self.port}{self.path}")
    
    def stop(self):
        """
        Stop the webhook listener
        """
        if not self.is_running:
            logger.warning("Webhook listener is not running")
            return
        
        # Flask doesn't provide a clean way to stop the server from another thread
        # In a production environment, you would use a more robust server like gunicorn
        # For now, we'll just set the flag and let the main thread handle shutdown
        self.is_running = False
        logger.info("Webhook listener stopped")


# Example usage:
# def signal_handler(signal_data):
#     print(f"Received signal: {signal_data}")
#     # Process the signal (e.g., execute a trade)

# webhook_listener = WebhookListener(signal_handler)
# webhook_listener.start()