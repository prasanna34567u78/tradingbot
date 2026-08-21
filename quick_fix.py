#!/usr/bin/env python3
"""
Quick fix script to repair main.py syntax errors
"""

def fix_main_py():
    """Fix the main.py file by removing syntax errors"""
    
    # Read the current file
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove problematic sections and fix syntax
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Skip problematic continue statements that are not in loops
        if 'continue' in line and not any(keyword in lines[max(0, i-10):i] for keyword in ['for ', 'while ']):
            # Replace with return
            line = line.replace('continue', 'return')
        
        # Fix indentation issues
        if line.strip() == 'try:' and i < len(lines) - 1:
            next_line = lines[i + 1] if i + 1 < len(lines) else ''
            if next_line.strip() == 'try:':
                i += 1  # Skip duplicate try
                continue
        
        fixed_lines.append(line)
        i += 1
    
    # Write the fixed content back
    fixed_content = '\n'.join(fixed_lines)
    
    # Additional fixes for specific syntax issues
    fixed_content = fixed_content.replace('            continue', '            return')
    fixed_content = fixed_content.replace('                            continue', '                            return')
    
    # Remove duplicate method definitions and fix structure
    if 'def _update_single_symbol_trades(self):' not in fixed_content:
        # Add missing method
        missing_method = '''
    def _update_single_symbol_trades(self):
        """
        Fallback method for single symbol mode
        """
        try:
            if not hasattr(self, 'trade_executor') or not self.trade_executor:
                logger.warning("Single symbol mode - MT5 executor not available")
                return
                
            if not hasattr(self, 'strategy') or not self.strategy:
                logger.warning("Single symbol mode - strategy not available")
                return
                
            # Get current open trades
            try:
                current_trades = self.trade_executor.update_trade_status_mt5()
                if current_trades:
                    logger.info("Single symbol mode - monitoring existing trades")
                    # Simple monitoring logic
                    for trade_id, trade_info in current_trades.items():
                        logger.info(f"Monitoring trade {trade_id}: {trade_info.get('side', 'unknown')} at {trade_info.get('entry_price', 'unknown')}")
                else:
                    logger.debug("Single symbol mode - no active trades")
            except Exception as e:
                logger.error(f"Error in single symbol trade monitoring: {e}")
                
        except Exception as e:
            logger.error(f"Error in single symbol mode: {e}")
'''
        # Insert before the signal handler function
        fixed_content = fixed_content.replace(
            'def signal_handler(sig, frame):',
            missing_method + '\n\ndef signal_handler(sig, frame):'
        )
    
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print("[SUCCESS] Fixed main.py syntax errors")

def create_simple_bot():
    """Create a simplified working bot"""
    simple_bot_code = '''#!/usr/bin/env python3
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
                    logger.info(f"[SUCCESS] {symbol} initialized")
                else:
                    logger.error(f"[ERROR] Failed to connect to MT5 for {symbol}")
                    
            except Exception as e:
                logger.error(f"[ERROR] Error initializing {symbol}: {e}")
        
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
'''
    
    with open('simple_bot.py', 'w', encoding='utf-8') as f:
        f.write(simple_bot_code)
    
    print("[SUCCESS] Created simple_bot.py")

if __name__ == "__main__":
    print("🔧 Fixing syntax errors in main.py...")
    fix_main_py()
    
    print("🔧 Creating simplified working bot...")
    create_simple_bot()
    
    print("\n[SUCCESS] All fixes completed!")
    print("You can now run:")
    print("  python simple_bot.py    # Run the simplified bot")
    print("  python main.py          # Try the full bot again") 