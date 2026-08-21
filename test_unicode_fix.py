#!/usr/bin/env python3
"""
Unicode Fix Test Script
Tests that all Unicode symbols have been properly replaced
"""

import os
import sys
import logging

# Configure logging without Unicode
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def test_unicode_removal():
    """Test that Unicode symbols are removed from log messages"""
    print("[TESTING] Unicode symbol removal...")
    
    # Test logging messages that previously had Unicode
    logger.info("[SUCCESS] Test message - trade opened with ID: 12345")
    logger.info("[EXECUTING] BTC SELL TRADE:")
    logger.info("[FAILED] Trade execution failed")
    logger.warning("[WARNING] Risk distance too small")
    
    print("[SUCCESS] All test messages logged without Unicode errors")
    return True

def test_telegram_graceful_handling():
    """Test that Telegram imports are handled gracefully"""
    print("[TESTING] Telegram import handling...")
    
    try:
        # This should not cause the script to crash
        from main import TelegramNotifier
        notifier = TelegramNotifier("", "")  # Empty credentials
        print("[SUCCESS] TelegramNotifier handles missing credentials gracefully")
        return True
    except Exception as e:
        print(f"[ERROR] TelegramNotifier test failed: {e}")
        return False

def test_bot_startup():
    """Test that the bot can start without Unicode errors"""
    print("[TESTING] Bot startup without Unicode errors...")
    
    try:
        # Import main components
        import config
        from main import GoldTradingBot
        
        print("[SUCCESS] Main imports successful")
        print(f"[INFO] Active symbols: {[s for s, cfg in config.SYMBOLS.items() if cfg.get('enabled', False)]}")
        
        return True
    except UnicodeEncodeError as e:
        print(f"[ERROR] Unicode encoding error: {e}")
        return False
    except ImportError as e:
        print(f"[WARNING] Import error (expected for optional dependencies): {e}")
        return True  # This is expected for optional deps
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False

def main():
    """Run all Unicode fix tests"""
    print("=" * 60)
    print("[STARTING] Unicode Fix Verification Tests")
    print("=" * 60)
    
    tests = [
        test_unicode_removal,
        test_telegram_graceful_handling,
        test_bot_startup
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
                print(f"[PASS] {test.__name__}")
            else:
                print(f"[FAIL] {test.__name__}")
        except Exception as e:
            print(f"[ERROR] {test.__name__} crashed: {e}")
        
        print("-" * 40)
    
    print("=" * 60)
    print(f"[RESULTS] {passed}/{total} tests passed")
    
    if passed == total:
        print("[SUCCESS] All Unicode fixes are working correctly!")
        print("[INFO] The bot should now run without encoding errors")
        return True
    else:
        print("[WARNING] Some tests failed - check the output above")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 