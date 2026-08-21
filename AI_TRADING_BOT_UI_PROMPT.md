# Trading Bot Dashboard — Full-Stack UI Generation Prompt
## Mapped directly from config.py & Integrated with Gemini AI CLI

---

## Bot Summary

| Property | Value |
|---|---|
| AI Engine | Google Gemini AI (`gemini-1.5-pro` / `gemini-pro`) + OpenAI (`gpt-4o-mini`) + Local RandomForest ML |
| Broker | Exness MT5 |
| Symbols | XAUUSDm · BTCUSDm · USOILm · EURUSDm |
| Strategy Modes | `mcp_enhanced` · `standard_ai` · `scalping` |
| MCP | MT5 Tool Engine (orderbook depth, spread, correlation) |
| Notifications | Telegram Bot |
| Database | SQLite `trades.db` |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, TailwindCSS v3 |
| State Management | Zustand |
| Charts | Recharts (Equity AreaChart, Symbol Distribution Donut, Monthly P&L BarChart) |
| Real-time Data | WebSocket `ws://localhost:8000/ws` |
| HTTP Client | Axios with interceptors |
| AI Integration | Google Gemini API (`@google/generative-ai`) + Gemini CLI Natural Language Layer |
| Backend Shim | FastAPI (`api_server.py`) — wraps existing Python MT5 trading bot |

---

## Backend API Contract (`api_server.py`)

```
GET    /api/config           → returns full config dict parsed from config.py
PUT    /api/config           → updates config.py via AST/regex patch & hot-reloads bot
GET    /api/account          → { balance, equity, margin, free_margin, profit }
GET    /api/positions        → [ { ticket, symbol, type, lots, open_price, sl, tp, profit, open_time } ]
POST   /api/positions/open   → { symbol, direction, lots, sl, tp } → opens a trade
POST   /api/positions/close  → { ticket } → closes a trade
POST   /api/positions/modify → { ticket, sl, tp } → modifies open position SL/TP
POST   /api/bot/start        → starts trading bot loop in background thread
POST   /api/bot/stop         → stops trading bot loop
GET    /api/bot/status       → { running: bool, uptime: seconds, strategy_mode, active_symbols }
GET    /api/history          → [ { ticket, symbol, type, lots, open_price, close_price, profit, duration } ]
GET    /api/performance      → aggregated metrics from trades.db (win rate, profit factor, max drawdown, sharpe)
POST   /api/backtest         → { strategy, symbol, timeframe, start_date, end_date, initial_balance }
GET    /api/backtest/:id     → returns backtest progress / completed results
POST   /api/ai/command       → natural language trade execution via Gemini AI
WS     /ws                   → streams live { account, positions, tick, log, signal, trade_event }
```

---

## Application Layout

**Left Sidebar** (collapsible, 180px) + **Top Header Bar** + **Main Content Area**.

### Sidebar Nav Items (6 Pages)
1. 📊 Dashboard
2. 📈 Live Trades
3. ⚙️ Configuration (12 detailed sections mapped to `config.py`)
4. 🤖 AI Settings (Gemini CLI / OpenAI / RandomForest switches & weight controls)
5. 🧪 Backtesting (SSE/polling backtest engine with comparative metrics)
6. 📋 Logs (4-tab terminal stream: Bot Logs, Trade Events, AI Decisions, MT5 Raw)

### Top Header Bar
- Left: Logo "TradeBot AI" + strategy mode badge (`MCP Enhanced` / `Standard AI` / `Scalping`)
- Center: Live Account Stats (Balance | Equity | Free Margin | Daily P&L) via WebSocket
- Right: Bot Status Pill (🟢 Running / 🔴 Stopped) + Start/Stop toggle button + Gemini AI Chat Floating Launcher Button

---

## Page 1 — Dashboard

### Metric Cards Row (4 cards)
| Card | Source | Indicator |
|---|---|---|
| Account Balance | `account.balance` | Neutral |
| Open P&L | Sum of open position profits | Green if positive, Red if negative |
| Active Symbols | Count of enabled symbols in `SYMBOLS` config | Neutral |
| Today's Win Rate | Calculated from `trades.db` | Green ≥55%, Amber 45-55%, Red <45% |

### Charts Section
- **Left (60%):** Equity Curve `AreaChart` with historical trade dot overlays (green=win, red=loss) & time selector (1D | 1W | 1M | All).
- **Right (40%):** Donut Chart showing trade distribution by symbol (XAUUSDm, BTCUSDm, USOILm, EURUSDm).

### Active Symbol Status Cards Grid (1 card per symbol in `SYMBOLS`)
- Symbol Name + Enabled Toggle (live updates `enabled` state in config)
- Risk % | TP Ratio | Scalping Mode Badge
- Open Trade Count for that symbol
- Last Signal summary

---

## Page 2 — Live Trades

### Open Positions Table
Columns: Ticket | Symbol | Type (BUY/SELL badge) | Lots | Open Price | Current Price | SL | TP | Profit ($) | Profit (%) | Duration | Actions

- Real-time updates via WebSocket with animated profit flash (green/red)
- Actions: [Modify SL/TP] [Close Trade]
- Row clicking opens Trade Detail Drawer (right side panel)

### Manual Trade Panel (Right Drawer / Modal)
- Symbol dropdown (XAUUSDm, BTCUSDm, USOILm, EURUSDm)
- Direction BUY/SELL toggle
- Lot size input + slider
- Stop Loss & Take Profit (pip inputs with auto price calculation)
- Risk Calculator showing exact dollar risk amount
- [Open Trade] button calling `POST /api/positions/open`

### Gemini AI Trade Command Bar (Bottom Panel)
- Natural language chat input: "Open a BUY on EURUSDm with 0.1 lots, 20 pip SL and 40 pip TP"
- Gemini CLI processes prompt, parses structured `action` blocks, and renders Confirmation Card:
  ```
  Gemini Action Proposal:
  Action: OPEN_TRADE | Symbol: EURUSDm | Direction: BUY | Lots: 0.1 | SL: 20 pips | TP: 40 pips
  [Confirm & Execute Trade] [Cancel]
  ```
- Supports commands: "Close all losing trades", "Move SL on ticket #12345 to breakeven", "Show today's performance"
- Keeps last 20 messages history with timestamp and response status.

---

## Page 3 — Configuration (Mapped directly to `config.py`)

### 12 Detailed Configuration Sections

1. **MT5 Connection**: MT5 Login, Password (show/hide), MT5 Server, Account ID, [Test Connection] button.
2. **Symbol Configuration (2x2 Grid)**: Per-symbol card (XAUUSDm, BTCUSDm, USOILm, EURUSDm) with Enabled toggle (dims card when disabled), expandable to:
   - *Risk & Sizing*: Risk per trade (%), TP Ratio, Min R:R, Max Trades, Fixed Lot Size toggle/input.
   - *Trailing Settings*: Start ratio (% of TP), Trail step, Breakeven ratio, Trail TP toggle, Trail SL toggle.
   - *Feature Flags*: Volatility Adjustment, Correlation Filter, Scalping Mode toggles.
3. **Global Risk Management** (`RISK_MANAGEMENT`): Max Total Risk %, Max Correlated Risk %, Correlation Threshold, Volatility Lookback, Dynamic Sizing toggle, Max Drawdown Stop %, Daily Loss Limit %, Consecutive Loss Limit, Max Daily Trades.
4. **Trailing Algorithm Settings** (`TRAILING_SETTINGS`): Algorithm (Simple, ATR, Enhanced ATR, Parabolic), ATR Multiplier, Min Trail Distance, Trail Frequency (seconds), Swing Levels toggle, Consolidation Filter toggle.
5. **Strategy & Timeframes**:
   - Strategy Mode Segmented Control: `MCP Enhanced` | `Standard AI` | `Scalping`
   - Timeframes: Primary, Confirmation list, Precision list.
6. **ICT / SMC Settings** (`ICT_SETTINGS`): London/NY/Asian Session Time range pickers, Power of Three windows (Accumulation, Manipulation, Distribution), Order Block lookback, Liquidity Sweep tolerance, FVG min size, Premium/Discount Fib levels.
7. **MCP Settings** (`MCP_SETTINGS`, visible when `mcp_enhanced`): Master toggle, Level 2 Depth toggle, Spread Protection toggle, Portfolio Correlation filter toggle, Max Spread ATR Multiplier.
8. **Scheduler Intervals** (`SCHEDULER_INTERVALS`): Signal check (s), Trade monitor (s), Market analysis (s), Correlation update (s), Risk check (s) with visual timeline diagram.
9. **Trade Quality Filters** (`TRADE_QUALITY`): Min ATR Multiplier, Max Spread Multiplier, Low Volume Filter, Trend Confirmation, Session Filter, News Avoidance Window (hours).
10. **Telegram Notifications**: Telegram Token, Chat ID, [Send Test Message], Notify on Open/Close/Error toggles, Daily Summary time picker.
11. **System Settings**: Log Level (DEBUG/INFO/WARNING/ERROR), Log File path, DB path, Webhook Port/Host/Path.
12. **Legacy Single Symbol**: Backward compatibility controls (`SYMBOL`, `RISK_PERCENT`, `TP_RATIO`, `SL_PADDING`).

**Sticky Save Bar**: Dirty state indicator (orange dot), [Save Configuration] button showing diff toast (e.g. "5 fields changed") on update.

---

## Page 4 — AI Settings

### AI Engine Selector
Toggle between:
- **Google Gemini AI CLI** (`gemini-1.5-pro` / `gemini-pro`)
- **OpenAI API** (`gpt-4o-mini` / `gpt-4o`)
- **Local RandomForest ML Model**

### Gemini AI CLI Options Panel (when Gemini selected)
- Gemini API Key input (show/hide)
- Gemini Model dropdown (`gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-pro`)
- Natural Language Auto-Execute toggle (if off, AI presents confirmation card; if on, auto-executes high-confidence trades)
- AI Confidence Threshold Slider (50%–95%) with color-coded gauge (red <50%, amber 50-60%, green >60%)
- [Test Gemini Connection] button with response speed benchmark

### OpenAI Options Panel (when OpenAI selected)
- OpenAI API Key, Model selector (`gpt-4o-mini`, `gpt-4o`, `gpt-4-turbo`), Max Tokens (100–2000), Temperature (0.0–2.0), API Key test button.

### RandomForest ML Panel (when ML selected)
- Model File Path input, Feature count (14 features read-only), Retrain button, Last trained date, Feature importance horizontal bar chart.

### AI Analysis Weights (Must sum to 1.0)
- Technical Analysis Weight slider (default 0.6)
- Market Condition Weight slider (default 0.3)
- Sentiment Analysis Weight slider (default 0.1)
- *Auto-balances remaining sliders when one is adjusted.*

---

## Page 5 — Backtesting

### Left Panel (Parameters & Overrides)
- Strategy Mode, Symbol, Timeframe, Date Range (Start/End), Initial Balance ($)
- Config Overrides toggle (Risk %, TP Ratio, Min R:R, Confidence threshold, Scalping toggle)
- [Run Backtest] button with SSE/polling progress log (`[✓] Loading historical data... [⟳] Simulating 1240 / 5000 candles...`)

### Right Panel (Results)
- Summary Metric Cards: Total P&L, Win Rate, Profit Factor, Max Drawdown, Sharpe Ratio, Total Trades
- Equity Curve AreaChart with trade dot overlays
- Per-Symbol P&L BarChart & Monthly P&L BarChart
- Sortable & Filterable Trade List Table with CSV export
- Strategy Comparison Split View (compare SMC vs ICT vs Scalping side-by-side)

---

## Page 6 — Logs

### 4-Tab Terminal Interface
1. **Bot Logs**: Monospace dark terminal stream with timestamp, log level colors (INFO gray, SUCCESS green, WARNING amber, ERROR red, DEBUG blue), filter pills, search input, auto-scroll toggle, export `.log` button.
2. **Trade Events**: Table of `SIGNAL_GENERATED`, `ORDER_SENT`, `ORDER_FILLED`, `SL_HIT`, `TP_HIT`, `TRAILING_UPDATED`, `BREAKEVEN_SET`.
3. **AI Decisions**: Table of Gemini/OpenAI/RandomForest calls with symbol, confidence score, signal, and full payload JSON viewer modal.
4. **MT5 Raw**: Detailed MT5 terminal connection events and raw IPC message logs.

---

## Floating Gemini AI Assistant Component (`GeminiChat.jsx`)
- Accessible from top bar button on every page as a floating modal/drawer.
- Supports voice/text natural language trade management, portfolio querying, strategy configuration advice, and instant command execution.

---

## Visual Design System
- **Background**: `#0d1117` | **Cards**: `#161b22` | **Border**: `#30363d`
- **Profits**: `#00d395` | **Losses**: `#f85149` | **Accent**: `#58a6ff`
- **Symbol Color Palette**:
  - XAUUSDm: Amber (`#d29922`)
  - BTCUSDm: Orange (`#f78166`)
  - USOILm: Blue (`#58a6ff`)
  - EURUSDm: Green (`#00d395`)
- **Typography**: Inter (Google Fonts)

---

## Setup & Implementation Folder Structure

Create isolated implementation folder `E:\Trading\trading_app` so original code remains untouched:

```
trading_app/
├── api_server.py                ← FastAPI shim wrapping config.py & MT5 bot
├── config.py                    ← copied from parent for isolated modification
├── frontend/                    ← React 18 + Vite + TailwindCSS application
│   ├── src/
│   │   ├── api/                 ← Axios API client
│   │   ├── components/          ← GeminiChat, TradeTable, SymbolCard, EquityChart, LogViewer, etc.
│   │   ├── store/               ← Zustand stores (configStore, accountStore, positionStore, logStore)
│   │   ├── pages/               ← Dashboard, LiveTrades, Configuration, AISettings, Backtesting, Logs
│   │   └── App.jsx
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
```
