#!/usr/bin/env python3
"""
Daily Portfolio Briefing — Telegram Bot
Sends a morning summary of your portfolio P&L to Telegram.
Schedule with cron: 0 4 * * 1-5  (8:00 AM UAE time, Mon-Fri)
"""

import urllib.request
import urllib.parse
import urllib.error
import json
import sys
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
BOT_TOKEN = "8668525958:AAG7LRqZbNuDVUXPLeqQmkSa66hi-NgSzpQ"
CHAT_ID   = "6050679787"

PORTFOLIO = [
    {"ticker": "META",  "shares": 2711.40 / 635.33, "avg_price": 635.33, "name": "Meta Platforms"},
    {"ticker": "ONTO",  "shares": 135.00  / 140.36, "avg_price": 140.36, "name": "Onto Innovation"},
    {"ticker": "SMH",   "shares": 271.50  / 595.94, "avg_price": 595.94, "name": "VanEck Semi ETF"},
]
# ──────────────────────────────────────────────────────────────────────────────


def log(msg):
    print(msg, flush=True)


def fetch_price(ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        meta  = data["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        prev  = meta.get("previousClose", price)
        log(f"  {ticker}: ${price:.2f} (prev: ${prev:.2f})")
        return round(price, 2), round(prev, 2)
    except urllib.error.HTTPError as e:
        raise Exception(f"HTTP {e.code} from Yahoo for {ticker}")
    except Exception as e:
        raise Exception(f"Failed to fetch {ticker}: {e}")


def pct(value, reference):
    return (value - reference) / reference * 100


def arrow(change):
    if change > 2:    return "🚀"
    if change > 0.5:  return "🟢"
    if change < -2:   return "🔴"
    if change < -0.5: return "🟡"
    return "⚪"


def build_message(results):
    today = datetime.now().strftime("%A, %b %d %Y")
    lines = [f"📊 *Portfolio Briefing — {today}*\n"]

    total_cost    = 0
    total_current = 0

    for r in results:
        cost      = r["shares"] * r["avg_price"]
        current   = r["shares"] * r["price"]
        day_chg   = pct(r["price"], r["prev"])
        total_chg = pct(current, cost)
        total_cost    += cost
        total_current += current
        icon = arrow(day_chg)

        lines.append(
            f"{icon} *{r['ticker']}* — ${r['price']:.2f}\n"
            f"   Day: {day_chg:+.2f}%  |  P&L: {total_chg:+.2f}% (${current - cost:+.2f})\n"
        )

    overall_pct = pct(total_current, total_cost)
    overall_abs = total_current - total_cost
    lines.append(
        f"─────────────────\n"
        f"💼 *Total Value:* ${total_current:.2f}\n"
        f"📈 *Overall P&L:* {overall_pct:+.2f}% (${overall_abs:+.2f})\n"
    )

    if overall_pct > 3:
        lines.append("_Strong day — portfolio performing well._")
    elif overall_pct < -3:
        lines.append("_Rough day — review your positions._")
    else:
        lines.append("_Steady. No action needed._")

    return "\n".join(lines)


def send_telegram(message):
    log("Sending Telegram message...")
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id":    CHAT_ID,
        "text":       message,
        "parse_mode": "Markdown",
    }).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded"
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                log("Telegram message sent successfully.")
            else:
                log(f"Telegram error: {result}")
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise Exception(f"Telegram HTTP {e.code}: {body}")
    except Exception as e:
        raise Exception(f"Telegram send failed: {e}")


def main():
    log("=== Portfolio Briefing Starting ===")
    results = []
    errors  = []

    log("Fetching prices...")
    for pos in PORTFOLIO:
        try:
            price, prev = fetch_price(pos["ticker"])
            results.append({**pos, "price": price, "prev": prev})
        except Exception as e:
            log(f"ERROR: {e}")
            errors.append(str(e))

    if errors:
        msg = "⚠️ Portfolio bot error:\n" + "\n".join(errors)
        log(msg)
        send_telegram(msg)
        sys.exit(1)

    log("Building message...")
    msg = build_message(results)
    log(f"Message:\n{msg}")
    send_telegram(msg)
    log("=== Done ===")


if __name__ == "__main__":
    main()
