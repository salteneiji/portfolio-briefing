#!/usr/bin/env python3
"""
Finviz Screener Daily Alert — Telegram Bot
Uses the finvizfinance library to reliably pull screener results.
Runs via GitHub Actions every weekday at 8:15 AM UAE time.

Filters:
  Sector: Technology | D/E < 1 | EPS 3Y > 20% | Sales 3Y > 20%
  Est. LT Growth > 20% | PEG < 1 | P/E < 50
"""

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime

from finvizfinance.screener.overview import Overview

# ── CONFIG ────────────────────────────────────────────────────────────────────
BOT_TOKEN = "8668525958:AAG7LRqZbNuDVUXPLeqQmkSa66hi-NgSzpQ"
CHAT_ID   = "6050679787"

FILTERS = {
    'Sector'                    : 'Technology',
    'Debt/Equity'               : 'Under 1',
    'EPS growthpast 5 years'    : 'Over 20%',
    'Sales growthpast 5 years'  : 'Over 20%',
    'EPS growthnext 5 years'    : 'Over 20%',
    'P/E'                       : 'Under 50',
    'PEG'                       : 'Under 1',
}
# ──────────────────────────────────────────────────────────────────────────────


def log(msg):
    print(msg, flush=True)


def run_screener():
    log("Running Finviz screener via finvizfinance...")
    screen = Overview()
    screen.set_filter(filters_dict=FILTERS)
    df = screen.screener_view()
    log(f"Screener returned {len(df) if df is not None else 0} rows")
    if df is not None:
        log(f"Columns: {list(df.columns)}")
    return df


def esc(text):
    """Escape Telegram MarkdownV2 special characters."""
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = str(text).replace(ch, '\\' + ch)
    return text


def send_telegram(message):
    log("Sending Telegram message...")
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id":    CHAT_ID,
        "text":       message,
        "parse_mode": "MarkdownV2",
    }).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
        if result.get("ok"):
            log("✅ Telegram message sent.")
        else:
            log(f"Telegram error: {result}")
            sys.exit(1)


def main():
    log("=== Finviz Screener Alert Starting ===")

    try:
        df = run_screener()
    except Exception as e:
        log(f"ERROR: {e}")
        send_telegram(f"⚠️ Screener failed: {esc(str(e))}")
        sys.exit(1)

    today = datetime.now().strftime("%A, %b %d %Y")
    lines = [f"📡 *Tech Screener — {esc(today)}*\n"]

    if df is None or len(df) == 0:
        lines.append("_No stocks matched today\\._\n")
        lines.append("_Tech · D/E \\< 1 · EPS 3Y \\> 20% · Sales 3Y \\> 20%_")
        lines.append("_Est\\. LT Growth \\> 20% · PEG \\< 1 · P/E \\< 50_")
        send_telegram("\n".join(lines))
        return

    n = len(df)
    lines.append(f"*{n} stock{'s' if n != 1 else ''}* matched:\n")
    lines.append("_Tech · D/E \\< 1 · EPS 3Y \\> 20% · Sales 3Y \\> 20%_")
    lines.append("_Est\\. LT Growth \\> 20% · PEG \\< 1 · P/E \\< 50_\n")

    for _, row in df.iterrows():
        ticker  = str(row.get('Ticker', '')).strip()
        company = str(row.get('Company', '')).strip()[:28]
        price   = str(row.get('Price', '')).strip()
        change  = str(row.get('Change', '')).strip()

        if not ticker or ticker == 'nan':
            continue

        line = f"• *{esc(ticker)}*   {esc(company)}"
        if price and price != 'nan' and price != '-':
            line += f"   \\${esc(price)}"
        if change and change != 'nan' and change != '-':
            arrow = '▲' if not change.startswith('-') else '▼'
            line += f"   {arrow}{esc(change)}"
        lines.append(line)

    send_telegram("\n".join(lines))
    log("=== Done ===")


if __name__ == "__main__":
    main()
