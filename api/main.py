#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║              mcprice — FastAPI HTTP Layer  v2.0                  ║
║                                                                  ║
║  Exposes the same logic as the MCP server over plain HTTP.       ║
║  Useful for:                                                     ║
║    • Programmatic SEO pages                                      ║
║    • Browser / JS frontends                                      ║
║    • Webhook integrations                                        ║
║    • Direct REST calls without MCP client                        ║
║                                                                  ║
║  Run:                                                            ║
║    uvicorn api.main:app --reload --port 8001                     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ─── load config ─────────────────────────────────────────────────────────────
_CONFIG_DIR = Path(__file__).parent.parent / "config"

with open(_CONFIG_DIR / "revolut_stocks.json") as f:
    _STOCKS_DATA = json.load(f)
    REVOLUT_STOCKS: dict = _STOCKS_DATA["stocks"]

with open(_CONFIG_DIR / "revolut_crypto.json") as f:
    _CRYPTO_DATA = json.load(f)
    REVOLUT_CRYPTO: set = set(_CRYPTO_DATA["crypto"])

# ─── shared cache (reuse from MCP logic) ─────────────────────────────────────
_cache: dict = {}

def _ttl_get(key: str):
    if key in _cache:
        data, expiry = _cache[key]
        if time.monotonic() < expiry:
            return data
    return None

def _ttl_set(key: str, value, ttl: int):
    _cache[key] = (value, time.monotonic() + ttl)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; mcprice/2.0; +https://github.com/gepappas98/mcprice)"}

# ─── providers ────────────────────────────────────────────────────────────────
async def _yahoo(ticker: str) -> dict:
    cached = _ttl_get(f"y:{ticker}")
    if cached:
        return cached
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
        r = await c.get(url, params={"interval": "1d", "range": "2d"}, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
    meta = data["chart"]["result"][0]["meta"]
    price = meta.get("regularMarketPrice", 0.0)
    prev  = meta.get("chartPreviousClose") or meta.get("previousClose", price)
    chg   = price - prev
    chg_p = (chg / prev * 100) if prev else 0.0
    result = {
        "ticker":     ticker,
        "name":       meta.get("longName") or meta.get("shortName") or ticker,
        "price":      round(price, 4),
        "change":     round(chg, 4),
        "change_pct": round(chg_p, 2),
        "volume":     meta.get("regularMarketVolume", 0),
        "currency":   meta.get("currency", "USD"),
        "source":     "Yahoo Finance",
        "revolut":    ticker in REVOLUT_STOCKS,
    }
    _ttl_set(f"y:{ticker}", result, 30)
    return result

async def _binance(symbol: str) -> dict:
    cached = _ttl_get(f"b:{symbol}")
    if cached:
        return cached
    sym = symbol.upper()
    if not sym.endswith("USDT"):
        sym += "USDT"
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get("https://api.binance.com/api/v3/ticker/24hr", params={"symbol": sym})
        r.raise_for_status()
        d = r.json()
    base = sym.replace("USDT", "")
    result = {
        "ticker":         base,
        "price":          round(float(d["lastPrice"]), 6),
        "change_pct":     round(float(d["priceChangePercent"]), 2),
        "high_24h":       round(float(d["highPrice"]), 6),
        "low_24h":        round(float(d["lowPrice"]), 6),
        "volume_usd_24h": round(float(d["quoteVolume"]), 0),
        "source":         "Binance",
        "revolut":        base in REVOLUT_CRYPTO,
    }
    _ttl_set(f"b:{symbol}", result, 10)
    return result

# ─── app ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="mcprice API",
    description=(
        "Real-time stock & crypto prices. No API key required. "
        "Stocks via Yahoo Finance, crypto via Binance. "
        "Companion MCP server: revolut-pulse-mcp."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ─── routes ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    """Health check — uptime monitoring."""
    return {"status": "ok", "version": "2.0.0"}


@app.get("/price/{ticker}", tags=["Stocks"])
async def get_price(ticker: str):
    """
    Current price for one stock or ETF (Yahoo Finance, 30s cache).
    Automatically marks if available on Revolut.
    """
    ticker = ticker.upper().strip()
    try:
        return await _yahoo(ticker)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Yahoo Finance error: {e}")


@app.get("/prices", tags=["Stocks"])
async def get_prices_bulk(
    tickers: str = Query(..., description="Comma-separated list, e.g. NVDA,AAPL,MSFT")
):
    """
    Prices for multiple stocks/ETFs at once (max 20, comma-separated).
    """
    symbols = [t.strip().upper() for t in tickers.split(",")][:20]
    results = await asyncio.gather(*[_yahoo(s) for s in symbols], return_exceptions=True)
    out = [r for r in results if isinstance(r, dict)]
    return {
        "count": len(out),
        "results": out,
        "gainers": sorted(out, key=lambda x: x.get("change_pct", 0), reverse=True)[:3],
        "losers":  sorted(out, key=lambda x: x.get("change_pct", 0))[:3],
    }


@app.get("/crypto/{symbol}", tags=["Crypto"])
async def get_crypto(symbol: str):
    """
    Crypto price from Binance (10s cache, real-time).
    Automatically marks if available on Revolut.
    """
    symbol = symbol.upper().replace("USDT", "").strip()
    try:
        return await _binance(symbol)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Binance error: {e}")


@app.get("/revolut/stocks", tags=["Revolut"])
async def revolut_stocks_list():
    """Full list of stocks tradeable on Revolut."""
    return {"count": len(REVOLUT_STOCKS), "stocks": REVOLUT_STOCKS}


@app.get("/revolut/crypto", tags=["Revolut"])
async def revolut_crypto_list():
    """Full list of crypto tradeable on Revolut."""
    return {"count": len(REVOLUT_CRYPTO), "crypto": sorted(REVOLUT_CRYPTO)}


@app.get("/revolut/check/{ticker}", tags=["Revolut"])
async def revolut_check(ticker: str):
    """
    Is this stock or crypto available on Revolut? + live price.
    """
    ticker = ticker.upper().strip()
    on_rev = ticker in REVOLUT_STOCKS or ticker in REVOLUT_CRYPTO
    is_crypto = ticker in REVOLUT_CRYPTO or ticker not in REVOLUT_STOCKS

    try:
        if is_crypto:
            data = await _binance(ticker)
        else:
            data = await _yahoo(ticker)
        price = data.get("price")
        chg   = data.get("change_pct", 0)
    except Exception:
        price, chg = None, None

    return {
        "ticker":            ticker,
        "revolut_available": on_rev,
        "asset_type":        "crypto" if is_crypto else "stock",
        "price":             price,
        "change_pct":        chg,
        "verdict": (
            f"✅ {ticker} is available on Revolut"
            if on_rev else
            f"❌ {ticker} is NOT available on Revolut"
        ),
    }


@app.get("/snapshot", tags=["Watchlist"])
async def snapshot(
    tickers: Optional[str] = Query(None, description="Comma-separated. Defaults to top watchlist.")
):
    """
    Rich snapshot for a mixed stock+crypto watchlist.
    """
    if tickers:
        syms = [t.strip().upper() for t in tickers.split(",")][:25]
    else:
        syms = ["NVDA", "AAPL", "MSFT", "TSLA", "LMT", "GLD", "SPY",
                "BTC",  "ETH",  "SOL",  "XRP",  "DOGE"]

    stocks  = [s for s in syms if s not in REVOLUT_CRYPTO]
    cryptos = [s for s in syms if s in REVOLUT_CRYPTO or s in {"BTC","ETH","SOL","XRP","DOGE","BNB","ADA"}]

    s_res, c_res = await asyncio.gather(
        asyncio.gather(*[_yahoo(s)   for s in stocks],  return_exceptions=True),
        asyncio.gather(*[_binance(c) for c in cryptos], return_exceptions=True),
    )

    all_valid = [r for r in list(s_res) + list(c_res) if isinstance(r, dict)]
    if not all_valid:
        return {"error": "No data"}

    avg = sum(r.get("change_pct", 0) for r in all_valid) / len(all_valid)

    return {
        "stocks": [r for r in s_res if isinstance(r, dict)],
        "crypto": [r for r in c_res if isinstance(r, dict)],
        "summary": {
            "total":          len(all_valid),
            "avg_change_pct": round(avg, 2),
            "market_mood":    "🟢 Risk-On" if avg > 0 else "🔴 Risk-Off",
            "top_gainer":     max(all_valid, key=lambda x: x.get("change_pct", 0)).get("ticker"),
            "top_loser":      min(all_valid, key=lambda x: x.get("change_pct", 0)).get("ticker"),
        },
    }
