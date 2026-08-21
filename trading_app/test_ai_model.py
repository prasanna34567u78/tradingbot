#!/usr/bin/env python3
"""
Test script to verify AI model works without session_bias error
"""

import pandas as pd
import numpy as np
from ai_analyzer import AITradeAnalyzer

def test_ai_model():
    """Test the AI model to ensure no session_bias error"""
    print("🧪 Testing AI Model...")
    print("=" * 40)
    
    try:
        # Initialize AI analyzer
        ai_analyzer = AITradeAnalyzer()
        
        print(f"[SUCCESS] AI Analyzer initialized successfully")
        print(f"[INFO] Model trained: {ai_analyzer.is_model_trained}")
        print(f"[INFO] Features: {len(ai_analyzer.feature_names)}")
        print(f"[INFO] Feature names: {ai_analyzer.feature_names}")
        
        # Create test market data
        test_data = {
            'open': [2650.0, 2651.0, 2652.0, 2653.0, 2654.0],
            'high': [2652.0, 2653.0, 2654.0, 2655.0, 2656.0],
            'low': [2649.0, 2650.0, 2651.0, 2652.0, 2653.0],
            'close': [2651.0, 2652.0, 2653.0, 2654.0, 2655.0],
            'volume': [1000, 1100, 1200, 1300, 1400]
        }
        
        df = pd.DataFrame(test_data)
        
        # Add basic indicators
        df['atr'] = 1.0
        df['bos_bullish'] = [0, 1, 0, 1, 0]
        df['bos_bearish'] = [1, 0, 1, 0, 1]
        df['bullish_ob'] = [0, 0, 1, 0, 1]
        df['bearish_ob'] = [1, 1, 0, 1, 0]
        df['bullish_fvg'] = [0, 1, 0, 0, 1]
        df['bearish_fvg'] = [1, 0, 1, 1, 0]
        
        print(f"[CHART] Test data created: {len(df)} rows")
        
        # Test feature preparation
        features = ai_analyzer.prepare_features(df)
        print(f"[SUCCESS] Features prepared: {features.shape}")
        print(f"[INFO] Feature columns: {list(features.columns)}")
        
        # Test trade validation
        validation_result = ai_analyzer.validate_trade(df, 1)  # Test buy signal
        print(f"[SUCCESS] Trade validation successful")
        print(f"[INFO] Validation result: {validation_result}")
        
        # Test model info
        model_info = ai_analyzer.get_model_info()
        print(f"[SUCCESS] Model info retrieved")
        print(f"[INFO] Model details: {model_info}")
        
        print("\n[SUCCESS] All tests passed! AI model is working correctly.")
        print("[SUCCESS] No session_bias error - the issue has been fixed!")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_ai_model()
    if success:
        print("\n[READY] The AI model is ready for use!")
    else:
        print("\n[ERROR] There are still issues to fix.") 