#!/usr/bin/env python3
"""
Test script to check for import errors and basic functionality
"""

import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test all imports"""
    print("Testing imports...")
    
    try:
        # Test basic imports
        import pandas as pd
        import numpy as np
        print("[SUCCESS] pandas and numpy imported successfully")
        
        # Test config import
        import config
        print("[SUCCESS] config imported successfully")
        print(f"   - Active symbols: {list(config.SYMBOLS.keys())}")
        print(f"   - Enabled symbols: {[s for s, cfg in config.SYMBOLS.items() if cfg.get('enabled', False)]}")
        
        # Test indicators import
        from indicators import SMCIndicators
        print("[SUCCESS] SMCIndicators imported successfully")
        
        # Test strategy import
        from strategy import SMCStrategy
        print("[SUCCESS] SMCStrategy imported successfully")
        
        # Test MT5 executor import
        from mt5_executor import MT5Executor
        print("[SUCCESS] MT5Executor imported successfully")
        
        # Test AI analyzer import
        from ai_analyzer import AITradeAnalyzer
        print("[SUCCESS] AITradeAnalyzer imported successfully")
        
        # Test logger import
        from logger import TradeLogger
        print("[SUCCESS] TradeLogger imported successfully")
        
        # Test optional imports
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            print("[SUCCESS] APScheduler imported successfully")
        except ImportError as e:
            print(f"[ERROR] APScheduler import failed: {e}")
            
        try:
            from telegram import Bot
            print("[SUCCESS] Telegram Bot imported successfully")
        except ImportError as e:
            print(f"[WARNING] Telegram Bot import failed (optional): {e}")
            print("   This is optional - bot will work without Telegram notifications")
            
        try:
            import MetaTrader5 as mt5
            print("[SUCCESS] MetaTrader5 imported successfully")
        except ImportError as e:
            print(f"[ERROR] MetaTrader5 import failed: {e}")
            
    except Exception as e:
        print(f"[ERROR] Import error: {e}")
        return False
    
    return True

def test_config_validation():
    """Test configuration validation"""
    print("\nTesting configuration...")
    
    try:
        import config
        
        # Check symbols configuration
        enabled_symbols = [s for s, cfg in config.SYMBOLS.items() if cfg.get('enabled', False)]
        print(f"[SUCCESS] Enabled symbols: {enabled_symbols}")
        
        # Check risk management settings
        risk_mgmt = config.RISK_MANAGEMENT
        print(f"[SUCCESS] Risk management configured:")
        print(f"   - Max total risk: {risk_mgmt.get('max_total_risk', 'N/A')}%")
        print(f"   - Max correlated risk: {risk_mgmt.get('max_correlated_risk', 'N/A')}%")
        print(f"   - Correlation threshold: {risk_mgmt.get('correlation_threshold', 'N/A')}")
        
        # Check trailing settings
        trailing = config.TRAILING_SETTINGS
        print(f"[SUCCESS] Trailing settings:")
        print(f"   - Algorithm: {trailing.get('algorithm', 'N/A')}")
        print(f"   - ATR multiplier: {trailing.get('atr_multiplier', 'N/A')}")
        
        # Validate symbol configurations
        for symbol, cfg in config.SYMBOLS.items():
            if cfg.get('enabled', False):
                required_keys = ['risk_percent', 'tp_ratio', 'min_rr_ratio', 'trailing_settings']
                missing_keys = [key for key in required_keys if key not in cfg]
                if missing_keys:
                    print(f"[WARNING] {symbol} missing keys: {missing_keys}")
                else:
                    print(f"[SUCCESS] {symbol} configuration complete")
        
    except Exception as e:
        print(f"[ERROR] Configuration error: {e}")
        return False
    
    return True

def test_basic_functionality():
    """Test basic class instantiation"""
    print("\nTesting basic functionality...")
    
    try:
        # Test strategy creation
        from strategy import SMCStrategy
        strategy = SMCStrategy()
        print("[SUCCESS] SMCStrategy created successfully")
        
        # Test indicators
        from indicators import SMCIndicators
        indicators = SMCIndicators()
        print("[SUCCESS] SMCIndicators created successfully")
        
        # Test AI analyzer (without MT5)
        from ai_analyzer import AITradeAnalyzer
        ai_analyzer = AITradeAnalyzer()
        print("[SUCCESS] AITradeAnalyzer created successfully")
        
        # Test sample data processing
        import pandas as pd
        import numpy as np
        
        # Create sample OHLC data
        dates = pd.date_range('2024-01-01', periods=100, freq='15min')
        sample_data = pd.DataFrame({
            'open': np.random.uniform(2000, 2100, 100),
            'high': np.random.uniform(2050, 2150, 100),
            'low': np.random.uniform(1950, 2050, 100),
            'close': np.random.uniform(2000, 2100, 100),
            'volume': np.random.uniform(1000, 5000, 100)
        }, index=dates)
        
        # Test indicators on sample data
        processed_data = indicators.apply_all_indicators(sample_data)
        print("[SUCCESS] Indicators processing works")
        
        # Test strategy analysis
        analyzed_data = strategy.analyze_market(processed_data)
        print("[SUCCESS] Strategy analysis works")
        
    except Exception as e:
        print(f"[ERROR] Functionality error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def main():
    """Main test function"""
    print("[STARTING] Multi-Symbol Trading Bot Tests\n")
    
    # Run tests
    tests = [
        test_imports,
        test_config_validation,
        test_basic_functionality
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"[ERROR] Test {test.__name__} failed with exception: {e}")
    
    print(f"\n[TEST RESULTS] {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! Bot should be ready to run.")
        return True
    else:
        print("⚠️  Some tests failed. Please fix the issues before running the bot.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 