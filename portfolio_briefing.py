#!/usr/bin/env python3
"""
Daily Portfolio Briefing — Telegram Bot
Sends a morning summary of your portfolio P&L to Telegram.
Schedule with cron: 0 8 * * 1-5  (8am, Mon–Fri)
"""

import urllib.request
import urllib.parse
import json
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
BOT_TOKEN = "8668525958:AAG7LRqZbNuDVUXPLeqQmkSa66hi-NgSzpQ"
CHAT_ID   = "6050679787"

PORTFOLIO = [
    {"ticker": "META",  "shares": 2711.40 / 635.33, "avg_price": 635.33,  "name": "Meta Platforms"},
    {"ticker": "ONTO",  "shares": 135.00  / 140.36, "avg_price": 140.36,  "name": "Onto Innovation"},
    {"ticker": "SMH",   "shares": 271.50  / 595.94, "avg_price": 595.94,  "name": "VanEck Semi ETF"},
]
# ──────────────────────────────────────────────────────────────────────────────


def fetch_price(ticker):
    """Fetch current price from Yahoo Finance (no API key needed)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    meta = data["chart"]["result"][0]["meta"]
    price = meta.get("regularMarketPrice") or meta.get("previousClose")
    prev  = meta.get("previousClose", price)
    return round(price, 2), round(prev, 2)


def pct(value, reference):
    return (value - reference) / reference * 100


def arrow(change):
    if change > 2:   return "🚀"
    if change > 0.5: return "🟢"
    if change < -2:  return "🔴"
    if change < -0.5:return "🟡"
