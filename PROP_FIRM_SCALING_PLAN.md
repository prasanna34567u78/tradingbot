# 🚀 Prop Firm Scaling Blueprint — Multi-Account Automated Trading System

> **Version:** 1.0  
> **Date:** September 2026  
> **Author:** Trading Bot Project  
> **Status:** Research & Planning Phase

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Trading Platform APIs — Complete Reference](#2-trading-platform-apis--complete-reference)
   - [MatchTrader API (Full Details)](#21-matchtrader-api-full-details)
   - [cTrader Open API](#22-ctrader-open-api)
   - [TradeLocker API](#23-tradelocker-api)
   - [DXtrade API](#24-dxtrade-api)
   - [Tradovate API (Futures)](#25-tradovate-api-futures)
   - [MetaTrader 5 (MT5)](#26-metatrader-5-mt5)
3. [Platform Comparison Matrix](#3-platform-comparison-matrix)
4. [Prop Firm → Platform Mapping](#4-prop-firm--platform-mapping)
5. [Multi-Account Architecture — Hub & Spoke Model](#5-multi-account-architecture--hub--spoke-model)
6. [Dynamic Risk Scaling Per Account Size](#6-dynamic-risk-scaling-per-account-size)
7. [Prop Firm Rule Enforcement Engine](#7-prop-firm-rule-enforcement-engine)
8. [Anti-Detection & Anti-Correlation Strategies](#8-anti-detection--anti-correlation-strategies)
9. [Technology Stack Recommendations](#9-technology-stack-recommendations)
10. [Account Configuration Schema](#10-account-configuration-schema)
11. [Step-by-Step Roadmap — From Zero to Prop Firm Empire](#11-step-by-step-roadmap--from-zero-to-prop-firm-empire)
12. [Cost Analysis & ROI Projections](#12-cost-analysis--roi-projections)
13. [Common Pitfalls & How to Avoid Them](#13-common-pitfalls--how-to-avoid-them)

---

## 1. Executive Summary

This document is a comprehensive blueprint for scaling the Sweep Structure trading bot across **multiple funded accounts from different prop firms**, with different account sizes, platforms, and rule sets. 

### The Vision
```
┌──────────────────────────────────────────────────────┐
│              MASTER CONTROL HUB (Your VPS)           │
│                                                      │
│   Signal Engine → Sweep Structure Strategy           │
│   News Filter  → ForexFactory Feed                   │
│   Risk Engine   → Per-Account DD Enforcement         │
│                                                      │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│   │ Worker 1│ │ Worker 2│ │ Worker 3│ │ Worker N│  │
│   │ FTMO    │ │FundedNxt│ │Fund Pips│ │ The5ers │  │
│   │ $100K   │ │ $200K   │ │ $50K    │ │ $40K    │  │
│   │ cTrader │ │MatchTr  │ │ MT5     │ │ cTrader │  │
│   └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
└──────────────────────────────────────────────────────┘
```

### Key Numbers
- **Your Current Setup:** 1× Exness MT5 Trial account, Sweep Structure strategy on XAUUSDm + USTECm + US30m
- **Backtest Results:** +77.81% return ($778 on $1000) with <10% max drawdown over 1 year
- **Scaling Target:** 5-20 funded accounts across 3-5 prop firms = potential **$500K–$2M+ in managed capital**

---

## 2. Trading Platform APIs — Complete Reference

### 2.1 MatchTrader API (Full Details)

> **Used by:** FundingPips, FundedNext (US), E8 Markets, Maven Trading, Blue Guardian, City Traders Imperium, Crypto Fund Trader, Ment Funding

#### Overview
Match-Trader (by Match-Trade Technologies) is a **B2B white-label platform**. It provides rich REST + WebSocket APIs, but **retail API access depends entirely on the prop firm enabling it**. Many prop firms disable API access, returning `403 Forbidden`.

#### API Architecture
| API Layer | Protocol | Purpose |
|-----------|----------|---------|
| **Platform API** | REST (JSON) | Client-facing trading: orders, positions, account data |
| **WebSocket API** | STOMP over WebSocket | Real-time price ticks, execution events |
| **Broker API v2** | REST + gRPC | Admin/back-office: account provisioning, risk monitoring |
| **FIX API** | FIX 4.4 (TCP) | Institutional liquidity & HFT connections |

#### Authentication Flow
```
POST /mtr-backend/login
Content-Type: application/json

{
  "email": "trader@example.com",
  "password": "your_password",
  "brokerId": 1234          ← Specific to each prop firm (sandbox = 0)
}

Response:
{
  "tradingApiToken": "...",   ← Used in header: Auth-trading-api: <token>
  "token": "...",             ← Session cookie: co-auth=<token>
  "systemUUID": "...",        ← Inserted into all endpoint URLs
  "tradingAccountToken": "..."← Sub-account specific token
}
```

> ⚠️ **Tokens expire every 15 minutes.** Your bot MUST implement a background keep-alive loop calling `POST /refresh-token`.

#### Key Trading Endpoints
All endpoints prefixed with `/mtr-api/{SYSTEM_UUID}/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/position/open` | POST | Open market position: `{"symbol":"EURUSD","cmd":"BUY","volume":0.1,"slPrice":0,"tpPrice":0}` |
| `/position/close` | POST | Close position by `positionId` |
| `/position/close-partially` | POST | Partial close with reduced volume |
| `/position/edit` | POST | Modify SL/TP on open position |
| `/open-positions` | GET | All active positions (ticket, symbol, side, volume, PnL) |
| `/closed-positions` | POST | Historical closed positions by date range |
| `/pending-order/create` | POST | Place limit/stop orders |
| `/pending-order/edit` | POST | Modify pending order |
| `/pending-order/cancel` | POST | Cancel pending order |
| `/active-orders` | GET | All working pending orders |
| `/balance` | GET | Balance, equity, margin, free margin, margin level |
| `/symbols` | GET | Tradeable instruments + specs (contract size, digits, lot sizes) |
| `/market-watch` | GET | Current bid/ask prices |
| `/candles` | GET | Historical OHLCV (M1, M5, M15, H1, D1) |

#### WebSocket (STOMP) Channels
```python
# Subscribe for real-time quotes
SUBSCRIBE /topic/market-watch

# Subscribe for account events (fills, balance changes)
SUBSCRIBE /topic/account/{accountId}

# Send orders via WebSocket (lower latency than REST)
SEND /app/position/open
SEND /app/pending-order/create
```

#### Python Integration (No Official SDK)
```python
import requests
import json

class MatchTraderClient:
    def __init__(self, email, password, broker_id, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self._login(email, password, broker_id)
    
    def _login(self, email, password, broker_id):
        resp = self.session.post(f"{self.base_url}/mtr-backend/login", json={
            "email": email,
            "password": password,
            "brokerId": broker_id
        })
        data = resp.json()
        self.system_uuid = data["systemUUID"]
        self.session.headers["Auth-trading-api"] = data["tradingApiToken"]
        self.session.cookies.set("co-auth", data["token"])
    
    def get_balance(self):
        return self.session.get(
            f"{self.base_url}/mtr-api/{self.system_uuid}/balance"
        ).json()
    
    def open_position(self, symbol, cmd, volume, sl=0, tp=0):
        return self.session.post(
            f"{self.base_url}/mtr-api/{self.system_uuid}/position/open",
            json={"symbol": symbol, "cmd": cmd, "volume": volume, 
                  "slPrice": sl, "tpPrice": tp}
        ).json()
    
    def close_position(self, position_id):
        return self.session.post(
            f"{self.base_url}/mtr-api/{self.system_uuid}/position/close",
            json={"positionId": position_id}
        ).json()
    
    def get_open_positions(self):
        return self.session.get(
            f"{self.base_url}/mtr-api/{self.system_uuid}/open-positions"
        ).json()
    
    def refresh_token(self):
        """Call every 10-12 minutes to keep session alive"""
        return self.session.post(
            f"{self.base_url}/refresh-token"
        ).json()
```

#### Rate Limits & Restrictions
- **500 requests/minute** per account/IP (exceeding → `429 Too Many Requests`)
- **15-minute token TTL** — must refresh continuously
- **403 Forbidden** — if prop firm has disabled API access at admin level
- **Prop firm TOS restrictions:** HFT tick scalping (<30s holds), latency arbitrage, and news-spike abuse are typically banned

#### Official Documentation & Resources
| Resource | URL |
|----------|-----|
| Platform API Docs (Theneo) | https://app.theneo.io/match-trade/platform-api |
| Broker API v2 Docs (Theneo) | https://app.theneo.io/match-trade/broker-api-v2 |
| Sandbox Base URL | `https://mtr-demo-prod.match-trader.com` (`brokerId = 0`) |
| AI Integration Skill (GitHub) | https://github.com/match-trade/Broker-API-skill |
| QuantPipe Framework (GitHub) | https://github.com/Gitchegumi/QuantPipe |
| Official Website | https://match-trader.com |

#### ⚠️ Critical Warning for Prop Firms
> Even if a prop firm offers MatchTrader and allows "EAs" or "Bots", they often mean desktop copy traders or local automation. **Many prop firms explicitly disable the Platform API for retail challenge accounts.** Always confirm with the prop firm's support team if direct API trading is enabled before relying on MatchTrader API.

---

### 2.2 cTrader Open API

> **Used by:** FTMO, FundedNext, Funding Pips, The5ers, E8 Markets, Alpha Capital Group, Fintokei

#### Overview
Developed by Spotware, cTrader is the **most developer-friendly** platform for algorithmic trading. It uses Protocol Buffers over TCP/WebSocket, has a proper OAuth 2.0 flow, and provides an official Python SDK.

#### Authentication (OAuth 2.0)
```
Step 1: Register an application at https://openapi.ctrader.com
        → Get clientId + clientSecret

Step 2: Application Auth
        Send ProtoOAApplicationAuthReq { clientId, clientSecret }

Step 3: Account Auth  
        Send ProtoOAAccountAuthReq { ctidTraderAccountId, accessToken }
```

#### Key Protobuf Messages
| Message | Purpose |
|---------|---------|
| `ProtoOANewOrderReq` | Place Market/Limit/Stop orders with SL/TP |
| `ProtoOAClosePositionReq` | Close position by ID |
| `ProtoOACancelOrderReq` | Cancel pending order |
| `ProtoOAAmendOrderReq` | Modify existing order |
| `ProtoOAReconcileReq` | Full snapshot of all positions + pending orders |
| `ProtoOAGetAccountListByAccessTokenReq` | List all connected accounts |
| `ProtoOATraderReq` | Account balance/equity details |
| `ProtoOASubscribeSpotsReq` | Subscribe to live price ticks |
| `ProtoOAGetTrendbarsReq` | Historical OHLC bars |
| `ProtoOAGetTickDataReq` | Tick-by-tick historical data |
| `ProtoOAExecutionEvent` | Real-time execution notifications |

#### Python SDK
```bash
pip install ctrader-open-api
```
```python
from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import *
from ctrader_open_api.messages.OpenApiMessages_pb2 import *

# Connect
client = Client(EndPoints.PROTOBUF_LIVE_HOST, EndPoints.PROTOBUF_PORT, TcpProtocol)

# Auth
auth_req = ProtoOAApplicationAuthReq()
auth_req.clientId = "your_client_id"
auth_req.clientSecret = "your_client_secret"
client.send(auth_req)

# Place order
order = ProtoOANewOrderReq()
order.ctidTraderAccountId = 12345678
order.symbolId = 1  # EURUSD
order.orderType = ProtoOAOrderType.MARKET
order.tradeSide = ProtoOATradeSide.BUY
order.volume = 100000  # 1 lot (in units)
client.send(order)
```

#### Technical Specs
| Spec | Value |
|------|-------|
| Protocol | Protobuf over TCP (port 5035) or WebSocket |
| Rate Limit | 50 messages/sec burst, 250 req/min sustained |
| Auth | OAuth 2.0 (universal across all cTrader brokers) |
| Docs | https://help.ctrader.com/open-api/ |
| Python SDK | `pip install ctrader-open-api` |
| Native Python cBots | ✅ Supported in cTrader Automate |

---

### 2.3 TradeLocker API

> **Used by:** E8 Markets, Funding Pips, Alpha Capital Group, AquaFunded, Blue Guardian, Goat Funded Trader

#### Overview
Cloud-based platform with native TradingView charting. Has the **simplest, most Pythonic API** of all prop firm platforms. Official `pip` package available.

#### Authentication (JWT)
```python
import requests

resp = requests.post("https://live.tradelocker.com/auth/jwt/token", json={
    "email": "your@email.com",
    "password": "your_password",
    "server": "server_name_from_firm"
})
tokens = resp.json()
access_token = tokens["accessToken"]
refresh_token = tokens["refreshToken"]

headers = {
    "Authorization": f"Bearer {access_token}",
    "accNum": str(account_id)
}
```

#### Key REST Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/trade/accounts` | GET | List all trading accounts |
| `/trade/accounts/{accId}/state` | GET | Account balance/equity/margin |
| `/trade/instruments` | GET | Available instruments |
| `/trade/accounts/{accId}/orders` | POST | Place order (Market/Limit/Stop) |
| `/trade/accounts/{accId}/orders` | GET | Get all orders |
| `/trade/accounts/{accId}/orders/{id}` | DELETE | Cancel order |
| `/trade/accounts/{accId}/positions` | GET | Get open positions |
| `/trade/accounts/{accId}/positions/{id}` | DELETE | Close position |

#### Python SDK
```bash
pip install tradelocker
```
```python
from tradelocker import TLAPI

tl = TLAPI(
    environment="https://live.tradelocker.com",
    username="your@email.com",
    password="your_password",
    server="PropFirmServerName"
)

# Get instruments
instruments = tl.get_all_instruments()

# Place order
order_id = tl.create_order(
    instrument_id=12345,
    quantity=0.1,
    side="buy",
    type_="market"
)

# Get positions
positions = tl.get_all_positions()
```

#### Technical Specs
| Spec | Value |
|------|-------|
| Protocol | REST (JSON) + Socket.IO WebSocket |
| Auth | JWT Bearer Token |
| Docs | https://public-api.tradelocker.com/ |
| Python SDK | `pip install tradelocker` |
| Rate Limit | ~60-120 req/min per IP |

---

### 2.4 DXtrade API

> **Used by:** FTMO (web), FundedNext (some evaluations), The5ers (certain programs), Funding Pips

#### Overview
White-label platform by Devexperts. API documentation is **restricted to licensee partners** — retail traders typically reverse-engineer the web client endpoints.

#### Authentication
```python
resp = requests.post(f"https://{firm_domain}/dxsca-web/login", json={
    "username": "your_username",
    "password": "your_password",
    "domain": "firm_domain"
})
session_token = resp.json()["sessionToken"]
```

#### Key Endpoints (via `/dxsca-web/`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/login` | POST | Session authentication |
| `/accounts` | GET | List trading accounts |
| `/accounts/{acc}/metrics` | GET | Balance, equity, P&L |
| `/accounts/{acc}/positions` | GET | Open positions |
| `/accounts/{acc}/positions/close` | POST | Close position |
| `/accounts/{acc}/orders` | POST | Place order |
| `/accounts/{acc}/orders/{id}` | DELETE | Cancel order |

#### Python Libraries (Community)
- `scotthooker/dxtrade-python-sdk` (GitHub)
- `danielgroen/dxtrade-api` (Node.js)

#### ⚠️ Access Warning
> DXtrade does NOT provide direct developer portal keys for retail traders. Access relies on reverse-engineering web-session credentials. Base URLs and paths differ across prop firm deployments.

---

### 2.5 Tradovate API (Futures)

> **Used by:** Topstep, Apex Trader Funding (via Tradovate/Rithmic)

#### Authentication (OAuth 2.0)
```python
resp = requests.post("https://live.tradovate.com/v1/auth/accesstokenrequest", json={
    "name": "your_username",
    "password": "your_password",
    "appId": "your_app_id",
    "appVersion": "1.0",
    "cid": "your_cid",
    "deviceId": "your_device"
})
```

#### Key Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/account/list` | GET | Account list |
| `/v1/cashBalance/get` | GET | Cash balance |
| `/v1/position/list` | GET | Open positions |
| `/v1/order/placeorder` | POST | Place order |

#### Docs: https://api.tradovate.com/v1/

---

### 2.6 MetaTrader 5 (MT5)

> **Used by:** Your current bot (Exness), FTMO, FundedNext, The5ers, E8 Markets, Funding Pips

#### Your Current Setup
- Python library: `MetaTrader5` (`pip install MetaTrader5`)
- Direct local connection to MT5 terminal
- **Limitation:** Must run from user session (not Windows Service — Session 0 isolation)
- **Strength:** Most battle-tested integration, your entire Sweep Structure bot is built on it

#### Key Functions
```python
import MetaTrader5 as mt5

mt5.initialize()
mt5.login(account, password=pwd, server=srv)

# Market data
rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)

# Trading
request = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": "XAUUSDm",
    "volume": 0.1,
    "type": mt5.ORDER_TYPE_BUY,
    "price": mt5.symbol_info_tick("XAUUSDm").ask,
    "sl": sl_price,
    "tp": tp_price,
    "magic": 123456,
    "comment": "SweepBot",
}
result = mt5.order_send(request)
```

---

## 3. Platform Comparison Matrix

| Feature | MT5 | MatchTrader | cTrader | TradeLocker | DXtrade |
|---------|-----|-------------|---------|-------------|---------|
| **Official Python SDK** | ✅ `MetaTrader5` | ❌ None | ✅ `ctrader-open-api` | ✅ `tradelocker` | ❌ Community only |
| **Auth Method** | Local terminal | Token (15-min TTL) | OAuth 2.0 | JWT Bearer | Session token |
| **Protocol** | Local DLL/pipe | REST + STOMP WS | Protobuf TCP/WS | REST + Socket.IO | REST + WS |
| **Rate Limit** | N/A (local) | 500 req/min | 50 msg/sec | 60-120 req/min | Varies |
| **Retail API Access** | ✅ Always | ⚠️ Firm dependent | ✅ Always | ✅ Always | ⚠️ Restricted |
| **Historical Data** | ✅ Excellent | ✅ Candles | ✅ Tick-level | ⚠️ Bar-level | ⚠️ Limited |
| **Level 2 / DOM** | ❌ No | ❌ No | ✅ Yes | ❌ No | ❌ No |
| **Best For** | Your current bot | FundedNext US | FTMO, The5ers | E8, quick setup | FTMO web alt |
| **Difficulty** | ⭐ Easy | ⭐⭐⭐ Medium | ⭐⭐ Medium | ⭐ Easy | ⭐⭐⭐⭐ Hard |

---

## 4. Prop Firm → Platform Mapping

| Prop Firm | Platforms Available | Best for Bot | US Traders? | API Feasibility |
|-----------|-------------------|--------------|-------------|-----------------|
| **FTMO** | MT4, MT5, cTrader, DXtrade, TradingView | **cTrader** (OpenAPI) | ❌ No US | ✅ High |
| **FundedNext** | cTrader, Match-Trader, MT4, MT5 | **cTrader** or **MT5** | Match-Trader only | ✅ High |
| **The5ers** | MT5, cTrader, TradingView, BlackArrow | **cTrader** or **MT5** | TradingView only | ✅ High |
| **Funding Pips** | cTrader, Match-Trader, TradeLocker, MT5 | **cTrader** or **MT5** | Match-Trader/TL | ✅ High |
| **E8 Markets** | TradeLocker, Match-Trader, cTrader, MT5, Tradovate | **TradeLocker** or **MT5** | TL/Match-Trader | ✅ High |
| **Lux Trading Firm** | "The Lux Trader" (TradingView), MT5 | **MT5** | ❌ Limited | ⚠️ Medium |
| **Topstep** | TopstepX, Tradovate, NinjaTrader, TradingView | **Tradovate API** | ✅ US Futures | ✅ High |
| **Apex Trader Funding** | Tradovate, Rithmic | **Tradovate API** | ✅ US Futures | ✅ High |
| **MyForexFunds** | *DEFUNCT* — Shut down by CFTC Aug 2023 | — | — | ❌ |
| **True Forex Funds** | *DEFUNCT* — Closed May 2024 | — | — | ❌ |

### 🏆 Recommended Prop Firms to Start With
1. **FTMO** — Gold standard, highest payouts, best reputation. Use cTrader.
2. **FundedNext** — Good scaling plan, use cTrader or MT5.
3. **Funding Pips** — Most platform options, good for testing MatchTrader.
4. **The5ers** — Instant funding option, use MT5/cTrader.
5. **E8 Markets** — Easy TradeLocker integration.

---

## 5. Multi-Account Architecture — Hub & Spoke Model

### Architecture Diagram
```
                    ┌───────────────────────────────┐
                    │     MASTER SIGNAL HUB         │
                    │     (Central VPS / Cloud)      │
                    │                               │
                    │  ┌─────────────────────────┐  │
                    │  │   Signal Generator       │  │
                    │  │   - Sweep Structure      │  │
                    │  │   - News Filter          │  │
                    │  │   - Session Filter       │  │
                    │  │   - HTF Alignment        │  │
                    │  └──────────┬──────────────┘  │
                    │             │                  │
                    │    Signal Bus (Internal)       │
                    │             │                  │
                    │  ┌──────────┴──────────────┐  │
                    │  │   Risk Orchestrator      │  │
                    │  │   - Per-account DD check │  │
                    │  │   - Lot size scaling     │  │
                    │  │   - Correlation guard    │  │
                    │  │   - Jitter engine        │  │
                    │  └──────────┬──────────────┘  │
                    └─────────────┼─────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
    ┌─────────▼─────────┐ ┌──────▼──────────┐ ┌──────▼──────────┐
    │   Worker: FTMO     │ │ Worker: FundedNxt│ │ Worker: E8 Mkts │
    │   Platform: cTrader│ │ Platform: MT5    │ │ Platform: TL    │
    │   Account: $100K   │ │ Account: $200K   │ │ Account: $50K   │
    │   Max DD: 10%      │ │ Max DD: 10%      │ │ Max DD: 8%      │
    │   Daily DD: 5%     │ │ Daily DD: 5%     │ │ Daily DD: 5%    │
    │                    │ │                   │ │                 │
    │   Executor Module  │ │ Executor Module   │ │ Executor Module │
    │   (cTrader OpenAPI)│ │ (MT5 Python lib)  │ │ (TradeLocker SDK│
    └────────────────────┘ └───────────────────┘ └─────────────────┘
```

### How It Works

1. **Signal Generator** runs ONE instance — produces BUY/SELL signals for XAUUSDm, USTECm, US30m
2. **Risk Orchestrator** receives the signal and for EACH active account:
   - Checks if that account has hit daily DD limit → skip if yes
   - Checks if overall DD is too close to max → reduce lot size
   - Calculates lot size based on account balance + account-specific risk %
   - Applies jitter (±2-5 seconds delay, ±0.5-2 pip SL/TP offset)
3. **Workers** execute the trade via the platform-specific API
4. **Workers** independently monitor positions, trail stops, and report results back to Hub

### Key Design Principles
- **Signal is generated ONCE, executed MANY times** with per-account customization
- **Each worker is independent** — if one account's API fails, others continue
- **Jitter prevents identical timestamps** across accounts (anti-correlation)
- **Per-account DD tracking** prevents catastrophic losses on any single account

---

## 6. Dynamic Risk Scaling Per Account Size

### Risk Scaling Matrix

| Account Size | Risk Per Trade | Max Lot (Gold) | Max Lot (USTEC) | Max Lot (US30) | Max Concurrent |
|-------------|---------------|----------------|-----------------|----------------|----------------|
| $10K | 0.5% ($50) | 0.03 | 0.5 | 0.3 | 1 |
| $25K | 0.5% ($125) | 0.08 | 1.2 | 0.8 | 2 |
| $50K | 0.5% ($250) | 0.15 | 2.5 | 1.5 | 2 |
| $100K | 0.5% ($500) | 0.30 | 5.0 | 3.0 | 3 |
| $200K | 0.3% ($600) | 0.35 | 6.0 | 3.5 | 3 |
| $400K | 0.2% ($800) | 0.45 | 8.0 | 5.0 | 3 |

### Adaptive Drawdown Protection
```python
def calculate_risk_percent(account):
    """Reduce risk as drawdown approaches limit"""
    current_dd = account.peak_balance - account.current_balance
    max_dd_allowed = account.max_drawdown_limit  # e.g., 10%
    dd_used_pct = (current_dd / account.peak_balance) / max_dd_allowed
    
    if dd_used_pct < 0.3:      # < 30% of DD used → full risk
        return account.base_risk  # 0.5%
    elif dd_used_pct < 0.5:    # 30-50% of DD used → reduce
        return account.base_risk * 0.7  # 0.35%
    elif dd_used_pct < 0.7:    # 50-70% of DD used → minimal
        return account.base_risk * 0.4  # 0.2%
    else:                       # > 70% of DD used → STOP TRADING
        return 0  # No trades allowed
```

### Daily Drawdown Circuit Breaker
```python
def check_daily_dd(account):
    """Stop trading if daily DD limit approached"""
    daily_starting_balance = account.get_balance_at_day_start()
    current_balance = account.get_current_balance()
    daily_loss = daily_starting_balance - current_balance
    daily_dd_limit = daily_starting_balance * account.daily_dd_pct  # e.g., 5%
    
    if daily_loss >= daily_dd_limit * 0.7:  # 70% of daily DD hit
        return False  # STOP — don't risk breaching
    return True  # OK to trade
```

---

## 7. Prop Firm Rule Enforcement Engine

### Rule Matrix by Firm

| Rule | FTMO | FundedNext | The5ers | Funding Pips | E8 Markets |
|------|------|-----------|---------|-------------|------------|
| **Max Overall DD** | 10% (from initial) | 10% (from initial) | 6% (trailing) | 10% (from initial) | 8% (static) |
| **Max Daily DD** | 5% | 5% | 4% | 5% | 5% |
| **Min Trading Days** | 4 | 5 | None | 3 | None |
| **Max Trading Days** | 30 (challenge) | 30 (challenge) | None | None | None |
| **News Trading** | ❌ Banned (±2 min) | ✅ Allowed | ✅ Allowed | ✅ Allowed | ❌ Banned (±2 min) |
| **Weekend Holding** | ✅ Allowed | ✅ Allowed | ⚠️ Conditional | ✅ Allowed | ✅ Allowed |
| **Max Leverage** | 1:100 | 1:100 | 1:30 (Forex) | 1:100 | 1:100 |
| **Profit Target (Ph1)** | 10% | 10% | 8% | 8% | 8% |
| **Profit Target (Ph2)** | 5% | 5% | 5% | 5% | 5% |
| **Profit Split** | 80% (up to 90%) | 80% (up to 95%) | 80% (up to 100%) | 80% (up to 90%) | 80% |

### Enforcement Code Structure
```python
class PropFirmRuleEngine:
    def __init__(self, firm_config):
        self.max_overall_dd_pct = firm_config['max_overall_dd']  # 0.10
        self.max_daily_dd_pct = firm_config['max_daily_dd']      # 0.05
        self.news_banned = firm_config['news_banned']            # True/False
        self.news_buffer_minutes = firm_config.get('news_buffer', 2)
        self.weekend_close_required = firm_config['weekend_close']
        self.min_hold_time_seconds = firm_config.get('min_hold', 0)
        self.trailing_dd = firm_config.get('trailing_dd', False)
    
    def can_trade(self, account_state, news_filter):
        """Master gate — returns (allowed, reason)"""
        # 1. Overall DD check
        if self.trailing_dd:
            dd = account_state.high_water_mark - account_state.equity
        else:
            dd = account_state.initial_balance - account_state.equity
        
        if dd >= account_state.initial_balance * self.max_overall_dd_pct * 0.75:
            return False, "Overall DD approaching limit"
        
        # 2. Daily DD check
        daily_loss = account_state.day_start_balance - account_state.equity
        if daily_loss >= account_state.day_start_balance * self.max_daily_dd_pct * 0.70:
            return False, "Daily DD approaching limit"
        
        # 3. News check (if firm bans news trading)
        if self.news_banned and news_filter.is_news_blackout(
            buffer_minutes=self.news_buffer_minutes
        ):
            return False, f"News blackout (±{self.news_buffer_minutes}min)"
        
        # 4. Weekend check (Friday close)
        if self.weekend_close_required:
            now = datetime.utcnow()
            if now.weekday() == 4 and now.hour >= 20:  # Friday 8 PM UTC
                return False, "Weekend close required"
        
        return True, "OK"
```

---

## 8. Anti-Detection & Anti-Correlation Strategies

> **Why this matters:** Prop firms actively monitor for "copy trading" or "group trading" patterns. If multiple accounts place identical trades at identical times with identical SL/TP, they will be flagged and potentially banned.

### Strategy 1: Entry Time Jitter
```python
import random

def apply_entry_jitter():
    """Random delay 2-8 seconds before executing trade"""
    jitter = random.uniform(2.0, 8.0)
    time.sleep(jitter)
```

### Strategy 2: SL/TP Dispersal
```python
def apply_sl_tp_jitter(sl_price, tp_price, atr, symbol_digits):
    """Add ±0.5-2 pips random offset to SL/TP"""
    sl_offset = random.uniform(-0.0002, 0.0002) * atr
    tp_offset = random.uniform(-0.0002, 0.0002) * atr
    
    return (
        round(sl_price + sl_offset, symbol_digits),
        round(tp_price + tp_offset, symbol_digits)
    )
```

### Strategy 3: Lot Size Variation
```python
def apply_lot_jitter(base_lot, min_lot=0.01):
    """Vary lot size by ±5-10%"""
    variation = random.uniform(0.90, 1.10)
    adjusted = base_lot * variation
    return max(min_lot, round(adjusted, 2))
```

### Strategy 4: Selective Signal Skip
```python
def should_skip_signal(skip_probability=0.10):
    """Each account has 10% chance of skipping any given signal"""
    return random.random() < skip_probability
```

### Strategy 5: Different Magic Numbers & Comments
```python
def generate_trade_comment(account_id):
    """Each account uses unique magic numbers and comments"""
    magic = hash(f"{account_id}_{datetime.now().date()}") % 900000 + 100000
    comments = ["Swing", "Momentum", "Breakout", "Reversal", "Continuation"]
    return magic, random.choice(comments)
```

### Strategy 6: IP Isolation
- **Each account runs through a different VPS/proxy IP**
- Use residential proxies or separate VPS instances per firm
- Never log into multiple same-firm accounts from the same IP

---

## 9. Technology Stack Recommendations

### Infrastructure
```
┌─────────────────────────────────────────────┐
│               PRODUCTION STACK               │
├─────────────────────────────────────────────┤
│                                             │
│  🖥️  VPS Provider:                          │
│     - Azure (current) or AWS/Hetzner        │
│     - Windows Server 2022 (for MT5)         │
│     - 4 vCPU, 8 GB RAM recommended          │
│     - Location: London (for NY/London       │
│       session overlap proximity)            │
│                                             │
│  🐍  Python Stack:                          │
│     - Python 3.13+                          │
│     - MetaTrader5 (pip)                     │
│     - ctrader-open-api (pip)                │
│     - tradelocker (pip)                     │
│     - requests + stomp.py (MatchTrader)     │
│     - FastAPI + Uvicorn (dashboard)         │
│     - pandas, numpy (data processing)       │
│                                             │
│  📊  Monitoring:                            │
│     - FastAPI Dashboard (current)           │
│     - Telegram Bot (trade alerts)           │
│     - Daily P&L reports via email           │
│                                             │
│  🔐  Security:                              │
│     - Encrypted credential store (env vars) │
│     - Per-account API key rotation          │
│     - Separate IPs per prop firm            │
│                                             │
│  💾  Database:                              │
│     - SQLite (current, fine for <20 accts)  │
│     - PostgreSQL (when scaling >20 accts)   │
│                                             │
└─────────────────────────────────────────────┘
```

### Recommended Python Packages
```
# Core Trading
MetaTrader5==5.0.45
ctrader-open-api==0.11.0
tradelocker==0.1.8
requests==2.31.0
stomp.py==8.1.0        # For MatchTrader STOMP WebSocket

# Web Dashboard
fastapi==0.111.0
uvicorn==0.30.0
jinja2==3.1.4

# Data & Analysis
pandas==2.2.2
numpy==1.26.4
ta==0.11.0             # Technical Analysis library

# Monitoring
python-telegram-bot==21.3
schedule==1.2.2

# Utilities
python-dotenv==1.0.1
cryptography==42.0.0   # For encrypted credential storage
```

---

## 10. Account Configuration Schema

### JSON Configuration Per Account
```json
{
  "accounts": [
    {
      "id": "ftmo_100k_01",
      "firm": "FTMO",
      "platform": "ctrader",
      "account_size": 100000,
      "currency": "USD",
      "phase": "funded",
      "enabled": true,
      
      "credentials": {
        "client_id": "env:FTMO_01_CLIENT_ID",
        "client_secret": "env:FTMO_01_CLIENT_SECRET",
        "access_token": "env:FTMO_01_ACCESS_TOKEN",
        "account_id": "env:FTMO_01_ACCOUNT_ID"
      },
      
      "rules": {
        "max_overall_dd_pct": 0.10,
        "max_daily_dd_pct": 0.05,
        "trailing_dd": false,
        "news_banned": true,
        "news_buffer_minutes": 2,
        "weekend_close_required": false,
        "min_hold_time_seconds": 120,
        "max_leverage": 100
      },
      
      "risk": {
        "base_risk_per_trade_pct": 0.005,
        "max_concurrent_trades": 3,
        "max_daily_trades": 6,
        "max_daily_loss_trades": 3
      },
      
      "symbols": {
        "XAUUSD": {"enabled": true, "lot_multiplier": 1.0},
        "USTEC": {"enabled": true, "lot_multiplier": 1.0},
        "US30": {"enabled": true, "lot_multiplier": 1.0}
      },
      
      "anti_detection": {
        "entry_jitter_seconds": [2, 8],
        "sl_tp_jitter_pct": 0.002,
        "lot_jitter_pct": 0.10,
        "signal_skip_probability": 0.10,
        "unique_magic_seed": "ftmo_01_2026"
      },
      
      "proxy": {
        "ip": "203.0.113.50",
        "port": 8080,
        "type": "socks5"
      }
    },
    {
      "id": "fundednext_200k_01",
      "firm": "FundedNext",
      "platform": "mt5",
      "account_size": 200000,
      "currency": "USD",
      "phase": "challenge_phase1",
      "enabled": true,
      
      "credentials": {
        "login": "env:FN_01_LOGIN",
        "password": "env:FN_01_PASSWORD",
        "server": "env:FN_01_SERVER"
      },
      
      "rules": {
        "max_overall_dd_pct": 0.10,
        "max_daily_dd_pct": 0.05,
        "trailing_dd": false,
        "news_banned": false,
        "weekend_close_required": false,
        "min_hold_time_seconds": 0,
        "profit_target_pct": 0.10
      },
      
      "risk": {
        "base_risk_per_trade_pct": 0.005,
        "max_concurrent_trades": 3,
        "max_daily_trades": 8,
        "max_daily_loss_trades": 3
      },
      
      "symbols": {
        "XAUUSDm": {"enabled": true, "lot_multiplier": 1.0},
        "USTECm": {"enabled": true, "lot_multiplier": 1.0},
        "US30m": {"enabled": true, "lot_multiplier": 1.0}
      },
      
      "anti_detection": {
        "entry_jitter_seconds": [3, 10],
        "sl_tp_jitter_pct": 0.003,
        "lot_jitter_pct": 0.08,
        "signal_skip_probability": 0.05,
        "unique_magic_seed": "fn_01_2026"
      }
    }
  ],
  
  "global_settings": {
    "signal_symbols": ["XAUUSD", "USTEC", "US30"],
    "strategy_mode": "sweep_structure",
    "signal_timeframe": "M5",
    "htf_timeframe": "H1",
    "news_filter_enabled": true,
    "news_source": "forexfactory",
    "max_total_concurrent_trades": 15,
    "dashboard_port": 8000,
    "telegram_alerts": true,
    "telegram_bot_token": "env:TELEGRAM_BOT_TOKEN",
    "telegram_chat_id": "env:TELEGRAM_CHAT_ID"
  }
}
```

---

## 11. Step-by-Step Roadmap — From Zero to Prop Firm Empire

### Phase 0: Foundation (Where You Are Now) ✅
- [x] Built Sweep Structure strategy on MT5
- [x] Backtested on Gold, US indices (XAUUSDm +27%, multi-asset +77.81%)
- [x] Implemented news filter (ForexFactory)
- [x] Implemented broker SL detection & cooldown
- [x] VPS deployed on Azure
- [x] Web dashboard (FastAPI)
- **Capital invested:** ~$20-30/month (Azure VPS)

### Phase 1: Validate on Live (Weeks 1-4) 🔄
**Goal:** Prove the strategy works on live markets with real spreads/slippage

- [ ] Run bot on Exness trial account for 30 trading days
- [ ] Track every trade — compare to backtest expectations
- [ ] Target: **15-25% monthly return** with **<5% max drawdown**
- [ ] Fix any live-specific issues (slippage, requotes, spread spikes)
- [ ] Document win rate, profit factor, average trade duration

**Key Metrics to Hit:**
| Metric | Target |
|--------|--------|
| Win Rate | >45% |
| Profit Factor | >1.8 |
| Max Drawdown | <5% |
| Monthly Return | 15-25% |
| Avg Trade Duration | >5 minutes |
| Total Trades | 60-120/month |

### Phase 2: First Prop Firm Challenge (Weeks 5-8)
**Goal:** Pass your first prop firm evaluation

- [ ] **Choose:** FTMO $10K account (cheapest, best reputation)
  - Challenge fee: ~$155
  - Phase 1 target: 10% ($1,000 profit)
  - Phase 2 target: 5% ($500 profit)
  - Max Daily DD: 5% ($500)
  - Max Overall DD: 10% ($1,000)
- [ ] Use **cTrader** platform (best API, or MT5 if more comfortable)
- [ ] Configure prop firm rule engine for FTMO
- [ ] Run bot with conservative risk (0.3% per trade)
- [ ] Target: Pass Phase 1 in 2-3 weeks, Phase 2 in 1-2 weeks

**Cost:** $155 (refunded on funded account)

### Phase 3: Scale to Multiple Accounts (Weeks 9-16)
**Goal:** Run 3-5 funded accounts simultaneously

- [ ] After getting funded on FTMO, take profit for 2 months
- [ ] Simultaneously start challenges on:
  - FundedNext $25K (cTrader or MT5)
  - Funding Pips $25K (TradeLocker — test new platform)
  - E8 Markets $25K (TradeLocker)
- [ ] Build the **Hub & Spoke** architecture
- [ ] Implement anti-detection jitter across accounts
- [ ] Test multi-platform executor (MT5 + cTrader + TradeLocker)

**Total challenges cost:** ~$500-800
**Potential managed capital:** $100K-$125K

### Phase 4: Serious Scaling (Months 5-8)
**Goal:** 10+ funded accounts, $500K+ managed capital

- [ ] Scale FTMO to $200K account
- [ ] Add FundedNext $100K + $200K accounts
- [ ] Add The5ers $40K instant funding
- [ ] Implement PostgreSQL for trade tracking
- [ ] Add Telegram bot for real-time alerts
- [ ] Upgrade VPS (8 vCPU, 16 GB RAM)
- [ ] Set up separate IPs per firm (proxy rotation)

**Monthly revenue potential at 5% average return:**
| Account | Size | 5% Return | 80% Payout |
|---------|------|-----------|------------|
| FTMO #1 | $200K | $10,000 | $8,000 |
| FundedNext #1 | $200K | $10,000 | $8,000 |
| FundedNext #2 | $100K | $5,000 | $4,000 |
| The5ers | $40K | $2,000 | $1,600 |
| Funding Pips | $50K | $2,500 | $2,000 |
| E8 Markets | $50K | $2,500 | $2,000 |
| **TOTAL** | **$640K** | **$32,000** | **$25,600/month** |

### Phase 5: Empire Mode (Months 9-12+)
**Goal:** $1M+ managed capital, fully automated

- [ ] 15-20 funded accounts across 5+ firms
- [ ] Dedicated VPS per firm cluster
- [ ] Automated challenge purchasing (when scaling works)
- [ ] Monthly payout optimization (stagger payout requests)
- [ ] Legal: Register as a business entity for tax purposes
- [ ] Consider hiring a DevOps person for infrastructure

**Monthly revenue potential:** $40,000-$80,000/month

---

## 12. Cost Analysis & ROI Projections

### Startup Costs
| Item | Cost | Frequency |
|------|------|-----------|
| Azure VPS (current) | $30/month | Monthly |
| First FTMO challenge | $155 | One-time |
| Additional challenges (5×) | $800 | One-time |
| Residential proxies (5 IPs) | $50/month | Monthly |
| Upgraded VPS (8 vCPU) | $80/month | Monthly |
| **Total Initial Investment** | **~$1,115** | — |
| **Monthly Operating Cost** | **~$160** | Monthly |

### Revenue Timeline
| Month | Managed Capital | Est. Monthly Revenue | Cumulative |
|-------|----------------|---------------------|------------|
| 1 | $0 (validating) | $0 | -$30 |
| 2 | $10K (FTMO challenge) | $0 (challenge phase) | -$215 |
| 3 | $10K (funded) | $400 (80% of $500) | +$185 |
| 4 | $35K (+ 2 more) | $1,400 | +$1,585 |
| 5 | $85K (scaling) | $3,400 | +$4,985 |
| 6 | $200K (scaling) | $8,000 | +$12,985 |
| 8 | $400K | $16,000 | +$44,985 |
| 10 | $640K | $25,600 | +$96,185 |
| 12 | $1M+ | $40,000+ | +$176,185+ |

> **Break-even point:** Month 3-4 (after first funded payout)

---

## 13. Common Pitfalls & How to Avoid Them

### ❌ Pitfall 1: Trading During High-Impact News
**What happens:** Bot takes 9 trades in 5 minutes during FOMC → wipes gains
**Solution:** ✅ Already implemented — ForexFactory news filter with ±30 min blackout

### ❌ Pitfall 2: Identical Trades Across Accounts
**What happens:** Prop firm detects "copy trading" → accounts banned
**Solution:** ✅ Anti-detection jitter (time, SL/TP, lot size, signal skip)

### ❌ Pitfall 3: Breaching Daily Drawdown
**What happens:** One bad day wipes the account → lose challenge fee
**Solution:** ✅ Daily DD circuit breaker at 70% of limit

### ❌ Pitfall 4: Running MT5 as Windows Service
**What happens:** Session 0 isolation → MT5 can't connect → bot trades blind
**Solution:** ✅ Always run from user session (not Windows Service)

### ❌ Pitfall 5: Over-leveraging on Large Accounts
**What happens:** Same lot size on $200K as $10K → one loss = catastrophic
**Solution:** ✅ Adaptive risk scaling — always risk 0.3-0.5% per trade

### ❌ Pitfall 6: Not Refreshing API Tokens
**What happens:** MatchTrader token expires after 15 min → orders fail silently
**Solution:** ✅ Background token refresh loop every 10 minutes

### ❌ Pitfall 7: Prop Firm Goes Bankrupt
**What happens:** MyForexFunds, True Forex Funds — both collapsed
**Solution:** ✅ Never have >30% of capital with one firm. Diversify across 3-5 firms.

### ❌ Pitfall 8: Weekend Holding When Not Allowed
**What happens:** Gap risk + firm violation → account breach
**Solution:** ✅ Friday auto-close at 20:00 UTC for firms that require it

---

## Appendix A: Quick Reference — API Access by Platform

```
✅ = Official SDK + Open Access
⚠️ = Available but restricted/unofficial
❌ = No API access

MT5          → ✅ pip install MetaTrader5     (your current setup)
cTrader      → ✅ pip install ctrader-open-api (OAuth 2.0, best for FTMO)
TradeLocker  → ✅ pip install tradelocker      (JWT, easiest API)
MatchTrader  → ⚠️ REST + STOMP (no official SDK, firm may block)
DXtrade      → ⚠️ Community SDK only (scotthooker/dxtrade-python-sdk)
Tradovate    → ✅ REST + WebSocket (for futures prop firms)
```

## Appendix B: Useful Links

| Resource | URL |
|----------|-----|
| FTMO | https://ftmo.com |
| FundedNext | https://fundednext.com |
| Funding Pips | https://fundingpips.com |
| The5ers | https://the5ers.com |
| E8 Markets | https://e8markets.com |
| MatchTrader Platform API Docs | https://app.theneo.io/match-trade/platform-api |
| MatchTrader Broker API v2 Docs | https://app.theneo.io/match-trade/broker-api-v2 |
| MatchTrader Sandbox | https://mtr-demo-prod.match-trader.com |
| MatchTrader GitHub (AI Skill) | https://github.com/match-trade/Broker-API-skill |
| cTrader Open API Docs | https://help.ctrader.com/open-api/ |
| cTrader Python SDK | https://github.com/spotware/OpenApiPy |
| TradeLocker API Docs | https://public-api.tradelocker.com/ |
| TradeLocker Python SDK | https://github.com/TradeLocker/tradelocker-python |
| DXtrade Developer Portal | https://dx.trade/apis |
| Tradovate API | https://api.tradovate.com/v1/ |
| ForexFactory Calendar (JSON) | https://nfs.faireconomy.media/ff_calendar_thisweek.json |
| QuantPipe (MatchTrader Framework) | https://github.com/Gitchegumi/QuantPipe |

---

> **Last Updated:** September 16, 2026  
> **Next Steps:** Complete Phase 1 (live validation on Exness), then begin Phase 2 (first FTMO challenge)
