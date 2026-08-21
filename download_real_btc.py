import os
import sys
import json
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

sys.path.insert(0, "E:\\Trading")
import config

DATA_DIR = "E:\\Trading\\data"
os.makedirs(DATA_DIR, exist_ok=True)

def download_data():
    print("=" * 70)
    print("   DOWNLOADING REAL MT5 DATA FOR BTCUSDm")
    print("=" * 70)
    
    if not mt5.initialize(login=config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER):
        if not mt5.initialize():
            raise RuntimeError(f"MT5 Init failed: {mt5.last_error()}")
            
    symbol = "BTCUSDm"
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Failed to select symbol {symbol}")
        
    s_info = mt5.symbol_info(symbol)
    spec = {
        "symbol": symbol,
        "digits": s_info.digits,
        "point": s_info.point,
        "spread_points": s_info.spread,
        "contract_size": s_info.trade_contract_size,
        "volume_min": s_info.volume_min,
        "volume_max": s_info.volume_max,
        "volume_step": s_info.volume_step,
        "currency_base": s_info.currency_base,
        "currency_profit": s_info.currency_profit,
        "tick_size": s_info.trade_tick_size,
        "tick_value": s_info.trade_tick_value,
        "margin_initial": s_info.margin_initial,
        "server_time": str(datetime.now(timezone.utc))
    }
    with open(os.path.join(DATA_DIR, f"{symbol}_spec.json"), "w") as f:
        json.dump(spec, f, indent=2)
    print("Symbol Specs saved.")
    
    timeframes = {
        "5m": (mt5.TIMEFRAME_M5, 50000),
        "15m": (mt5.TIMEFRAME_M15, 50000),
        "1h": (mt5.TIMEFRAME_H1, 30000),
        "4h": (mt5.TIMEFRAME_H4, 15000),
        "1d": (mt5.TIMEFRAME_D1, 5000)
    }
    
    for name, (tf, max_bars) in timeframes.items():
        print(f"Fetching {name} (up to {max_bars:,} bars)...")
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, max_bars)
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.rename(columns={'tick_volume': 'volume'}, inplace=True)
            filepath = os.path.join(DATA_DIR, f"{symbol}_{name}.csv")
            df.to_csv(filepath, index=False)
            print(f"  -> Saved {len(df):,} {name} bars | {df['time'].min()} to {df['time'].max()}")
        else:
            print(f"  -> Failed to fetch {name}: {mt5.last_error()}")
            
    mt5.shutdown()
    print("\nDownload complete!")

if __name__ == "__main__":
    download_data()
