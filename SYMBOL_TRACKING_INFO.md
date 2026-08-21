# Enhanced Symbol Signal Tracking

## Overview
I've added comprehensive logging to help you track which symbols are being checked for signals and their analysis progress.

## New Logging Features

### 1. **Signal Check Cycle Start/End**
```
=== SIGNAL CHECK CYCLE STARTED - Checking 3 symbols ===
...
=== SIGNAL CHECK CYCLE COMPLETED ===
```

### 2. **Individual Symbol Processing**
```
>>> CHECKING SIGNALS FOR: XAUUSDm
  ├─ XAUUSDm: Risk checks passed, starting analysis...
  ├─ XAUUSDm: Current trades: 0, Max allowed: 1
>>> COMPLETED signal check for: XAUUSDm
```

### 3. **Multi-Timeframe Analysis Progress**
```
  ├─ XAUUSDm: Analyzing 4 timeframes...
  │  ├─ 4h: bullish trend, Price: 2685.123
  │  ├─ 1h: bullish trend, Price: 2685.456
  │  ├─ 15m: neutral trend, Price: 2685.789
  │  ├─ 5m: bullish trend, Price: 2685.234
```

### 4. **Confluence Detection**
```
  ├─ XAUUSDm: Checking confluence across 4 timeframes...
  ├─ XAUUSDm: CONFLUENCE FOUND! Signal: BUY (confidence: 75.2%)
  ├─ XAUUSDm: Correlation risk acceptable, proceeding with BUY signal...
```

### 5. **Skip Reasons**
```
  └─ BTCUSDm: Max trades reached (1/1) - SKIPPED
  └─ USOILm: Global risk limits exceeded - SKIPPED
  └─ XAUUSDm: No confluence signal found - NO TRADE
  └─ BTCUSDm: Correlation risk too high for BUY signal - BLOCKED
```

## How to Monitor

### **Real-time Monitoring**
Watch the log file to see which symbol is currently being analyzed:
```bash
tail -f trading_bot.log
```

### **Filter by Symbol**
To see activity for a specific symbol:
```bash
grep "XAUUSDm" trading_bot.log
```

### **Signal Detection Only**
To see only when signals are found:
```bash
grep "CONFLUENCE FOUND" trading_bot.log
```

## Log Hierarchy

The logging uses a tree structure to show analysis flow:

- `===` : Cycle boundaries
- `>>>` : Symbol processing start/end
- `├─`  : Main symbol actions
- `│  ├─` : Sub-actions (timeframe analysis)
- `└─`  : Final outcomes (skip/block reasons)

## Expected Flow

1. **Cycle Start** → Lists how many symbols will be checked
2. **For Each Symbol:**
   - Risk checks
   - Timeframe analysis (4h, 1h, 15m, 5m)
   - Confluence calculation
   - Correlation risk check
   - Signal execution (if all checks pass)
3. **Cycle Complete** → Ready for next cycle

## Benefits

✅ **Clear Visibility**: See exactly which symbol is being processed  
✅ **Debug Support**: Identify where analysis fails  
✅ **Performance Tracking**: Monitor analysis speed per symbol  
✅ **Risk Monitoring**: See why trades are blocked  
✅ **Confluence Insight**: Understand signal strength across timeframes

Now you can easily track which symbol the bot is analyzing and why certain trading decisions are made! 