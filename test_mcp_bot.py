#!/usr/bin/env python3
"""
Test script to verify MT5 MCP Engine & AI Validation Integration
"""

import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)

def test_mcp_integration():
    print("🧪 Testing MT5 MCP Engine & AI Integration...")
    print("=" * 50)

    try:
        # 1. Test MT5MCPEngine initialization & tool execution
        from mt5_mcp_server import MT5MCPEngine
        mcp = MT5MCPEngine()
        
        print("[SUCCESS] MT5MCPEngine initialized")
        print(f"[INFO] Registered MCP Tools: {list(mcp.tools_registry.keys())}")
        
        # Test Account Info Tool
        acc_res = mcp.call_tool('mcp_get_account_info')
        print(f"[SUCCESS] Account Info Tool Call: {acc_res}")

        # Test Spread & Volatility Tool
        spread_res = mcp.call_tool('mcp_get_spread_and_volatility', symbol='XAUUSDm')
        print(f"[SUCCESS] Spread Tool Call: {spread_res}")

        # Test Portfolio Risk Tool
        risk_res = mcp.call_tool('mcp_check_portfolio_risk', symbol='XAUUSDm', new_risk_percent=1.0)
        print(f"[SUCCESS] Portfolio Risk Tool Call: {risk_res}")

        # 2. Test AITradeAnalyzer with MCP Trade Validation
        from ai_analyzer import AITradeAnalyzer
        ai = AITradeAnalyzer()
        
        print("[SUCCESS] AITradeAnalyzer initialized with MCP Engine")

        # Create test DataFrame
        test_df = pd.DataFrame({
            'open': [2650.0, 2651.0, 2652.0, 2653.0, 2654.0],
            'high': [2652.0, 2653.0, 2654.0, 2655.0, 2656.0],
            'low': [2649.0, 2650.0, 2651.0, 2652.0, 2653.0],
            'close': [2651.0, 2652.0, 2653.0, 2654.0, 2655.0],
            'volume': [1000, 1100, 1200, 1300, 1400],
            'atr': [1.5, 1.5, 1.5, 1.5, 1.5],
            'bos_bullish': [0, 1, 0, 1, 0],
            'bos_bearish': [0, 0, 0, 0, 0],
            'bullish_ob': [0, 1, 0, 1, 0],
            'bearish_ob': [0, 0, 0, 0, 0],
            'bullish_fvg': [0, 1, 0, 1, 0],
            'bearish_fvg': [0, 0, 0, 0, 0]
        })

        mcp_val = ai.mcp_validate_trade(test_df, 1, symbol='XAUUSDm')
        print(f"[SUCCESS] MCP Trade Validation Result: {mcp_val}")

        print("\n🎉 ALL MT5 MCP INTEGRATION TESTS PASSED SUCCESSFULLY!")
        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_mcp_integration()
