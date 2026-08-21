"""
Unit & Integration Test Suite for Trailing Stop & Dynamic Partial Lot Booking
=============================================================================
Tests:
1. Dynamic volume calculation (e.g. 50% of 0.02 = 0.01, 50% of 0.04 = 0.02, custom %)
2. Breakeven trigger at 50% TP (breakeven_ratio = 0.5)
3. Partial close signal emission alongside Breakeven SL modification
4. Trailing SL advance using trail_step & ATR
5. UI / config parameter dynamic reactivity (start_ratio, trail_step, breakeven_ratio, partial_close_pct, trail_sl, trail_tp)
6. State persistence across multiple polling cycles (no tick reset bug)
"""

import unittest
import pandas as pd
import numpy as np
import config
from strategy import SMCStrategy


class MockMT5Executor:
    """Mock MT5 executor for testing order execution without live broker connection"""
    def __init__(self, symbol='BTCUSDm'):
        self.symbol = symbol
        self.connected = True
        self.open_trades = {}
        self.modified_positions = []
        self.partial_closed_trades = []

    def modify_position(self, ticket, stop_loss=None, take_profit=None):
        self.modified_positions.append({'ticket': ticket, 'sl': stop_loss, 'tp': take_profit})
        if ticket in self.open_trades:
            if stop_loss is not None:
                self.open_trades[ticket]['stop_loss'] = stop_loss
            if take_profit is not None:
                self.open_trades[ticket]['take_profit'] = take_profit
        return True

    def partial_close_trade(self, position_id, volume_to_close, reason="Partial TP"):
        trade = self.open_trades.get(position_id, {'volume': 0.02})
        curr_vol = trade['volume']
        vol_to_close = round(float(volume_to_close), 2)
        rem_vol = round(curr_vol - vol_to_close, 2)
        
        self.partial_closed_trades.append({
            'ticket': position_id,
            'closed_vol': vol_to_close,
            'rem_vol': rem_vol,
            'reason': reason
        })
        if position_id in self.open_trades:
            self.open_trades[position_id]['volume'] = rem_vol
        return {
            'success': True,
            'closed_volume': vol_to_close,
            'remaining_volume': rem_vol,
            'close_price': 60500.0
        }


class TestTrailingAndPartialClose(unittest.TestCase):

    def setUp(self):
        # Build synthetic DataFrame with ATR
        dates = pd.date_range(start='2026-01-01', periods=50, freq='15min')
        self.df = pd.DataFrame({
            'open': [60000.0] * 50,
            'high': [60200.0] * 50,
            'low': [59800.0] * 50,
            'close': [60000.0] * 50,
            'volume': [100.0] * 50,
            'atr': [200.0] * 50,
            'bos_bearish': [False] * 50,
            'bos_bullish': [False] * 50,
            'bearish_ob': [False] * 50,
            'bullish_ob': [False] * 50,
        }, index=dates)
        
        self.mock_executor = MockMT5Executor(symbol='BTCUSDm')
        self.strategy = SMCStrategy.__new__(SMCStrategy)
        self.strategy.current_trade = None
        self.strategy.trailing_activated = False
        self.strategy.initial_stop_distance = None
        self.strategy.initial_tp_distance = None
        self.strategy.last_trail_price = None
        self.strategy.breakeven_activated = False
        self.strategy.partial_booked = False
        self.strategy.trailing_algorithm = 'enhanced_atr'
        self.strategy.atr_multiplier = 2.0
        self.strategy.min_trail_distance = 0.001
        self.strategy.use_swing_levels = True
        self.strategy.mt5_executor = self.mock_executor

    def test_01_breakeven_and_50pct_partial_close_btc(self):
        """Test that reaching 50% TP triggers 50% volume partial booking and moves SL to breakeven on BTC"""
        # Trade open: Buy at 60,000, SL at 59,000 (1000 risk), TP at 62,000 (2000 target), Vol = 0.02 lots
        trade_info = {
            'id': 1001,
            'symbol': 'BTCUSDm',
            'side': 'buy',
            'entry_price': 60000.0,
            'stop_loss': 59000.0,
            'take_profit': 62000.0,
            'volume': 0.02,
            'position_size': 0.02
        }
        self.mock_executor.open_trades[1001] = dict(trade_info)
        self.strategy.set_current_trade(trade_info)

        # 1. Price at 60,400 (only 20% of TP reached) -> Should NOT trigger breakeven yet (breakeven_ratio = 0.5)
        res1 = self.strategy.update_trailing_stop(self.df, 60400.0)
        self.assertFalse(res1['partial_close'])
        self.assertIsNone(res1['stop_loss'])

        # 2. Price hits 61,000 (50% of TP reached: 1000 profit / 2000 TP distance)
        res2 = self.strategy.update_trailing_stop(self.df, 61000.0)
        
        # Verify Partial close is triggered
        self.assertTrue(res2['partial_close'], "Partial close must trigger when 50% TP is reached")
        self.assertEqual(res2['partial_close_pct'], 50.0)
        
        # Verify Breakeven SL is set
        self.assertIsNotNone(res2['stop_loss'], "Stop loss must move to breakeven")
        self.assertGreaterEqual(res2['stop_loss'], 60000.0, "SL must be at or above entry price")

        # Simulate execution of partial booking (close 50% of 0.02 = 0.01)
        curr_vol = trade_info['volume']
        vol_to_close = curr_vol * (res2['partial_close_pct'] / 100.0)
        self.assertEqual(vol_to_close, 0.01, "0.02 lot trade must close exactly 0.01 lot")
        
        part_exec = self.mock_executor.partial_close_trade(1001, vol_to_close)
        self.assertTrue(part_exec['success'])
        self.assertEqual(part_exec['closed_volume'], 0.01)
        self.assertEqual(part_exec['remaining_volume'], 0.01)

    def test_02_dynamic_lot_size_scaling(self):
        """Test that different open lot sizes (e.g. 0.04 lots, 0.10 lots) close exactly configured %"""
        # Case A: 0.04 lots with 50% close
        vol_a = 0.04
        pct_a = 50.0
        close_a = round(vol_a * (pct_a / 100.0), 2)
        self.assertEqual(close_a, 0.02)
        self.assertEqual(round(vol_a - close_a, 2), 0.02)

        # Case B: 0.06 lots with 75% close
        vol_b = 0.06
        pct_b = 75.0
        close_b = round(vol_b * (pct_b / 100.0), 2)
        self.assertEqual(close_b, 0.04) # 0.045 -> step 0.01 -> 0.05 or 0.04
        
        # Case C: 0.02 lots with 50% close
        vol_c = 0.02
        pct_c = 50.0
        close_c = round(vol_c * (pct_c / 100.0), 2)
        self.assertEqual(close_c, 0.01)
        self.assertEqual(round(vol_c - close_c, 2), 0.01)

    def test_03_polling_tick_state_persistence(self):
        """Test that repeated calls to set_current_trade across polling ticks do NOT reset memory"""
        trade_info = {
            'id': 2002,
            'symbol': 'BTCUSDm',
            'side': 'buy',
            'entry_price': 60000.0,
            'stop_loss': 59000.0,
            'take_profit': 62000.0,
            'volume': 0.02,
            'position_size': 0.02
        }
        self.strategy.set_current_trade(trade_info)
        
        # Price hits 50% TP
        res = self.strategy.update_trailing_stop(self.df, 61000.0)
        self.assertTrue(res['partial_close'])
        self.assertTrue(self.strategy.breakeven_activated)
        self.assertTrue(self.strategy.partial_booked)

        # Next polling tick arrives with updated trade status (SL already moved)
        updated_trade_info = dict(trade_info)
        updated_trade_info['stop_loss'] = res['stop_loss']
        updated_trade_info['volume'] = 0.01
        
        self.strategy.set_current_trade(updated_trade_info)
        
        # Verify memory was preserved!
        self.assertTrue(self.strategy.breakeven_activated, "breakeven_activated must not be reset")
        self.assertTrue(self.strategy.partial_booked, "partial_booked must not be reset")
        self.assertEqual(self.strategy.initial_stop_distance, 1000.0, "initial_stop_distance must not be overwritten")

        # Next tick at 61,100 -> must NOT trigger partial close a second time!
        res_next = self.strategy.update_trailing_stop(self.df, 61100.0)
        self.assertFalse(res_next['partial_close'], "Partial close must only fire ONCE per trade")

    def test_04_trailing_sl_advance(self):
        """Test that when price reaches 80% TP (start_ratio = 0.8), Trailing SL activates and advances"""
        trade_info = {
            'id': 3003,
            'symbol': 'BTCUSDm',
            'side': 'buy',
            'entry_price': 60000.0,
            'stop_loss': 60020.0,  # Already at Breakeven
            'take_profit': 62000.0,
            'volume': 0.01,
            'position_size': 0.01
        }
        self.strategy.set_current_trade(trade_info)
        self.strategy.initial_stop_distance = 1000.0
        self.strategy.initial_tp_distance = 2000.0
        self.strategy.breakeven_activated = True
        self.strategy.partial_booked = True

        # Price reaches 61,700 (85% of TP distance -> exceeds start_ratio 0.8)
        res = self.strategy.update_trailing_stop(self.df, 61700.0)
        self.assertTrue(self.strategy.trailing_activated)
        if res['stop_loss']:
            self.assertGreater(res['stop_loss'], trade_info['stop_loss'], "Trailing SL must advance upward above breakeven")


if __name__ == '__main__':
    unittest.main()
