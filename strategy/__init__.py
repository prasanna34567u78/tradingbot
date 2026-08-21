"""
BTC Improved Strategy Package & SMC Strategy Package
=====================================================
Modular, institutional-grade trading system.
"""

import sys
import os

# Expose SMCStrategy from root strategy.py if available
try:
    import importlib.util
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    strat_py_path = os.path.join(root_dir, 'strategy.py')
    if os.path.exists(strat_py_path):
        spec = importlib.util.spec_from_file_location("root_strategy", strat_py_path)
        root_strategy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(root_strategy)
        SMCStrategy = getattr(root_strategy, 'SMCStrategy', None)
except Exception:
    pass

