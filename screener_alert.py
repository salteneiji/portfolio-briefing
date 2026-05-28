#!/usr/bin/env python3
"""
Finviz Screener Daily Alert — Telegram Bot
Fetches matching Tech stocks from Finviz and sends them via Telegram.
Runs via GitHub Actions every weekday at 8:15 AM UAE time.

Filters:
  Sector: Technology | D/E < 1 | EPS 3Y > 20% | Sales 3Y > 20%
  Est. LT Growth > 20% | PEG < 1 | P/E < 50
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime

import requests

# ── CONFIG ────────────────────────────────────────────────────────────────────
BOT_TOKEN = "8668525958:AAG7LRqZbNuDVUXPLeqQmkSa66hi-NgSzpQ"
CHAT_ID   = "6050679787"

SCREENER_URL = (
    "https://finviz.com/screener.ashx?v=111&ft=4"
    "&f=fa_debteq_u1,fa_eps3years_o20,fa_estltgrowth_o20,"
    "fa_pe_u50,fa_peg_u1,fa_sales3years_o20,sec_technology"
)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control":   "max-age=0",
}
# ──────────────────────────────────────────────────────────────────────────────


def log(msg):
    print(msg, flush=True)


def fetch_screener():
    """Use a persistent session: visit homepage first to get cookies, then screener."""
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    # Visit homepage to establish session cookies (mimics real browser flow)
    log("Establishing Finviz session...")
    session.get("https://finviz.com/", timeout=15)

    # Now fetch the screener with cookies set
    log(f"Fetching screener results...")
    resp = session.get(SCREENER_URL, timeout=20)
    resp.raise_for_status()
    log(f"Response: {resp.status_code}, {len(resp.text):,} bytes")
    return resp.text


def parse_results(html):
    """Extract list of (ticker, company, price, change) from screener HTML."""

    # Tickers appear as: <a class="screener-link-primary" href="quote.ashx?t=NVDA&...">NVDA</a>
    tickers = re.findall(
        r'class="screener-link-primary"[^>]*>([A-Z]{1,6})</a>',
        html
    )
    tickers = list(dict.fromkeys(tickers))  # deduplicate, preserve order

    if not tickers:
        log("WARNING: No tickers found in HTML. Showing first 500 chars:")
        log(html[:500])
        return []

    # Try to extract full row data (ticker, company, price, change)
    results = []
    for ticker in tickers:
        # Find the row containing this ticker and extract company/price/change
        pattern = (
            rf'class="screener-link-primary"[^>]*>{re.escape(ticker)}</a>'
            r'(?:(?!</tr>).){0,800}?'
            r'class="screener-link"[^>]*>([^<]{1,40})</a>'
            r'(?:(?!</tr>).){0,600}?'
            r'<td[^>]*>\$?([\d,\.]+)</td>'
            r'(?:(?!</tr>).){0,300}?'
            r'<td[^>]*class="[^"]*is-[^"]*"[^>]*>([^<]+)</td>'
        )
        m = re.search(pattern, html, re.DOTALL)
        if m:
            results.append((ticker, m.group(1).strip(), m.group(2), m.group(3).strip()))
        else:
            results.append((ticker, "", "", ""))

    return results


def parse_total(html):
    m = re.search(r'Total:\s*<b>(\d+)</b>', html)
    return int(m.group(1)) if m else None


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
        html = fetch_screener()
    except Exception as e:
        log(f"ERROR: {e}")
        send_telegram(f"⚠️ Screener fetch failed: {esc(str(e))}")
        sys.exit(1)

    results = parse_results(html)
    total   = parse_total(html)
    today   = datetime.now().strftime("%A, %b %d %Y")

    log(f"Found {len(results)} tickers on page (Finviz total: {total})")

    # Build Telegram message
    lines = [f"📡 *Tech Screener — {esc(today)}*\n"]

    if not results:
        lines.append("_No stocks matched today\\._\n")
        lines.append("_Filters: Tech · D/E \\< 1 · EPS 3Y \\> 20%_")
        lines.append("_Sales 3Y \\> 20% · Est\\. LT \\> 20% · PEG \\< 1 · P/E \\< 50_")
        send_telegram("\n".join(lines))
        return

    n = total if total else len(results)
    lines.append(f"*{n} stock{'s' if n != 1 else ''}* matched:\n")
    lines.append("_Tech · D/E \\< 1 · EPS 3Y \\> 20% · Sales 3Y \\> 20%_")
    lines.append("_Est\\. LT Growth \\> 20% · PEG \\< 1 · P/E \\< 50_\n")

    for ticker, company, price, change in results:
        line = f"• *{esc(ticker)}*"
        if company:
            line += f"   {esc(company[:30])}"
        if price:
            line += f"   \\${esc(price)}"
        if change:
            arrow = "▲" if not change.startswith("-") else "▼"
            line += f"   {arrow}{esc(change)}"
        lines.append(line)

    if total and total > len(results):
        lines.append(f"\n_\\+{total - len(results)} more — [view on Finviz]"
                     f"(https://finviz\\.com/screener\\.ashx\\?v\\=111\\&ft\\=4"
                     f"\\&f\\=fa\\_debteq\\_u1,fa\\_eps3years\\_o20,fa\\_estltgrowth\\_o20,"
                     f"fa\\_pe\\_u50,fa\\_peg\\_u1,fa\\_sales3years\\_o20,sec\\_technology)_")

    msg = "\n".join(lines)
    log(f"\nMessage:\n{msg}\n")
    send_telegram(msg)
    log("=== Done ===")


if __name__ == "__main__":
    main()
