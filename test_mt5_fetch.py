import MetaTrader5 as mt5
import config
from datetime import datetime, timezone
import pandas as pd

mt5.initialize(login=config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER)
symbol = 'BTCUSDm'
sel_res = mt5.symbol_select(symbol, True)
print(f"Symbol selected: {sel_res}, last error: {mt5.last_error()}")

for count in [100, 500, 1000, 5000, 10000, 20000, 50000]:
    r = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, count)
    print(f"Count {count}: {len(r) if r is not None else None}, error: {mt5.last_error()}")

utc_to = datetime.now(timezone.utc)
utc_from = datetime(2023, 1, 1, tzinfo=timezone.utc)
r_range = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M5, utc_from, utc_to)
print(f"Range 2023-now: {len(r_range) if r_range is not None else None}, error: {mt5.last_error()}")

# Also check XAUUSDm to see if history is cached for symbols
r_gold = mt5.copy_rates_from_pos("XAUUSDm", mt5.TIMEFRAME_M5, 0, 10000)
print(f"Gold 5M: {len(r_gold) if r_gold is not None else None}")

mt5.shutdown()
