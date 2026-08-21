# Gold Trading Bot

A fully automated trading bot for gold (XAUUSD) based on Smart Money Concepts (SMC) and ICT trading strategies. This bot integrates with Exness broker, analyzes market data, and executes trades based on predefined strategies.

## Features

- **SMC/ICT Trading Strategies**: Implements liquidity sweeps, break of structure, order blocks, and fair value gaps.
- **Risk Management**: Automatically calculates position sizes based on account balance and risk percentage.
- **Telegram Notifications**: Sends real-time alerts for trades and errors.
- **TradingView Webhook Integration**: Accepts signals from TradingView alerts.
- **Database Logging**: Tracks all trades, signals, and performance metrics.
- **Scheduled Analysis**: Periodically checks for trading opportunities.

## Project Structure

```
gold-trading-bot/
├── main.py              # Core logic (fetch data, strategy, execute)
├── config.py            # Broker API keys, settings
├── indicators.py        # Custom SMC/ICT indicators
├── strategy.py          # Entry/exit logic
├── trade_executor.py    # Buy/sell logic
├── logger.py            # Error/trade logs
├── webhook_listener.py  # Listen to TradingView signals
└── requirements.txt     # Dependencies
```

## Setup Instructions

### 1. Environment Setup

```bash
# Create and activate virtual environment
python -m venv botenv

# On Windows
botenv\Scripts\activate

# On Linux/Mac
source botenv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

1. Create a `.env` file in the project root with your API credentials:

```
EXNESS_API_KEY=your_api_key
EXNESS_API_SECRET=your_api_secret
EXNESS_ACCOUNT_ID=your_account_id
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

2. Adjust trading parameters in `config.py` if needed.

### 3. Telegram Bot Setup (Optional)

1. Create a Telegram bot using BotFather and get the token.
2. Start a chat with your bot and get your chat ID.
3. Add these to your `.env` file.

### 4. TradingView Alerts Setup (Optional)

1. Create a TradingView alert with webhook URL: `http://<your-server-ip>:5000/webhook`
2. Format the alert message as JSON:

```json
{
  "symbol": "XAUUSD",
  "action": "buy",
  "price": {{close}},
  "stop_loss": {{plot("Stop Loss")}},
  "take_profit": {{plot("Take Profit")}},
  "signal_type": "TradingView Alert"
}
```

## Running the Bot

```bash
python main.py
```

## Deployment

### Local Deployment

Run the bot in a terminal that stays open, or use a tool like `screen` or `tmux` on Linux.

### VPS Deployment

1. Set up a VPS with Ubuntu.
2. Clone the repository and follow the setup instructions.
3. Use a process manager like `systemd` or `supervisor` to keep the bot running.

Example systemd service file (`/etc/systemd/system/tradingbot.service`):

```
[Unit]
Description=Gold Trading Bot
After=network.target

[Service]
User=your_username
WorkingDirectory=/path/to/gold-trading-bot
ExecStart=/path/to/gold-trading-bot/botenv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then enable and start the service:

```bash
sudo systemctl enable tradingbot.service
sudo systemctl start tradingbot.service
```

## Trading Strategies

### Strategy 1: Liquidity Sweep + Break of Structure

This strategy looks for:
1. A liquidity sweep (price taking out significant swing highs/lows)
2. Followed by a break of market structure
3. Entry is taken at the close of the candle showing the break of structure
4. Stop loss is placed below/above the swept level
5. Take profit is set at a predefined risk-reward ratio (default: 2R)

### Strategy 2: Order Block / Fair Value Gap Return

This strategy looks for:
1. Identification of significant order blocks or fair value gaps
2. Price returning to these zones
3. Entry is taken when price reaches the zone with confirmation (e.g., bullish/bearish candle)
4. Stop loss is placed below/above the zone
5. Take profit is set at a predefined risk-reward ratio (default: 2R)

## Customization

- Modify `indicators.py` to add or adjust SMC/ICT indicators
- Adjust trading strategies in `strategy.py`
- Change risk parameters in `config.py`

## Disclaimer

Trading involves risk. This bot is provided for educational purposes only. Use at your own risk. Past performance is not indicative of future results.