#!/usr/bin/env python3
"""
Multi-Symbol Trading Bot Runner
"""

import sys
import os
import time
import logging

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    """Main entry point with error handling"""
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot_runner.log'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger('bot_runner')
    logger.info("STARTING Multi-Symbol Trading Bot...")
    
    try:
        # Test imports first
        logger.info("Testing imports...")
        
        import config
        logger.info(f"SUCCESS - Config loaded - Enabled symbols: {[s for s, cfg in config.SYMBOLS.items() if cfg.get('enabled')]}")
        
        from main import GoldTradingBot
        logger.info("SUCCESS - Main bot class imported")
        
        # Create and start bot
        logger.info("Creating bot instance...")
        bot = GoldTradingBot()
        
        logger.info("Starting bot...")
        bot.start()
        
    except ImportError as e:
        logger.error(f"ERROR - Import error: {e}")
        logger.error("Please install dependencies: pip install -r requirements.txt")
        return False
        
    except Exception as e:
        logger.error(f"ERROR - Error starting bot: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nINFO - Bot stopped by user")
    except Exception as e:
        print(f"ERROR - Unexpected error: {e}")
        sys.exit(1) 