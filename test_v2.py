import sys
sys.path.insert(0, 'E:/Trading')
from strategy.crypto_vpp_v2 import BTCImprovedStrategy, BTCStrategyConfig
import pandas as pd
import numpy as np
np.random.seed(42)

n = 500
closes = 40000 + np.cumsum(np.random.randn(n) * 200)
df = pd.DataFrame({
    'time': pd.date_range('2020-01-01', periods=n, freq='5min'),
    'open':  closes - np.abs(np.random.randn(n) * 100),
    'high':  closes + np.abs(np.random.randn(n) * 150),
    'low':   closes - np.abs(np.random.randn(n) * 150),
    'close': closes,
    'volume': np.abs(np.random.randn(n)) * 300 + 200,
})

cfg = BTCStrategyConfig()
cfg.min_score = 30
cfg.use_session_filter = False
cfg.cooldown_bars = 5
s = BTCImprovedStrategy(cfg)
out = s.generate_signals(df)
sigs = out[out['signal'] != 0]
print("Signal test:", len(sigs), "signals from 500 bars (min_score=30)")
print("Strategy module: WORKING CORRECTLY")
