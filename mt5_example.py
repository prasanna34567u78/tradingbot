# Example script for using MT5 integration

import logging
import time
from datetime import datetime

# Import custom modules
import config
from mt5_executor import MT5Executor

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('mt5_example')

def main():
    # Create MT5 executor instance with credentials from config
    mt5_executor = MT5Executor(
        login=config.MT5_LOGIN,
        password=config.MT5_PASSWORD,
        server=config.MT5_SERVER
    )
    logger.info(f"mts {mt5_executor.connected}")
    # Check if connection was successful
    if not mt5_executor.connected:
        logger.error("Failed to connect to MT5. Please check your credentials.")
        return
    
    try:
        # Get account balance
        balance = mt5_executor.get_account_balance()
        logger.info(f"Account balance: {balance}")
        
        # Get current price
        price = mt5_executor.get_current_price()
        if price:
            logger.info(f"Current price for {mt5_executor.symbol}: Bid={price['bid']}, Ask={price['ask']}")
        
        # Get open positions
        positions = mt5_executor.get_open_positions()
        logger.info(f"Open positions: {len(positions)}")
        for pos in positions:
            logger.info(f"Position: {pos['ticket']}, Symbol: {pos['symbol']}, Type: {'BUY' if pos['type'] == 0 else 'SELL'}, Volume: {pos['volume']}")
        
        # Example of how to execute a trade
        
        # Example: Buy 0.01 lots of XAUUSD with SL and TP
        current_price = mt5_executor.get_current_price()
        if current_price:
            entry_price = current_price['ask']
            stop_loss = entry_price - 10  # 10 points below entry
            take_profit = entry_price + 20  # 20 points above entry
            
            trade_id = mt5_executor.execute_trade(
                signal=1,  # 1 for buy, -1 for sell
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                position_size=0.01,  # 0.01 lots
                signal_type="Manual Example"
            )
            
            if trade_id:
                logger.info(f"Trade executed with ID: {trade_id}")
                
                # Wait a bit and then close the trade
                time.sleep(5)
                
                # Close the trade
                if mt5_executor.close_trade(trade_id,position_size=0.01,signal_type="Manual Example"):
                    logger.info(f"Trade {trade_id} closed successfully")
                else:
                    logger.error(f"Failed to close trade {trade_id}")
        
        
    except Exception as e:
        logger.error(f"Error in MT5 example: {str(e)}")
    finally:
        # Shutdown MT5 connection
        mt5_executor.shutdown()
        logger.info("MT5 connection closed")

if __name__ == "__main__":
    main()