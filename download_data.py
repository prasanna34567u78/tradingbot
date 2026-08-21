import MetaTrader5 as mt5
import config
import pandas as pd
import os
import json
from datetime import datetime, timezone

DATA_DIR = "E:\\Trading\\data"
os.makedirs(DATA_DIR, exist_ok=True)

print("Init MT5...", flush=True)
if not mt5.initialize(login=config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER):
    if not mt5.initialize():
        raise RuntimeError("MT5 init failed")

symbol = "BTCUSDm"
mt5.symbol_select(symbol, True)

s_info = mt5.symbol_info(symbol)
if s_info:
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
    print("Specs saved:", spec, flush=True)

# Fetch up to max bars for each timeframe
# Note: 50,000 5m bars is ~173 days. Let's also fetch 15m (50,000 bars is ~520 days), 1h (30,000 bars is ~1250 days / ~3.4 years), 1d (5000 bars is ~13 years).
for name, tf, count in [
    ('5m', mt5.TIMEFRAME_M5, 50000),
    ('15m', mt5.TIMEFRAME_M15, 50000),
    ('1h', mt5.TIMEFRAME_H1, 30000),
    ('4h', mt5.TIMEFRAME_H4, 15000),
    ('1d', mt5.TIMEFRAME_D1, 5000)
]:
    print(f"Fetching {name} ({count} bars)...", flush=True)
    r = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if r is not None and len(r) > 0:
        df = pd.DataFrame(r)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.rename(columns={'tick_volume': 'volume'}, inplace=True)
        path = os.path.join(DATA_DIR, f"{symbol}_{name}.csv")
        df.to_csv(path, index=False)
        print(f"  -> Saved {len(df):,} bars to {path} ({df['time'].min()} to {df['time'].max()})", flush=True)
    else:
        print(f"  -> Failed to fetch {name}: {mt5.last_error()}", flush=True)

mt5.shutdown()
print("DOWNLOAD COMPLETE!", flush=True)
