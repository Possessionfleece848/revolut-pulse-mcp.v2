# mcprice ⚡ v3.0 — Free Stock & Crypto Price MCP Server (No API Key)

> **16 tools. Real-time prices, technical signals, Fear & Greed, SEC insider flow,
> earnings calendar, crypto funding rates, and price alert monitoring — for Claude, Cursor, Cline.**
> Yahoo Finance · Binance · alternative.me · SEC EDGAR · Revolut availability · Zero API keys · Free forever.

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template)
[![Deploy on Fly.io](https://img.shields.io/badge/Fly.io-deploy-purple?logo=fly.io)](https://fly.io)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](https://python.org)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![MCP Server](https://img.shields.io/badge/MCP-server-orange)](https://mcpize.com/mcp/mcprice)
[![16 Tools](https://img.shields.io/badge/tools-16-brightgreen)](#tools)

---

## What is mcprice?

**mcprice** is a free, open-source MCP server that gives Claude, Cursor, and any AI agent
**live prices, technical signals, market sentiment, insider flow, and trading alerts** —
with no API key, no paid tier, and zero setup friction.

Ask Claude things like:

> *"What is the Fear & Greed index and should I buy NVDA on Revolut now?"*
> *"Show me RSI and MACD for AAPL — is it a buy?"*
> *"Are there any cluster insider buys I can trade on Revolut today?"*
> *"When does META report earnings and can I trade it on Revolut?"*
> *"What are BTC funding rates — is it a long squeeze?"*
> *"Alert me if TSLA drops below $200 or BTC hits $100K"*

---

## Why mcprice v3?

| Feature | mcprice v3 | Alpha Vantage MCP | Financial Datasets MCP |
|---------|-----------|------------------|----------------------|
| **API Key** | ❌ None | ✅ Required | ✅ Paid |
| **Stock prices** | ✅ yfinance | ✅ | ✅ |
| **Crypto (real-time)** | ✅ Binance | ❌ | ❌ |
| **Technical signals** | ✅ RSI/MACD/SMA | ❌ | ❌ |
| **Fear & Greed** | ✅ Built-in | ❌ | ❌ |
| **SEC Insider Flow** | ✅ Built-in | ❌ | ❌ |
| **Earnings calendar** | ✅ Built-in | ❌ | ❌ |
| **Funding rates** | ✅ Binance perp | ❌ | ❌ |
| **Price alerts** | ✅ Built-in | ❌ | ❌ |
| **Revolut filter** | ✅ Built-in | ❌ | ❌ |
| **Cost** | 🆓 Free | Freemium | Paid |

---

## Quick Start (2 minutes)

### Option A — MCP Mode (Claude Desktop / Cursor / Cline)

```bash
git clone https://github.com/gepappas98/revolut-pulse-mcp.v2.git
cd revolut-pulse-mcp.v2
uv run --with fastmcp,httpx,yfinance,pandas python app.py
```

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcprice": {
      "command": "uv",
      "args": ["run", "--with", "fastmcp,httpx,yfinance,pandas", "python", "app.py"],
      "cwd": "/path/to/revolut-pulse-mcp.v2"
    }
  }
}
```

### Option B — Remote (already deployed)

```json
{
  "mcpServers": {
    "mcprice": {
      "type": "streamable-http",
      "url": "https://mcprice.fly.dev/mcp"
    }
  }
}
```

### Option C — REST API

```bash
uvicorn api.main:app --reload --port 8001
# Open http://localhost:8001/docs
```

---

## Tools (16 total)

### 📊 Prices

| Tool | Description | Example prompt |
|------|-------------|----------------|
| `get_price` | Single stock/ETF price + Revolut flag | *"What is NVDA price?"* |
| `get_prices_bulk` | Up to 20 tickers at once | *"Give me AAPL, MSFT, TSLA, SPY prices"* |
| `get_crypto_price` | Binance real-time crypto | *"BTC price now"* |
| `price_snapshot` | Mixed watchlist snapshot + mood | *"Show my watchlist: NVDA, BTC, LMT"* |

### 💳 Revolut

| Tool | Description | Example prompt |
|------|-------------|----------------|
| `revolut_price_check` | Price + Revolut availability check | *"Can I buy LMT on Revolut?"* |
| `revolut_watchlist` | Bulk Revolut check for a mixed list | *"Which of these can I trade on Revolut?"* |
| `revolut_sector_scan` | Full sector scan + best Revolut pick | *"Scan the defense sector on Revolut"* |

### 📈 Portfolio

| Tool | Description | Example prompt |
|------|-------------|----------------|
| `portfolio_pnl` | Real-time P&L for your holdings | *"Calculate P&L: 10 NVDA @ $800, 0.5 BTC @ $40K"* |
| `market_overview` | Indices + commodities + crypto dashboard | *"Give me a morning market overview"* |
| `crypto_top_movers` | Binance 24h gainers & losers | *"What are the top crypto movers today?"* |

### 🧠 Signals (NEW in v3.0)

| Tool | Description | Example prompt |
|------|-------------|----------------|
| `fear_greed_index` | Fear & Greed score + trading bias | *"What is the Fear & Greed index?"* |
| `earnings_calendar` | Next earnings date + EPS estimates | *"When does NVDA report earnings?"* |
| `technical_signals` | RSI/SMA/EMA/MACD buy-sell signal | *"Is AAPL a buy right now? Show RSI and MACD"* |
| `insider_flow_scan` | SEC Form 4 cluster buy detection | *"Any insider cluster buys on Revolut?"* |
| `crypto_funding_rates` | Binance perp funding — contrarian signal | *"What are BTC and ETH funding rates?"* |
| `price_alert_check` | Multi-ticker price target monitoring | *"Has TSLA dropped below $200 or BTC hit $100K?"* |

---

## REST API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/price/{ticker}` | Single stock price |
| GET | `/prices?tickers=A,B,C` | Bulk prices |
| GET | `/crypto/{symbol}` | Crypto price |
| GET | `/crypto/movers` | Top Binance movers |
| GET | `/revolut/check/{ticker}` | Revolut availability |
| GET | `/revolut/stocks` | Full Revolut stock list |
| GET | `/revolut/crypto` | Full Revolut crypto list |
| GET | `/snapshot` | Mixed watchlist snapshot |
| GET | `/fear-greed` | Fear & Greed index 🆕 |
| GET | `/earnings?tickers=NVDA,META` | Earnings calendar 🆕 |
| GET | `/signals/{ticker}` | Technical signals 🆕 |
| GET | `/insider-flow` | SEC insider flow 🆕 |
| GET | `/funding-rates` | Crypto funding rates 🆕 |
| POST | `/alert-check` | Price alert monitor 🆕 |
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI |

---

## Deploy

### Fly.io (recommended — free tier)

```bash
flyctl launch --name mcprice --region ams
flyctl deploy
```

### Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template)

### Docker

```bash
docker compose up
```

---

## Architecture

```
Claude / Cursor / Cline
        │
        ▼ MCP (streamable-http or stdio)
  ┌─────────────────────────────────┐
  │          app.py (v3.0)          │
  │  16 MCP tools                   │
  │                                 │
  │  Providers:                     │
  │  ├─ yfinance    (stocks/ETFs)   │
  │  ├─ Binance API (crypto/perp)   │
  │  ├─ alternative.me (sentiment)  │
  │  └─ SEC EDGAR via GitHub Actions│
  └─────────────────────────────────┘
        │
        ▼ Optional REST layer
  ┌─────────────────────────────────┐
  │       api/main.py (v3.0)        │
  │  16 FastAPI endpoints           │
  │  /docs (Swagger UI)             │
  └─────────────────────────────────┘
```

---

## Related Projects

- 🖥️ **InsiderFlow Pro** — Full insider trading screener UI with Revolut filter, cluster buy alerts, and Hunter Score
  → [revolut-pulse.lovable.app/insiderflow-pro-v2.html](https://revolut-pulse.lovable.app/insiderflow-pro-v2.html)
- 📦 **mcpize listing** → [mcpize.com/mcp/mcprice](https://mcpize.com/mcp/mcprice)

---

## License

MIT — free to use, fork, and deploy.

---

*mcprice v3.0 — 16 tools · No API key · Free forever*
