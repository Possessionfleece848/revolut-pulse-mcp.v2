#!/usr/bin/env python3

"""
╔══════════════════════════════════════════════════════════════════╗
║  mcprice v2.2                                                    ║
║  Real-Time Price MCP Server for Claude / Cursor                  ║
║                                                                  ║
║  Stocks  → yfinance  (cloud-reliable, no raw HTTP blocks)        ║
║  Crypto  → Binance Public API (no key needed)                    ║
║  Revolut → marks assets tradeable on Revolut                     ║
║                                                                  ║
║  v2.2 upgrades over v2.1:                                        ║
║   ✅ HealthMiddleware  — GET/HEAD /health → 200, HEAD /mcp → 200 ║
║   ✅ Lazy semaphore    — no event-loop crash on Python 3.12      ║
║   ✅ Stampede-safe cache — _in_flight deduplication              ║
║   ✅ yfinance          — more reliable than raw Yahoo HTTP       ║
║   ✅ 429 handling      — respects Retry-After header             ║
║   ✅ Config fallback   — silent fallback to built-in defaults    ║
║   ✅ portfolio_pnl     — real-time P&L for a list of holdings    ║
║   ✅ market_overview   — indices + commodities + crypto dashboard ║
║   ✅ List[str] typing  — MCP schema compatible                   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import asyncio
import functools
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import List, Optional

import httpx
import yfinance as yf
from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("mcprice")

# ─────────────────────────────────────────────────────────────────────────────
# SERVER
# ─────────────────────────────────────────────────────────────────────────────

mcp = FastMCP("mcprice")

# ─────────────────────────────────────────────────────────────────────────────
# HEALTH MIDDLEWARE — fixes 406 probe errors on Smithery / MCPize / cloud
# ─────────────────────────────────────────────────────────────────────────────

class HealthMiddleware(BaseHTTPMiddleware):
    """
    Intercepts health probes before they reach the MCP ASGI app.
    - GET  /health  → 200 {"status": "ok"}
    - HEAD /health  → 200 (empty body)
    - HEAD /mcp     → 200 immediately (avoids 406 from streamable-http)
    """
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            if request.method in ("GET", "HEAD"):
                body = b'{"status":"ok","service":"mcprice","version":"2.2"}'
                return Response(
                    content=body if request.method == "GET" else b"",
                    status_code=200,
                    media_type="application/json",
                )
        if request.method == "HEAD" and request.url.path == "/mcp":
            return Response(status_code=200)
        return await call_next(request)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — load from JSON files, silent fallback to built-in defaults
# ─────────────────────────────────────────────────────────────────────────────

def _load_config() -> tuple[dict, set]:
    config_dir = Path(__file__).parent / "config"
    try:
        stocks_text = (config_dir / "revolut_stocks.json").read_text()
        crypto_text = (config_dir / "revolut_crypto.json").read_text()
        stocks = json.loads(stocks_text).get("stocks", {})
        crypto = set(json.loads(crypto_text).get("crypto", []))
        logger.info("Config loaded: %d stocks, %d crypto", len(stocks), len(crypto))
        return stocks, crypto
    except Exception as exc:
        logger.warning("Config load failed (%s) — using built-in defaults", exc)
        return _default_stocks(), _default_crypto()


def _default_stocks() -> dict:
    return {
        "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Alphabet A", "GOOG": "Alphabet C",
        "META": "Meta", "AMZN": "Amazon", "NVDA": "NVIDIA", "TSLA": "Tesla", "NFLX": "Netflix",
        "ADBE": "Adobe", "CRM": "Salesforce", "ORCL": "Oracle", "IBM": "IBM", "INTC": "Intel",
        "AMD": "AMD", "QCOM": "Qualcomm", "TXN": "Texas Instruments", "AVGO": "Broadcom",
        "MU": "Micron", "AMAT": "Applied Materials", "NOW": "ServiceNow", "INTU": "Intuit",
        "SNOW": "Snowflake", "UBER": "Uber", "SHOP": "Shopify", "SQ": "Block",
        "PYPL": "PayPal", "PLTR": "Palantir", "COIN": "Coinbase", "MSTR": "MicroStrategy",
        "JPM": "JPMorgan", "BAC": "Bank of America", "WFC": "Wells Fargo", "GS": "Goldman",
        "MS": "Morgan Stanley", "V": "Visa", "MA": "Mastercard", "AXP": "Amex",
        "BRKB": "Berkshire B", "BLK": "BlackRock", "SCHW": "Schwab",
        "JNJ": "J&J", "PFE": "Pfizer", "MRNA": "Moderna", "ABBV": "AbbVie",
        "LLY": "Eli Lilly", "MRK": "Merck", "AMGN": "Amgen", "GILD": "Gilead",
        "UNH": "UnitedHealth", "CVS": "CVS",
        "XOM": "ExxonMobil", "CVX": "Chevron", "COP": "ConocoPhillips", "OXY": "Occidental",
        "LMT": "Lockheed Martin", "RTX": "RTX/Raytheon", "BA": "Boeing", "GD": "General Dynamics",
        "NOC": "Northrop Grumman", "LHX": "L3Harris", "HII": "Huntington Ingalls",
        "KO": "Coca-Cola", "PEP": "PepsiCo", "MCD": "McDonald's", "SBUX": "Starbucks",
        "NKE": "Nike", "DIS": "Disney", "WMT": "Walmart", "COST": "Costco", "HD": "Home Depot",
        "T": "AT&T", "VZ": "Verizon", "CMCSA": "Comcast",
        "TSM": "TSMC ADR", "ASML": "ASML ADR", "LRCX": "Lam Research",
        "SPY": "S&P 500 ETF", "QQQ": "Nasdaq-100 ETF", "IWM": "Russell 2000 ETF",
        "DIA": "Dow Jones ETF", "GLD": "Gold ETF", "SLV": "Silver ETF",
        "TLT": "20yr Treasury ETF", "USO": "Oil ETF",
        "XLK": "Tech SPDR", "XLE": "Energy SPDR", "XLF": "Finance SPDR",
        "XLV": "Health SPDR", "XLI": "Industrial SPDR", "ITA": "Aerospace & Defense ETF",
        "ARKK": "ARK Innovation ETF", "VOO": "Vanguard S&P 500", "SOXX": "Semiconductor ETF",
        "DDOG": "Datadog", "NET": "Cloudflare", "CRWD": "CrowdStrike", "PANW": "Palo Alto",
        "ZS": "Zscaler", "FTNT": "Fortinet", "SNAP": "Snap", "PINS": "Pinterest",
        "ZM": "Zoom", "RBLX": "Roblox", "SPOT": "Spotify", "LYFT": "Lyft",
        "HUBS": "HubSpot", "TEAM": "Atlassian", "TWLO": "Twilio", "DOCU": "DocuSign",
        "OKTA": "Okta", "PATH": "UiPath", "U": "Unity", "AI": "C3.ai",
    }


def _default_crypto() -> set:
    return {
        "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "DOT", "AVAX", "MATIC", "LINK",
        "UNI", "ATOM", "LTC", "BCH", "XLM", "ALGO", "VET", "THETA", "FIL", "AAVE",
        "COMP", "SNX", "MKR", "SUSHI", "YFI", "BAT", "ZRX", "ENJ", "MANA", "SAND",
        "AXS", "CHZ", "GALA", "IMX", "APE", "NEAR", "FTM", "HBAR", "ICP", "ETC",
        "TRX", "EOS", "NEO", "DASH", "ZEC", "XMR", "QTUM", "ONT", "ZIL", "ICX",
        "BNB", "OP", "ARB", "SUI", "SEI", "TIA", "PYTH", "JUP",
    }


REVOLUT_STOCKS, REVOLUT_CRYPTO = _load_config()

# Independent crypto detection set for price_snapshot
# (works even if a coin is not in the Revolut list)
KNOWN_CRYPTO: set = {
    "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "DOT", "AVAX",
    "MATIC", "LINK", "UNI", "ATOM", "LTC", "BCH", "BNB", "OP", "ARB",
    "HBAR", "TIA", "SUI", "SEI", "NEAR", "FTM", "APE", "SAND", "MANA",
    "AXS", "CHZ", "GALA", "IMX", "AAVE", "COMP", "SNX", "MKR",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; mcprice/2.2; "
        "+https://github.com/gepappas98/mcprice)"
    )
}

# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

_VALID_TICKER = re.compile(r"^[A-Z0-9\.\-\^]{1,12}$")


def validate_ticker(ticker: str) -> str:
    t = ticker.upper().strip()
    if not _VALID_TICKER.match(t):
        raise ValueError(
            f"Invalid ticker '{ticker}'. "
            "Use 1-12 uppercase letters/digits (e.g. AAPL, BTC, SPY)."
        )
    return t

# ─────────────────────────────────────────────────────────────────────────────
# TTL CACHE — stampede-safe with _in_flight deduplication
# ─────────────────────────────────────────────────────────────────────────────

_cache: dict     = {}
_in_flight: dict = {}   # key → asyncio.Event, prevents cache stampede


def ttl_cache(ttl: int = 30):
    """
    Async TTL decorator with stampede protection.
    Concurrent requests for the same key wait on the first fetch instead of
    all hammering the upstream API simultaneously.
    ttl=30 for stocks / ttl=10 for crypto
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args):
            key = f"{func.__name__}:{args}"
            now = time.monotonic()

            # Cache HIT
            if key in _cache:
                data, expiry = _cache[key]
                if now < expiry:
                    logger.debug("Cache HIT %s", key)
                    return data

            # Stampede guard — if another coroutine is already fetching this key, wait
            if key in _in_flight:
                logger.debug("Cache WAIT (in-flight) %s", key)
                await _in_flight[key].wait()
                # After wait, return whatever was cached
                if key in _cache:
                    return _cache[key][0]

            # We are the first — set the in-flight event
            event = asyncio.Event()
            _in_flight[key] = event
            try:
                logger.debug("Cache MISS %s", key)
                result = await func(*args)
                _cache[key] = (result, now + ttl)
                return result
            finally:
                event.set()
                _in_flight.pop(key, None)

        return wrapper
    return decorator

# ─────────────────────────────────────────────────────────────────────────────
# RATE LIMITER — lazy init (avoids Python 3.12 event-loop crash)
# ─────────────────────────────────────────────────────────────────────────────

_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(5)
    return _semaphore


async def limited_call(fn, *args):
    async with _get_semaphore():
        return await fn(*args)

# ─────────────────────────────────────────────────────────────────────────────
# RETRY WITH EXPONENTIAL BACKOFF + 429 Retry-After support
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_with_retry(fn, *args, retries: int = 3, base_delay: float = 0.5):
    last_exc = Exception("unknown")
    for attempt in range(retries):
        try:
            return await fn(*args)
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code == 429:
                retry_after = float(exc.response.headers.get("Retry-After", 5))
                wait = min(retry_after, 60.0)
                logger.warning("Rate limited (429) on %s — waiting %.1fs", getattr(fn, "__name__", str(fn)), wait)
                await asyncio.sleep(wait)
                continue
            if attempt < retries - 1:
                wait = base_delay * (2 ** attempt)
                logger.warning(
                    "Retry %d/%d for %s — %s (wait %.1fs)",
                    attempt + 1, retries, getattr(fn, "__name__", str(fn)), exc, wait,
                )
                await asyncio.sleep(wait)
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                wait = base_delay * (2 ** attempt)
                logger.warning(
                    "Retry %d/%d for %s — %s (wait %.1fs)",
                    attempt + 1, retries, getattr(fn, "__name__", str(fn)), exc, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc

# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER LAYER — yfinance (more reliable than raw Yahoo HTTP on cloud IPs)
# ─────────────────────────────────────────────────────────────────────────────

@ttl_cache(ttl=30)
async def _yfinance_quote(ticker: str) -> dict:
    """yfinance fast_info — cached 30 seconds. Runs in thread pool to avoid blocking."""
    logger.info("yfinance fetch: %s", ticker)

    def _sync_fetch():
        t = yf.Ticker(ticker)
        info = t.fast_info
        price    = float(info.last_price or 0)
        prev     = float(info.previous_close or price)
        change   = price - prev
        chg_pct  = (change / prev * 100) if prev else 0.0
        return {
            "ticker":     ticker,
            "name":       getattr(info, "display_name", None) or ticker,
            "price":      round(price, 4),
            "change":     round(change, 4),
            "change_pct": round(chg_pct, 2),
            "volume":     int(info.three_month_average_volume or 0),
            "market_cap": getattr(info, "market_cap", None),
            "currency":   getattr(info, "currency", "USD"),
            "source":     "yfinance",
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_fetch)

# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER LAYER — Binance
# ─────────────────────────────────────────────────────────────────────────────

@ttl_cache(ttl=10)
async def _binance_ticker(symbol: str) -> dict:
    """Binance 24h ticker — cached 10 seconds."""
    sym = symbol.upper()
    if not sym.endswith("USDT"):
        sym += "USDT"
    logger.info("Binance fetch: %s", sym)
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            "https://api.binance.com/api/v3/ticker/24hr",
            params={"symbol": sym},
        )
        r.raise_for_status()
        d    = r.json()
        base = sym.replace("USDT", "")
        return {
            "ticker":          base,
            "pair":            sym,
            "price":           round(float(d["lastPrice"]), 6),
            "change":          round(float(d["priceChange"]), 6),
            "change_pct":      round(float(d["priceChangePercent"]), 2),
            "high_24h":        round(float(d["highPrice"]), 6),
            "low_24h":         round(float(d["lowPrice"]), 6),
            "volume_usd_24h":  round(float(d["quoteVolume"]), 0),
            "currency":        "USDT",
            "source":          "Binance",
            "revolut_crypto":  base in REVOLUT_CRYPTO,
        }

# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK yfinance → Binance
# ─────────────────────────────────────────────────────────────────────────────

async def _get_stock_price(ticker: str) -> dict:
    try:
        return await fetch_with_retry(limited_call, _yfinance_quote, ticker)
    except Exception as exc:
        logger.warning("yfinance failed for %s (%s) — trying Binance fallback", ticker, exc)
        try:
            return await fetch_with_retry(limited_call, _binance_ticker, ticker)
        except Exception as exc2:
            logger.error("Both providers failed for %s: %s", ticker, exc2)
            return {"ticker": ticker, "error": str(exc2), "source": "all providers failed"}

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _arrow(change_pct: float) -> str:
    if change_pct > 2:  return "🚀"
    if change_pct > 0:  return "📈"
    if change_pct < -2: return "🔻"
    if change_pct < 0:  return "📉"
    return "➡️"


def _enrich_stock(q: dict) -> dict:
    t  = q.get("ticker", "")
    q["revolut_available"] = t in REVOLUT_STOCKS
    if t in REVOLUT_STOCKS:
        q["revolut_name"] = REVOLUT_STOCKS[t]
    cp   = q.get("change_pct", 0)
    sign = "+" if cp >= 0 else ""
    q["emoji"]   = _arrow(cp)
    q["summary"] = (
        f"{q['emoji']} {t}: ${q.get('price', '?')} ({sign}{cp}%)"
        + (" 💳 Revolut" if q["revolut_available"] else "")
    )
    return q

# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1 — get_price
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_price(ticker: str) -> dict:
    """
    Current price for one stock or ETF.
    Source: yfinance (30s cache). Falls back to Binance on failure.

    Args:
        ticker: Symbol e.g. "NVDA", "SPY", "LMT"
    """
    try:
        ticker = validate_ticker(ticker)
    except ValueError as e:
        return {"error": str(e)}
    quote = await _get_stock_price(ticker)
    return _enrich_stock(quote) if quote else {"ticker": ticker, "error": "No data"}

# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2 — get_prices_bulk
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_prices_bulk(tickers: List[str]) -> dict:
    """
    Prices for multiple stocks/ETFs at once (max 20).

    Args:
        tickers: e.g. ["NVDA", "LMT", "GLD", "SPY"]
    """
    validated, errors = [], []
    for t in tickers[:20]:
        try:
            validated.append(validate_ticker(t))
        except ValueError as e:
            errors.append({"ticker": t, "error": str(e)})

    quotes  = await asyncio.gather(*[_get_stock_price(t) for t in validated])
    results = [_enrich_stock(q) for q in quotes if q]
    valid   = [r for r in results if "error" not in r]
    return {
        "count":   len(results),
        "results": results,
        "errors":  errors,
        "gainers": sorted(valid, key=lambda x: x.get("change_pct", 0), reverse=True)[:3],
        "losers":  sorted(valid, key=lambda x: x.get("change_pct", 0))[:3],
    }

# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3 — get_crypto_price
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_crypto_price(symbol: str) -> dict:
    """
    Crypto price from Binance Public API (10s cache).

    Args:
        symbol: e.g. "BTC", "ETH", "SOL" (no USDT suffix needed)
    """
    try:
        symbol = validate_ticker(symbol.replace("USDT", "").replace("/", ""))
    except ValueError as e:
        return {"error": str(e)}
    try:
        result = await fetch_with_retry(limited_call, _binance_ticker, symbol)
    except Exception as exc:
        logger.error("Binance failed for %s: %s", symbol, exc)
        return {"ticker": symbol, "error": str(exc)}
    if result:
        cp   = result.get("change_pct", 0)
        sign = "+" if cp >= 0 else ""
        result["emoji"]   = _arrow(cp)
        result["summary"] = (
            f"{result['emoji']} {symbol}: ${result.get('price', '?')} "
            f"({sign}{cp}% 24h)"
            + (" 💳 Revolut Crypto" if result.get("revolut_crypto") else "")
        )
    return result or {"symbol": symbol, "error": "Not found on Binance"}

# ─────────────────────────────────────────────────────────────────────────────
# TOOL 4 — price_snapshot
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def price_snapshot(tickers: Optional[List[str]] = None) -> dict:
    """
    Rich snapshot for a mixed watchlist (stocks + crypto).
    Uses default watchlist if no tickers provided.
    """
    DEFAULT_STOCKS = ["NVDA", "AAPL", "MSFT", "TSLA", "LMT", "RTX", "GLD", "SPY", "META", "AMZN"]
    DEFAULT_CRYPTO = ["BTC", "ETH", "SOL", "XRP", "DOGE"]

    if tickers:
        upper       = [t.upper().strip() for t in tickers[:25]]
        # KNOWN_CRYPTO is independent of Revolut config — correct Binance routing
        crypto_list = [t for t in upper if t in KNOWN_CRYPTO]
        stock_list  = [t for t in upper if t not in KNOWN_CRYPTO]
    else:
        stock_list, crypto_list = DEFAULT_STOCKS, DEFAULT_CRYPTO

    stock_results, crypto_results = await asyncio.gather(
        asyncio.gather(*[_get_stock_price(t) for t in stock_list], return_exceptions=True),
        asyncio.gather(*[fetch_with_retry(limited_call, _binance_ticker, t) for t in crypto_list], return_exceptions=True),
    )

    stocks_out = [_enrich_stock(q) for q in stock_results if isinstance(q, dict) and "error" not in q]
    crypto_out = []
    for q in crypto_results:
        if isinstance(q, dict) and "error" not in q:
            q["emoji"] = _arrow(q.get("change_pct", 0))
            crypto_out.append(q)

    all_valid  = stocks_out + crypto_out
    avg_chg    = sum(x.get("change_pct", 0) for x in all_valid) / len(all_valid) if all_valid else 0
    top_gainer = max(all_valid, key=lambda x: x.get("change_pct", 0), default=None)
    top_loser  = min(all_valid, key=lambda x: x.get("change_pct", 0), default=None)

    return {
        "stocks": stocks_out,
        "crypto": crypto_out,
        "summary": {
            "total_assets":   len(all_valid),
            "avg_change_pct": round(avg_chg, 2),
            "market_mood":    "🟢 Risk-On" if avg_chg > 0 else "🔴 Risk-Off",
            "top_gainer":     {"ticker": top_gainer["ticker"], "change_pct": top_gainer.get("change_pct")} if top_gainer else None,
            "top_loser":      {"ticker": top_loser["ticker"],  "change_pct": top_loser.get("change_pct")}  if top_loser  else None,
        },
    }

# ─────────────────────────────────────────────────────────────────────────────
# TOOL 5 — revolut_price_check
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def revolut_price_check(ticker: str) -> dict:
    """
    Combined: is this stock/ETF on Revolut? + current price.

    Args:
        ticker: Stock or ETF symbol e.g. "LMT", "GLD", "ITA"
    """
    try:
        ticker = validate_ticker(ticker)
    except ValueError as e:
        return {"error": str(e)}

    quote  = await _get_stock_price(ticker)
    on_rev = ticker in REVOLUT_STOCKS

    if not quote or "error" in quote:
        return {
            "ticker":           ticker,
            "revolut_available": on_rev,
            "price":            None,
            "quick_verdict": (
                f"{'✅' if on_rev else '❌'} {ticker} "
                f"{'on Revolut' if on_rev else 'NOT on Revolut'} — price unavailable"
            ),
        }

    cp   = quote.get("change_pct", 0)
    sign = "+" if cp >= 0 else ""
    name = REVOLUT_STOCKS.get(ticker, quote.get("name", ticker))

    return {
        "ticker":            ticker,
        "name":              name,
        "revolut_available": on_rev,
        "price":             quote["price"],
        "change_pct":        cp,
        "volume":            quote.get("volume"),
        "currency":          quote.get("currency", "USD"),
        "emoji":             _arrow(cp),
        "quick_verdict": (
            f"{'✅ 💳' if on_rev else '❌'} {ticker} ({name}): "
            f"${quote['price']} ({sign}{cp}%) "
            + ("— available on Revolut 💳" if on_rev else "— NOT on Revolut")
        ),
    }

# ─────────────────────────────────────────────────────────────────────────────
# TOOL 6 — crypto_top_movers
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def crypto_top_movers(
    limit: int = 10,
    min_volume_usd: float = 10_000_000,
) -> dict:
    """
    Top crypto gainers & losers over 24h from Binance (no API key).

    Args:
        limit: Results per category (default 10)
        min_volume_usd: Minimum 24h USD volume filter (default $10M)
    """
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("https://api.binance.com/api/v3/ticker/24hr")
            r.raise_for_status()
            all_tickers = r.json()
    except Exception as exc:
        logger.error("Binance top-movers failed: %s", exc)
        return {"error": "Binance connection failed", "details": str(exc)}

    filtered = []
    for t in all_tickers:
        sym = t.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        vol = float(t.get("quoteVolume", 0))
        if vol < min_volume_usd:
            continue
        base = sym[:-4]
        chg  = float(t.get("priceChangePercent", 0))
        filtered.append({
            "ticker":          base,
            "price":           round(float(t["lastPrice"]), 6),
            "change_pct":      round(chg, 2),
            "volume_usd_24h":  round(vol, 0),
            "revolut":         base in REVOLUT_CRYPTO,
            "emoji":           _arrow(chg),
        })

    return {
        "gainers": sorted(filtered, key=lambda x: x["change_pct"], reverse=True)[:limit],
        "losers":  sorted(filtered, key=lambda x: x["change_pct"])[:limit],
        "revolut_movers": [
            x for x in sorted(filtered, key=lambda x: abs(x["change_pct"]), reverse=True)
            if x["revolut"]
        ][:limit],
        "total_pairs_scanned": len(filtered),
    }

# ─────────────────────────────────────────────────────────────────────────────
# TOOL 7 — portfolio_pnl  ★ NEW
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def portfolio_pnl(holdings: List[dict]) -> dict:
    """
    Real-time P&L calculator for a portfolio of stocks and crypto.
    Pass a list of holdings with ticker, quantity, and average buy price.
    Returns current value, P&L per asset, Revolut availability, and portfolio summary.

    Args:
        holdings: List of dicts, e.g.:
            [
              {"ticker": "NVDA", "qty": 10, "avg_price": 800.0},
              {"ticker": "BTC",  "qty": 0.5, "avg_price": 40000.0},
              {"ticker": "LMT",  "qty": 5,   "avg_price": 450.0}
            ]
    """
    if not holdings:
        return {"error": "No holdings provided"}

    results       = []
    total_cost    = 0.0
    total_current = 0.0

    for h in holdings[:30]:
        raw_ticker = h.get("ticker", "")
        qty        = float(h.get("qty", 0))
        avg_price  = float(h.get("avg_price", 0))

        try:
            ticker = validate_ticker(raw_ticker)
        except ValueError as e:
            results.append({"ticker": raw_ticker, "error": str(e)})
            continue

        is_crypto = ticker in KNOWN_CRYPTO

        try:
            if is_crypto:
                q = await fetch_with_retry(limited_call, _binance_ticker, ticker)
            else:
                q = await _get_stock_price(ticker)
        except Exception as exc:
            results.append({"ticker": ticker, "qty": qty, "avg_price": avg_price, "error": str(exc)})
            continue

        if not q or "error" in q:
            results.append({"ticker": ticker, "qty": qty, "avg_price": avg_price, "error": "Price unavailable"})
            continue

        current_price = float(q.get("price", 0))
        cost_basis    = qty * avg_price
        current_value = qty * current_price
        pnl           = current_value - cost_basis
        pnl_pct       = (pnl / cost_basis * 100) if cost_basis else 0.0

        on_revolut = (ticker in REVOLUT_STOCKS) or (ticker in REVOLUT_CRYPTO)

        total_cost    += cost_basis
        total_current += current_value

        results.append({
            "ticker":            ticker,
            "qty":               qty,
            "avg_price":         avg_price,
            "current_price":     current_price,
            "cost_basis":        round(cost_basis, 2),
            "current_value":     round(current_value, 2),
            "pnl":               round(pnl, 2),
            "pnl_pct":           round(pnl_pct, 2),
            "revolut_available": on_revolut,
            "emoji":             _arrow(pnl_pct),
            "summary": (
                f"{_arrow(pnl_pct)} {ticker}: "
                f"${current_price} × {qty} = ${round(current_value, 2)} "
                f"({'+'  if pnl >= 0 else ''}{round(pnl, 2)} / {round(pnl_pct, 2):+.2f}%)"
                + (" 💳" if on_revolut else "")
            ),
        })

    total_pnl     = total_current - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0.0
    valid_results = [r for r in results if "error" not in r]

    return {
        "holdings":        results,
        "portfolio_summary": {
            "total_cost":        round(total_cost, 2),
            "total_current":     round(total_current, 2),
            "total_pnl":         round(total_pnl, 2),
            "total_pnl_pct":     round(total_pnl_pct, 2),
            "portfolio_mood":    "🟢 In profit" if total_pnl >= 0 else "🔴 In loss",
            "best_performer":    max(valid_results, key=lambda x: x.get("pnl_pct", 0), default=None),
            "worst_performer":   min(valid_results, key=lambda x: x.get("pnl_pct", 0), default=None),
            "on_revolut_count":  sum(1 for r in valid_results if r.get("revolut_available")),
        },
    }

# ─────────────────────────────────────────────────────────────────────────────
# TOOL 8 — market_overview  ★ NEW
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def market_overview() -> dict:
    """
    Full market dashboard: major indices, commodities, and top crypto — all at once.
    No arguments needed. Great for a morning market briefing.

    Covers:
    - Indices:     SPY (S&P 500), QQQ (Nasdaq), DIA (Dow), IWM (Russell 2000)
    - Commodities: GLD (Gold), SLV (Silver), USO (Oil), TLT (Bonds)
    - Crypto:      BTC, ETH, SOL, BNB
    """
    INDICES     = ["SPY", "QQQ", "DIA", "IWM"]
    COMMODITIES = ["GLD", "SLV", "USO", "TLT"]
    CRYPTO_LIST = ["BTC", "ETH", "SOL", "BNB"]

    indices_res, commodities_res, crypto_res = await asyncio.gather(
        asyncio.gather(*[_get_stock_price(t) for t in INDICES],     return_exceptions=True),
        asyncio.gather(*[_get_stock_price(t) for t in COMMODITIES], return_exceptions=True),
        asyncio.gather(*[fetch_with_retry(limited_call, _binance_ticker, t) for t in CRYPTO_LIST], return_exceptions=True),
    )

    def _safe_enrich(results):
        out = []
        for q in results:
            if isinstance(q, dict) and "error" not in q:
                out.append(_enrich_stock(q))
        return out

    indices_out    = _safe_enrich(indices_res)
    commodities_out = _safe_enrich(commodities_res)

    crypto_out = []
    for q in crypto_res:
        if isinstance(q, dict) and "error" not in q:
            cp   = q.get("change_pct", 0)
            sign = "+" if cp >= 0 else ""
            q["emoji"]             = _arrow(cp)
            q["revolut_available"] = q.get("revolut_crypto", False)
            q["summary"]           = (
                f"{q['emoji']} {q['ticker']}: ${q.get('price', '?')} ({sign}{cp}%)"
                + (" 💳" if q["revolut_available"] else "")
            )
            crypto_out.append(q)

    all_valid = indices_out + commodities_out + crypto_out
    avg_chg   = sum(x.get("change_pct", 0) for x in all_valid) / len(all_valid) if all_valid else 0

    # Risk-on/off signal based on SPY + BTC combined
    spy_chg = next((x.get("change_pct", 0) for x in indices_out if x["ticker"] == "SPY"), 0)
    btc_chg = next((x.get("change_pct", 0) for x in crypto_out  if x["ticker"] == "BTC"), 0)

    if spy_chg > 0 and btc_chg > 0:
        mood = "🟢 Risk-On — Equities & Crypto both up"
    elif spy_chg < 0 and btc_chg < 0:
        mood = "🔴 Risk-Off — Equities & Crypto both down"
    elif spy_chg > 0 and btc_chg < 0:
        mood = "🟡 Mixed — Equities up, Crypto down"
    elif spy_chg < 0 and btc_chg > 0:
        mood = "🟡 Mixed — Crypto up, Equities down"
    else:
        mood = "➡️ Neutral"

    return {
        "indices":    indices_out,
        "commodities": commodities_out,
        "crypto":     crypto_out,
        "overview": {
            "avg_change_pct": round(avg_chg, 2),
            "market_mood":    mood,
            "spy_change":     f"{spy_chg:+.2f}%",
            "btc_change":     f"{btc_chg:+.2f}%",
            "timestamp":      time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    }

# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "http":
        port = int(os.environ.get("PORT", "8080"))
        logger.info("mcprice v2.2 starting on http://0.0.0.0:%d/mcp", port)
        app = mcp.http_app()
        app.add_middleware(HealthMiddleware)

        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        logger.info("mcprice v2.2 starting (stdio mode)")
        mcp.run(transport="stdio")
