#!/usr/bin/env python3
"""
Simplified working multi-symbol trading bot
"""

import time
import logging
import pandas as pd
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simple_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('simple_bot')

def main():
    """Main function"""
    logger.info("Starting Simplified Multi-Symbol Trading Bot...")
    
    try:
        import config
        from mt5_executor import MT5Executor
        from strategy import SMCStrategy
        from apscheduler.schedulers.background import BackgroundScheduler
        
        # Get enabled symbols
        enabled_symbols = [s for s, cfg in config.SYMBOLS.items() if cfg.get('enabled', False)]
        logger.info(f"Enabled symbols: {enabled_symbols}")
        
        if not enabled_symbols:
            logger.error("No symbols enabled!")
            return
        
        # Initialize components for each symbol
        executors = {}
        strategies = {}
        
        for symbol in enabled_symbols:
            try:
                logger.info(f"Initializing {symbol}...")
                
                executor = MT5Executor(
                    login=config.MT5_LOGIN,
                    password=config.MT5_PASSWORD,
                    server=config.MT5_SERVER,
                    symbol=symbol
                )
                
                if executor.connected:
                    executors[symbol] = executor
                    
                    symbol_config = config.SYMBOLS[symbol]
                    strategy = SMCStrategy(
                        executor,
                        risk_percent=symbol_config.get('risk_percent', 1.0),
                        tp_ratio=symbol_config.get('tp_ratio', 2.0)
                    )
                    strategies[symbol] = strategy
                    logger.info(f"SUCCESS: {symbol} initialized")
                else:
                    logger.error(f"ERROR: Failed to connect to MT5 for {symbol}")
                    
            except Exception as e:
                logger.error(f"ERROR: Error initializing {symbol}: {e}")
        
        if not executors:
            logger.error("No symbols successfully initialized!")
            return
        
        logger.info(f"Bot ready with {len(executors)} symbols")
        
        # Simple monitoring loop
        while True:
            try:
                for symbol, executor in executors.items():
                    try:
                        # Check current positions
                        positions = executor.get_open_positions()
                        if positions:
                            logger.info(f"{symbol}: {len(positions)} open positions")
                        else:
                            logger.debug(f"{symbol}: No open positions")
                    except Exception as e:
                        logger.error(f"Error monitoring {symbol}: {e}")
                
                # Wait 30 seconds before next check
                time.sleep(30)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(60)  # Wait longer if there's an error
        
        # Cleanup
        for executor in executors.values():
            try:
                executor.shutdown()
            except:
                pass
                
        logger.info("Bot stopped")
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
