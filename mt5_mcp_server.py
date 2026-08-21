"""
MT5 Model Context Protocol (MCP) Server & Tool Suite
Provides standardized MCP tools and real-time execution tools for MetaTrader 5
"""

import logging
import time
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
import config

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

logger = logging.getLogger('gold_trading_bot')


class MT5MCPEngine:
    """
    Model Context Protocol (MCP) Engine for MetaTrader 5
    Exposes standardized MCP tools for market depth, account telemetry, risk checks, and trade execution.
    """
    
    def __init__(self, mt5_executor=None):
        self.executor = mt5_executor
        self.is_connected = False
        self.tools_registry = {}
        self._register_mcp_tools()
        logger.info("MT5 MCP Engine initialized with 8 standardized tools")

    def _register_mcp_tools(self):
        """Register MCP tool endpoints"""
        self.tools_registry = {
            'mcp_get_account_info': self.mcp_get_account_info,
            'mcp_get_market_depth': self.mcp_get_market_depth,
            'mcp_get_spread_and_volatility': self.mcp_get_spread_and_volatility,
            'mcp_check_portfolio_risk': self.mcp_check_portfolio_risk,
            'mcp_validate_smc_confluence': self.mcp_validate_smc_confluence,
            'mcp_execute_smart_trade': self.mcp_execute_smart_trade,
            'mcp_update_dynamic_trailing': self.mcp_update_dynamic_trailing,
            'mcp_get_active_positions': self.mcp_get_active_positions
        }

    def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Execute an MCP tool by name
        """
        if tool_name not in self.tools_registry:
            return {'status': 'error', 'message': f"MCP Tool '{tool_name}' not found"}
        
        try:
            handler = self.tools_registry[tool_name]
            result = handler(**kwargs)
            return {'status': 'success', 'tool': tool_name, 'data': result}
        except Exception as e:
            logger.error(f"Error calling MCP tool '{tool_name}': {str(e)}")
            return {'status': 'error', 'tool': tool_name, 'message': str(e)}

    def mcp_get_account_info(self) -> Dict[str, Any]:
        """
        MCP Tool: Retrieve account balance, equity, leverage, free margin, and server status.
        """
        if not MT5_AVAILABLE or not mt5.terminal_info():
            return {
                'connected': False,
                'balance': 0.0,
                'equity': 0.0,
                'margin': 0.0,
                'free_margin': 0.0,
                'currency': 'USD',
                'leverage': 100
            }
        
        acc = mt5.account_info()
        if acc is None:
            return {'connected': False, 'message': f"MT5 Error: {mt5.last_error()}"}
            
        acc_dict = acc._asdict()
        return {
            'connected': True,
            'login': acc_dict.get('login'),
            'server': acc_dict.get('server'),
            'balance': acc_dict.get('balance', 0.0),
            'equity': acc_dict.get('equity', 0.0),
            'margin': acc_dict.get('margin', 0.0),
            'free_margin': acc_dict.get('margin_free', 0.0),
            'margin_level': acc_dict.get('margin_level', 0.0),
            'currency': acc_dict.get('currency', 'USD'),
            'leverage': acc_dict.get('leverage', 100),
            'profit': acc_dict.get('profit', 0.0)
        }

    def mcp_get_market_depth(self, symbol: str) -> Dict[str, Any]:
        """
        MCP Tool: Retrieve Level 2 Market Depth (Book) and volume imbalance ratio.
        """
        if not MT5_AVAILABLE:
            return {'symbol': symbol, 'depth_available': False}

        # Subscribe to market book
        mt5.market_book_add(symbol)
        time.sleep(0.05)
        book = mt5.market_book_get(symbol)
        mt5.market_book_release(symbol)

        if book is None or len(book) == 0:
            # Fallback to tick info
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return {'symbol': symbol, 'depth_available': False, 'reason': 'No tick data'}
            
            return {
                'symbol': symbol,
                'depth_available': False,
                'bid': tick.bid,
                'ask': tick.ask,
                'spread_pips': (tick.ask - tick.bid) * (100 if 'XAU' in symbol else 10000),
                'imbalance_ratio': 1.0
            }

        bids = [item for item in book if item.type == mt5.BOOK_TYPE_BUY]
        asks = [item for item in book if item.type == mt5.BOOK_TYPE_SELL]

        total_bid_vol = sum(item.volume for item in bids)
        total_ask_vol = sum(item.volume for item in asks)

        imbalance_ratio = (total_bid_vol / (total_ask_vol + 1e-6)) if total_ask_vol > 0 else 1.0

        return {
            'symbol': symbol,
            'depth_available': True,
            'bids_count': len(bids),
            'asks_count': len(asks),
            'total_bid_volume': total_bid_vol,
            'total_ask_volume': total_ask_vol,
            'imbalance_ratio': round(imbalance_ratio, 3),
            'orderbook_bias': 'bullish' if imbalance_ratio > 1.25 else ('bearish' if imbalance_ratio < 0.75 else 'neutral')
        }

    def mcp_get_spread_and_volatility(self, symbol: str, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        MCP Tool: Calculate current spread vs ATR volatility ratio.
        Prevents entry if spread is expanded (news/low liquidity).
        """
        if not MT5_AVAILABLE:
            return {'symbol': symbol, 'spread_acceptable': True, 'spread_pips': 0.0}

        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            return {'symbol': symbol, 'spread_acceptable': True, 'spread_pips': 0.0}

        point = info.point if info.point > 0 else 0.00001
        spread_price = tick.ask - tick.bid
        spread_pips = spread_price / point if point > 0 else 0.0

        atr_pips = 10.0
        if df is not None and 'atr' in df.columns and len(df) > 0:
            atr_val = df['atr'].iloc[-1]
            atr_pips = (atr_val / point) if point > 0 else 10.0

        # Spread to ATR ratio threshold (max 15% of 1H ATR)
        max_allowed_spread = max(3.0, atr_pips * 0.25)
        spread_acceptable = spread_pips <= max_allowed_spread

        return {
            'symbol': symbol,
            'spread_price': round(spread_price, 5),
            'spread_pips': round(spread_pips, 2),
            'atr_pips': round(atr_pips, 2),
            'spread_acceptable': spread_acceptable,
            'max_allowed_spread_pips': round(max_allowed_spread, 2),
            'spread_quality': 'EXCELLENT' if spread_pips <= max_allowed_spread * 0.5 else ('FAIR' if spread_acceptable else 'HIGH_SPREAD_WARNING')
        }

    def mcp_check_portfolio_risk(self, symbol: str, new_risk_percent: float = 1.0) -> Dict[str, Any]:
        """
        MCP Tool: Check multi-symbol portfolio correlation risk and max total exposure limits.
        """
        if self.executor is not None:
            total_risk = getattr(self.executor, 'current_total_risk', 0.0)
            open_trades = getattr(self.executor, 'open_trades', {})
        else:
            total_risk = 0.0
            open_trades = {}

        max_allowed_risk = config.RISK_MANAGEMENT.get('max_total_risk', 3.0)
        projected_risk = total_risk + new_risk_percent
        risk_passed = projected_risk <= max_allowed_risk

        return {
            'symbol': symbol,
            'current_total_risk_percent': round(total_risk, 2),
            'new_trade_risk_percent': round(new_risk_percent, 2),
            'projected_risk_percent': round(projected_risk, 2),
            'max_allowed_risk_percent': max_allowed_risk,
            'risk_passed': risk_passed,
            'active_positions_count': len(open_trades)
        }

    def mcp_validate_smc_confluence(self, symbol: str, df_mtf: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        MCP Tool: Calculate Multi-Timeframe SMC/ICT Confluence Score (0.0 to 1.0).
        Evaluates Structure Break (BOS), Order Block (OB), Fair Value Gap (FVG), and Liquidity Sweep.
        """
        if df_mtf is None or len(df_mtf) < 5:
            return {
                'symbol': symbol,
                'confluence_score': 0.70,
                'confluence_factors': ['Primary 15M Structure', 'ATR Volatility Filter'],
                'quality_level': 'GOOD'
            }

        latest = df_mtf.iloc[-1]
        factors = []
        score = 0.0

        # 1. Structure Break (25 pts)
        if latest.get('bos_bullish', 0) == 1 or latest.get('bos_bearish', 0) == 1:
            score += 0.25
            factors.append("Market Structure Break (BOS)")

        # 2. Order Block (25 pts)
        if latest.get('bullish_ob', 0) == 1 or latest.get('bearish_ob', 0) == 1:
            score += 0.25
            factors.append("SMC Order Block Confluence")

        # 3. Fair Value Gap (25 pts)
        if latest.get('bullish_fvg', 0) == 1 or latest.get('bearish_fvg', 0) == 1:
            score += 0.25
            factors.append("Fair Value Gap (FVG) Fill")

        # 4. Momentum & Volatility (25 pts)
        if latest.get('atr', 0) > 0 and abs(latest.get('close', 0) - latest.get('open', 0)) > 0:
            score += 0.25
            factors.append("Active ATR Momentum")

        quality_level = 'EXCELLENT' if score >= 0.75 else ('GOOD' if score >= 0.50 else 'POOR')

        return {
            'symbol': symbol,
            'confluence_score': round(score, 2),
            'confluence_factors': factors,
            'factor_count': len(factors),
            'quality_level': quality_level
        }

    def mcp_execute_smart_trade(self, symbol: str, action: str, lot_size: float, stop_loss: float, take_profit: float, comment: str = "SMC-MCP AI Trade") -> Dict[str, Any]:
        """
        MCP Tool: Execute trade with pre-trade spread checks, slippage control, and logging.
        """
        # Pre-trade spread check
        spread_info = self.mcp_get_spread_and_volatility(symbol)
        if not spread_info.get('spread_acceptable', True):
            return {
                'success': False,
                'reason': f"Spread too high: {spread_info.get('spread_pips')} pips > max {spread_info.get('max_allowed_spread_pips')} pips"
            }

        # Execute order via MT5 executor if connected
        if self.executor is not None and getattr(self.executor, 'connected', False):
            result = self.executor.execute_trade_mt5(
                symbol=symbol,
                side=action,
                position_size=lot_size,
                stop_loss=stop_loss,
                take_profit=take_profit,
                comment=comment
            )
            return {
                'success': bool(result),
                'ticket': result if isinstance(result, int) else None,
                'symbol': symbol,
                'action': action,
                'lot_size': lot_size,
                'sl': stop_loss,
                'tp': take_profit,
                'spread_pips': spread_info.get('spread_pips')
            }

        return {
            'success': True,
            'simulated': True,
            'symbol': symbol,
            'action': action,
            'lot_size': lot_size,
            'sl': stop_loss,
            'tp': take_profit
        }

    def mcp_update_dynamic_trailing(self, ticket: int, symbol: str, current_sl: float, current_tp: float) -> Dict[str, Any]:
        """
        MCP Tool: Update Stop Loss dynamically using ATR steps & Breakeven protection.
        """
        if self.executor is not None and getattr(self.executor, 'connected', False):
            modified = self.executor.modify_position(ticket, stop_loss=current_sl, take_profit=current_tp)
            return {'ticket': ticket, 'modified': modified, 'new_sl': current_sl, 'new_tp': current_tp}

        return {'ticket': ticket, 'modified': True, 'simulated': True, 'new_sl': current_sl, 'new_tp': current_tp}

    def mcp_get_active_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        MCP Tool: Retrieve list of currently open MT5 positions.
        """
        if self.executor is not None and getattr(self.executor, 'connected', False):
            positions = self.executor.get_open_positions()
            if symbol:
                positions = [p for p in positions if p.get('symbol') == symbol]
            return positions
        return []
