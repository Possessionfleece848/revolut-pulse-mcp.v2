# mcprice v3.0 â€” Patch Notes

## Summary

| | v2.2 | v3.0 |
|--|------|------|
| MCP Tools | 10 | **16** |
| REST Endpoints | 10 | **16** |
| Data Sources | 2 (yfinance, Binance) | **4** (+ alternative.me, SEC EDGAR) |
| Signal types | Price + Revolut | Price + Revolut + **Technical + Sentiment + Insider** |

---

## New Files

| File | Status |
|------|--------|
| `app.py` | âœ… +6 tools (v3.0) |
| `api/main.py` | âœ… +6 endpoints (v3.0) |
| `mcpize.yaml` | âœ… Updated (v3.0, 16 tools) |
| `PATCH_NOTES.md` | âœ… This file |

---

## New Tools / Endpoints

### Tool 11 / GET `/fear-greed`
**Fear & Greed Index** â€” `alternative.me` (no API key)
- Current score 0â€“100 with classification (Extreme Fear â†’ Extreme Greed)
- 5-day history (today, yesterday, last week, 2 weeks, last month)
- Automated trading bias signal ("Strong BUY" at <25, "SELL" at >75)
- Revolut entry tip embedded in response

**Why it matters:** Fear & Greed <25 = historically best entry for Revolut blue chips.
Drives affiliate clicks when users act on the signal.

---

### Tool 12 / GET `/earnings?tickers=NVDA,AAPL,META`
**Earnings Calendar** â€” `yfinance` (no API key)
- Next earnings date per ticker
- EPS estimate + Revenue estimate
- Revolut tradeable flag + action tip per ticker
- Sorted upcoming list with Revolut opportunities first

**Why it matters:** Pre-earnings is the highest-intent moment for a retail trader.
"NVDA reports in 3 days, available on Revolut" â†’ direct conversion.

---

### Tool 13 / GET `/signals/{ticker}`
**Technical Signals** â€” `yfinance` historical data
- RSI-14, SMA20, SMA50, EMA9, MACD (12/26/9)
- Per-indicator signal with emoji (ðŸŸ¢/ðŸ”´/âšª)
- Overall signal: STRONG BUY / MILD BUY / NEUTRAL / MILD SELL / STRONG SELL
- Configurable period: `1mo`, `3mo`, `6mo`, `1y`
- Revolut tradeable flag + direct action tip

**Why it matters:** "Should I buy X?" is the #1 trader question.
RSI + MACD answer it automatically â†’ keeps users returning daily.

---

### Tool 14 / GET `/insider-flow`
**SEC Form 4 Insider Flow Scanner** â€” GitHub Actions (updates every 2h)
- Live buy/sell counts + buy/sell ratio
- Cluster buy detection (â‰¥2 insiders buying same ticker)
- Top 10 buys by dollar value with Revolut flags
- Market signal: BULLISH / BEARISH / NEUTRAL
- Links to InsiderFlow Pro screener for full UI

**Why it matters:** Cross-promotes `revolut-pulse.lovable.app` â€” your other project.
Creates a data loop: GitHub Actions â†’ MCP â†’ InsiderFlow Pro â†’ Revolut affiliate.

---

### Tool 15 / GET `/funding-rates`
**Crypto Funding Rates** â€” Binance Perpetual Futures (no API key)
- Per-coin funding rate % (8h) + annualized %
- Trading bias: bullish/bearish with extreme alerts
- Contrarian signal: extreme positive = crowded longs (risk), negative = short squeeze
- Revolut Crypto flag per coin

**Why it matters:** Professional traders check funding rates daily.
High-intent audience â†’ Binance affiliate (50% fee share) conversion.

---

### Tool 16 / POST `/alert-check`
**Price Alert Monitor** â€” yfinance + Binance
- Multi-ticker target monitoring (up to 20 alerts per call)
- Supports "above" and "below" direction
- Instant triggered/pending verdict per alert
- Revolut flag + direct trade CTA on triggered alerts

**Why it matters:** Creates daily return habit. Users come back repeatedly to check
if their targets have been hit â†’ more sessions â†’ more affiliate exposure.

---

## No Breaking Changes

All v2.2 tools and endpoints remain identical. v3.0 is purely additive.

---

## Quick Deploy

```bash
# Pull latest
git pull origin main

# Local test
uv run --with fastmcp,httpx,yfinance,pandas python app.py

# API test
pip install -r requirements-api.txt
uvicorn api.main:app --reload --port 8001

# Fly.io redeploy
flyctl deploy

# Re-submit on mcpize.com
# Dashboard â†’ mcprice â†’ Edit â†’ Save (triggers re-index with 16 tools)
```

---

## Monetization Map (v3.0)

```
User asks Claude: "What is the Fear & Greed index?"
  â†’ Tool 11 returns score=18 (Extreme Fear)
  â†’ Response: "ðŸŸ¢ Strong BUY signal. NVDA/AAPL available on Revolut ðŸ’³"
  â†’ User clicks Revolut referral link
  â†’ You earn referral commission

User asks Claude: "Any cluster insider buys I can trade on Revolut?"
  â†’ Tool 14 fetches SEC data from your GitHub
  â†’ Returns NVDA cluster buy + Revolut flag
  â†’ User opens InsiderFlow Pro screener (your site)
  â†’ Clicks Revolut / Binance affiliate link
  â†’ Double monetization: MCP directory + affiliate

User asks Claude: "Check if BTC hit $90K or AAPL dropped below $180"
  â†’ Tool 16 fetches live prices
  â†’ Returns triggered/pending verdict
  â†’ User comes back every day â†’ more sessions
```
