#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║            mcprice — Programmatic SEO Generator  v2.0           ║
║                                                                  ║
║  Generates 1000+ static HTML pages (one per ticker) + sitemap   ║
║  Each page has:                                                  ║
║    • Unique <title> + meta description                           ║
║    • Schema.org FinancialProduct structured data                 ║
║    • Open Graph tags                                             ║
║    • Canonical URLs                                              ║
║    • Auto sitemap.xml                                            ║
║                                                                  ║
║  Usage:                                                          ║
║    python seo/generator.py --base-url https://mcprice.fly.dev   ║
║    python seo/generator.py --base-url http://localhost:8001      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, UTC
from pathlib import Path

import httpx

# ─── paths ────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent.parent
CONFIG_DIR = ROOT / "config"
OUT_DIR    = ROOT / "seo" / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── load config ──────────────────────────────────────────────────────────────
with open(CONFIG_DIR / "revolut_stocks.json") as f:
    REVOLUT_STOCKS: dict = json.load(f)["stocks"]

with open(CONFIG_DIR / "revolut_crypto.json") as f:
    REVOLUT_CRYPTO: set = set(json.load(f)["crypto"])

# ─── keyword templates (SEO gold) ─────────────────────────────────────────────
STOCK_TITLE_TEMPLATES = [
    "{name} ({ticker}) Stock Price Today — Is It on Revolut?",
    "{ticker} Stock Price Live — Revolut Availability Check",
    "Buy {name} on Revolut? {ticker} Price & Availability",
]

CRYPTO_TITLE_TEMPLATES = [
    "{ticker} Price Today — Available on Revolut?",
    "{ticker} Crypto Price Live — Revolut Availability",
    "Buy {ticker} on Revolut? Live Price & Check",
]

REVOLUT_PAGES = [
    ("revolut-stocks-list",     "Full List of Stocks Available on Revolut (2025)"),
    ("revolut-crypto-list",     "All Cryptocurrencies Available on Revolut (2025)"),
    ("revolut-etf-list",        "ETFs Available on Revolut — Complete List"),
    ("is-nvda-on-revolut",      "Is NVIDIA (NVDA) Available on Revolut?"),
    ("is-tsla-on-revolut",      "Is Tesla (TSLA) Available on Revolut?"),
    ("is-btc-on-revolut",       "Is Bitcoin (BTC) Available on Revolut?"),
    ("is-sol-on-revolut",       "Is Solana (SOL) Available on Revolut?"),
    ("revolut-vs-trading212",   "Revolut vs Trading 212: Stock & Crypto Comparison"),
    ("revolut-stock-limits",    "Revolut Stock Trading Limits & Fees Explained"),
]


# ─── HTML page builder ────────────────────────────────────────────────────────

def _arrow(change_pct: float) -> str:
    if change_pct > 2:  return "🚀"
    if change_pct > 0:  return "📈"
    if change_pct < -2: return "🔻"
    if change_pct < 0:  return "📉"
    return "➡️"


def build_ticker_page(
    ticker:     str,
    name:       str,
    price:      float | None,
    change_pct: float | None,
    asset_type: str,           # "stock" | "crypto"
    on_revolut: bool,
    base_url:   str,
) -> str:
    title_tpl   = STOCK_TITLE_TEMPLATES[0] if asset_type == "stock" else CRYPTO_TITLE_TEMPLATES[0]
    page_title  = title_tpl.format(ticker=ticker, name=name)
    slug        = f"price/{ticker.lower()}"
    canonical   = f"{base_url}/{slug}"
    rev_badge   = "✅ Available on Revolut" if on_revolut else "❌ Not on Revolut"
    rev_color   = "#16a34a" if on_revolut else "#dc2626"
    price_str   = f"${price:,.4f}" if price else "Loading…"
    chg_str     = f"{'+' if (change_pct or 0) >= 0 else ''}{change_pct:.2f}%" if change_pct is not None else "—"
    chg_color   = "#16a34a" if (change_pct or 0) >= 0 else "#dc2626"
    now         = datetime.now(UTC).strftime("%Y-%m-%d")

    meta_desc = (
        f"{'📈' if (change_pct or 0) >= 0 else '📉'} {name} ({ticker}) live price: {price_str} "
        f"({chg_str} today). {rev_badge}. Real-time data, no login required."
    )

    schema = {
        "@context":    "https://schema.org",
        "@type":       "FinancialProduct",
        "name":        f"{name} ({ticker})",
        "description": meta_desc,
        "url":         canonical,
        "provider": {
            "@type": "Organization",
            "name":  "mcprice",
            "url":   base_url,
        },
        "offers": {
            "@type":         "Offer",
            "price":         str(price or ""),
            "priceCurrency": "USD",
            "availability":  "https://schema.org/InStock",
            "validFrom":     now,
        },
    }

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page_title}</title>
  <meta name="description" content="{meta_desc}">
  <link rel="canonical" href="{canonical}">

  <!-- Open Graph -->
  <meta property="og:title"       content="{page_title}">
  <meta property="og:description" content="{meta_desc}">
  <meta property="og:url"         content="{canonical}">
  <meta property="og:type"        content="website">
  <meta property="og:site_name"   content="mcprice">

  <!-- Twitter Card -->
  <meta name="twitter:card"        content="summary">
  <meta name="twitter:title"       content="{page_title}">
  <meta name="twitter:description" content="{meta_desc}">

  <!-- Schema.org -->
  <script type="application/ld+json">{json.dumps(schema, indent=2)}</script>

  <style>
    *  {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, sans-serif; background: #f8fafc; color: #1e293b; }}
    .container {{ max-width: 800px; margin: 0 auto; padding: 2rem 1rem; }}
    header {{ background: #1e293b; color: #f8fafc; padding: 1rem 2rem; }}
    header a {{ color: #60a5fa; text-decoration: none; font-size: .9rem; }}
    .card  {{ background: #fff; border-radius: 12px; padding: 2rem; box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-top: 1.5rem; }}
    .ticker  {{ font-size: 2.5rem; font-weight: 800; }}
    .name    {{ color: #64748b; margin-top: .25rem; }}
    .price   {{ font-size: 2rem; font-weight: 700; margin-top: 1rem; }}
    .change  {{ font-size: 1.1rem; font-weight: 600; color: {chg_color}; }}
    .badge   {{ display: inline-block; margin-top: 1rem; padding: .4rem 1rem;
                border-radius: 999px; font-size: .9rem; font-weight: 600;
                background: {rev_color}20; color: {rev_color}; border: 1px solid {rev_color}40; }}
    .meta    {{ margin-top: 1rem; font-size: .85rem; color: #94a3b8; }}
    .api-box {{ background: #1e293b; color: #e2e8f0; border-radius: 8px; padding: 1rem;
                margin-top: 1rem; font-family: monospace; font-size: .85rem; overflow-x: auto; }}
    footer   {{ text-align: center; padding: 2rem; font-size: .8rem; color: #94a3b8; }}
    footer a {{ color: #60a5fa; }}
  </style>
</head>
<body>
<header>
  <a href="{base_url}">← mcprice</a>
  &nbsp;/&nbsp;
  <a href="{base_url}/revolut/check/{ticker}">API</a>
  &nbsp;/&nbsp;
  <a href="{base_url}/docs">Docs</a>
</header>

<div class="container">
  <div class="card">
    <div class="ticker">{ticker}</div>
    <div class="name">{name}</div>
    <div class="price">{price_str}</div>
    <div class="change">{_arrow(change_pct or 0)} {chg_str} <span style="color:#94a3b8;font-weight:400">today</span></div>
    <div class="badge">{rev_badge}</div>
    <div class="meta">
      Last updated: <strong>{now}</strong> &nbsp;·&nbsp;
      Source: <strong>{'Binance' if asset_type == 'crypto' else 'Yahoo Finance'}</strong> &nbsp;·&nbsp;
      Asset type: <strong>{asset_type.capitalize()}</strong>
    </div>
  </div>

  <div class="card">
    <h2 style="font-size:1.1rem;font-weight:700;margin-bottom:.75rem">📡 API Access</h2>
    <p style="font-size:.9rem;color:#64748b;margin-bottom:.75rem">
      Get live {ticker} price in your app — no API key needed:
    </p>
    <div class="api-box">GET {base_url}/{'crypto' if asset_type == 'crypto' else 'price'}/{ticker}</div>
    <div class="api-box" style="margin-top:.5rem">GET {base_url}/revolut/check/{ticker}</div>
  </div>

  <div class="card">
    <h2 style="font-size:1.1rem;font-weight:700;margin-bottom:.75rem">❓ Is {ticker} on Revolut?</h2>
    <p style="color:{rev_color};font-weight:600">{rev_badge}</p>
    {'<p style="margin-top:.75rem;font-size:.9rem;color:#64748b">You can trade ' + name + ' directly in the Revolut app under the Stocks/Crypto tab.</p>' if on_revolut else '<p style="margin-top:.75rem;font-size:.9rem;color:#64748b">' + name + ' is not currently available for trading on Revolut. Consider alternative brokers.</p>'}
  </div>
</div>

<footer>
  <p>Real-time data via <a href="https://finance.yahoo.com">Yahoo Finance</a> &amp; <a href="https://binance.com">Binance</a></p>
  <p style="margin-top:.5rem">Not financial advice &nbsp;·&nbsp; <a href="{base_url}/docs">API Docs</a></p>
</footer>
</body>
</html>"""


def build_sitemap(base_url: str, slugs: list[str]) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d")
    urls = "\n".join(
        f"""  <url>
    <loc>{base_url}/{slug}</loc>
    <lastmod>{now}</lastmod>
    <changefreq>daily</changefreq>
    <priority>{'0.9' if 'price/' in slug else '0.8'}</priority>
  </url>"""
        for slug in slugs
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}
</urlset>"""


def build_robots(base_url: str) -> str:
    return f"""User-agent: *
Allow: /

Sitemap: {base_url}/sitemap.xml
"""


# ─── async price fetcher ──────────────────────────────────────────────────────
async def _fetch_price(ticker: str, is_crypto: bool, semaphore: asyncio.Semaphore) -> dict | None:
    async with semaphore:
        try:
            if is_crypto:
                sym = ticker + "USDT"
                async with httpx.AsyncClient(timeout=8) as c:
                    r = await c.get("https://api.binance.com/api/v3/ticker/24hr", params={"symbol": sym})
                    d = r.json()
                return {
                    "price":      round(float(d["lastPrice"]), 6),
                    "change_pct": round(float(d["priceChangePercent"]), 2),
                }
            else:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
                headers = {"User-Agent": "Mozilla/5.0 (compatible; mcprice/2.0)"}
                async with httpx.AsyncClient(timeout=8, follow_redirects=True) as c:
                    r = await c.get(url, params={"interval": "1d", "range": "2d"}, headers=headers)
                    data = r.json()
                meta  = data["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice", 0.0)
                prev  = meta.get("chartPreviousClose") or price
                chg_p = ((price - prev) / prev * 100) if prev else 0.0
                return {"price": round(price, 4), "change_pct": round(chg_p, 2)}
        except Exception as e:
            print(f"  ⚠  {ticker}: {e}", flush=True)
            return None


# ─── main generator ───────────────────────────────────────────────────────────
async def generate(base_url: str, live_prices: bool = True):
    print(f"🚀 mcprice SEO Generator — base URL: {base_url}")
    print(f"   Output dir: {OUT_DIR}")

    # create subdirectories
    (OUT_DIR / "price").mkdir(exist_ok=True)

    all_slugs: list[str] = []
    sem = asyncio.Semaphore(5)

    # ── stock pages ──────────────────────────────────────────────────────────
    print(f"\n📈 Generating {len(REVOLUT_STOCKS)} stock pages…")
    if live_prices:
        tasks   = {t: _fetch_price(t, False, sem) for t in REVOLUT_STOCKS}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        prices  = dict(zip(tasks.keys(), results))
    else:
        prices = {}

    for ticker, name in REVOLUT_STOCKS.items():
        pdata      = prices.get(ticker) if live_prices else None
        price      = pdata.get("price")      if isinstance(pdata, dict) else None
        change_pct = pdata.get("change_pct") if isinstance(pdata, dict) else None
        slug       = f"price/{ticker.lower()}"

        html = build_ticker_page(
            ticker=ticker, name=name,
            price=price, change_pct=change_pct,
            asset_type="stock", on_revolut=True,
            base_url=base_url,
        )
        (OUT_DIR / slug).with_suffix(".html").write_text(html, encoding="utf-8")
        all_slugs.append(slug)
        print(f"  ✅ {ticker}", end="\r")

    # ── crypto pages ─────────────────────────────────────────────────────────
    print(f"\n\n🪙  Generating {len(REVOLUT_CRYPTO)} crypto pages…")
    if live_prices:
        tasks   = {t: _fetch_price(t, True, sem) for t in REVOLUT_CRYPTO}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        prices  = dict(zip(tasks.keys(), results))
    else:
        prices = {}

    for ticker in sorted(REVOLUT_CRYPTO):
        pdata      = prices.get(ticker) if live_prices else None
        price      = pdata.get("price")      if isinstance(pdata, dict) else None
        change_pct = pdata.get("change_pct") if isinstance(pdata, dict) else None
        slug       = f"price/{ticker.lower()}"

        html = build_ticker_page(
            ticker=ticker, name=ticker,
            price=price, change_pct=change_pct,
            asset_type="crypto", on_revolut=True,
            base_url=base_url,
        )
        (OUT_DIR / slug).with_suffix(".html").write_text(html, encoding="utf-8")
        all_slugs.append(slug)
        print(f"  ✅ {ticker}", end="\r")

    # ── sitemap ──────────────────────────────────────────────────────────────
    print(f"\n\n🗺  Writing sitemap.xml ({len(all_slugs)} URLs)…")
    sitemap = build_sitemap(base_url, all_slugs)
    (OUT_DIR / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    # ── robots.txt ───────────────────────────────────────────────────────────
    robots = build_robots(base_url)
    (OUT_DIR / "robots.txt").write_text(robots, encoding="utf-8")

    print(f"\n✅ Done! Generated {len(all_slugs)} pages + sitemap.xml + robots.txt")
    print(f"   → {OUT_DIR}")
    return len(all_slugs)


# ─── entry ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="mcprice Programmatic SEO Generator")
    parser.add_argument(
        "--base-url",
        default=os.getenv("BASE_URL", "https://mcprice.fly.dev"),
        help="Base URL of your deployed site",
    )
    parser.add_argument(
        "--no-live",
        action="store_true",
        help="Skip live price fetching (faster, no prices embedded)",
    )
    args = parser.parse_args()

    asyncio.run(generate(base_url=args.base_url.rstrip("/"), live_prices=not args.no_live))
