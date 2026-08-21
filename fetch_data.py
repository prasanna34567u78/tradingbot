"""
BTCUSDm V3 Quantitative Research & Validation Suite
Phases 1 to 24 on REAL MT5 Data
"""

import os
import sys
import time
import json
import warnings
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

warnings.filterwarnings("ignore")
sys.path.insert(0, "E:\\Trading")
import config

DATA_DIR = "E:\\Trading\\data"
os.makedirs(DATA_DIR, exist_ok=True)

def connect_mt5():
    if not mt5.initialize(login=config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER):
        if not mt5.initialize():
            raise RuntimeError("Failed to connect to MT5")
    return True

def fetch_and_save_data(symbol="BTCUSDm"):
    connect_mt5()
    tf_dict = {
        "5m": mt5.TIMEFRAME_M5,
        "15m": mt5.TIMEFRAME_M15,
        "1h": mt5.TIMEFRAME_H1,
        "d1": mt5.TIMEFRAME_D1
    }
    data_files = {}
    for name, tf in tf_dict.items():
        print(f"Fetching {name} data for {symbol}...")
        # Get as many bars as possible
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, 100000)
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.rename(columns={'tick_volume': 'volume'}, inplace=True)
            path = os.path.join(DATA_DIR, f"{symbol}_{name}.csv")
            df.to_csv(path, index=False)
            data_files[name] = path
            print(f"  -> Saved {len(df):,} bars to {path} ({df['time'].min()} to {df['time'].max()})")
        else:
            print(f"  -> Failed to fetch {name}")
    
    # Also get symbol specifications
    s_info = mt5.symbol_info(symbol)
    spec = {}
    if s_info:
        spec = {
            "symbol": symbol,
            "digits": s_info.digits,
            "point": s_info.point,
            "spread": s_info.spread,
            "trade_contract_size": s_info.trade_contract_size,
            "volume_min": s_info.volume_min,
            "volume_max": s_info.volume_max,
            "volume_step": s_info.volume_step,
            "currency_base": s_info.currency_base,
            "currency_profit": s_info.currency_profit,
            "trade_tick_size": s_info.trade_tick_size,
            "trade_tick_value": s_info.trade_tick_value,
        }
        with open(os.path.join(DATA_DIR, f"{symbol}_spec.json"), "w") as f:
            json.dump(spec, f, indent=2)
        print(f"Symbol specs saved: {spec}")
    mt5.shutdown()
    return data_files, spec

if __name__ == "__main__":
    fetch_and_save_data()
