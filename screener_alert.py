#!/usr/bin/env python3
"""
Finviz Screener Daily Alert — Telegram Bot
Fetches matching Tech stocks from your Finviz screener and sends them via Telegram.
Runs via GitHub Actions every weekday at 8:15 AM UAE time.

Filters applied:
  Sector        : Technology
  Debt/Equity   : Under 1
  EPS Growth 3Y : Over 20%
  Sales Growth 3Y: Over 20%
  Est. LT Growth: Over 20%
  PEG Ratio     : Under 1
  P/E Ratio     : Under 50
"""

import urllib.request
import urllib.parse
import urllib.error
import json
import re
import sys
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
BOT_TOKEN = "8668525958:AAG7LRqZbNuDVUXPLeqQmkSa66hi-NgSzpQ"
CHAT_ID   = "6050679787"

SCREENER_URL = (
    "https://finviz.com/screener.ashx?v=111&ft=4"
    "&f=fa_debteq_u1,fa_eps3years_o20,fa_estltgrowth_o20,"
    "fa_pe_u50,fa_peg_u1,fa_sales3years_o20,sec_technology"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
}
# ──────────────────────────────────────────────────────────────────────────────


def log(msg):
    print(msg, flush=True)


def fetch_screener():
    log(f"Fetching: {SCREENER_URL}")
    req = urllib.request.Request(SCREENER_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    log(f"Fetched {len(html):,} bytes")
    return html


def parse_results(html):
    """
    Extract list of (ticker, company, price, change_pct) from screener HTML.
    Falls back to tickers-only if the richer pattern doesn't match.
    """
    # Primary: grab full rows from the overview table
    # Finviz row structure (v=111 Overview):
    #   <a class="screener-link-primary" href="quote.ashx?t=TICKER&...">TICKER</a>
    #   ...company name in next <a class="screener-link">...
    #   ...price in subsequent <td>
    #   ...change in <td class="is-[red|green]">

    rows = re.findall(
        r'class="screener-link-primary"[^>]*>([A-Z]{1,6})</a>'   # ticker
        r'(?:(?!</tr>).)*?'                                        # anything up to end of row
        r'class="screener-link"[^>]*>([^<]{1,40})</a>'           # company
        r'(?:(?!</tr>).)*?'                                        # anything
        r'<td[^>]*>\$?([\d,\.]+)</td>'                            # price
        r'(?:(?!</tr>).)*?'                                        # anything
        r'<td[^>]*class="[^"]*is-[^"]*"[^>]*>([^<]+)</td>',      # change %
        html, re.DOTALL
    )

    if rows:
        seen = set()
        results = []
        for ticker, company, price, change in rows:
            if ticker not in seen:
                seen.add(ticker)
                results.append((ticker, company.strip(), price, change.strip()))
        return results

    # Fallback: tickers only
    tickers = re.findall(
        r'class="screener-link-primary"[^>]*>([A-Z]{1,6})</a>',
        html
    )
    seen = set()
    return [(t, "", "", "") for t in tickers if not (t in seen or seen.add(t))]


def parse_total(html):
    m = re.search(r'Total:\s*<b>(\d+)</b>', html)
    if m:
        return int(m.group(1))
    # Alternative pattern
    m = re.search(r'(\d+)\s+Total', html)
    return int(m.group(1)) if m else None


def esc(text):
    """Escape special characters for Telegram MarkdownV2."""
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, '\\' + ch)
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

    # Fetch screener
    try:
        html = fetch_screener()
    except Exception as e:
        log(f"ERROR fetching screener: {e}")
        send_telegram(f"⚠️ Screener fetch failed: {esc(str(e))}")
        sys.exit(1)

    results = parse_results(html)
    total   = parse_total(html)
    today   = datetime.now().strftime("%A, %b %d %Y")

    log(f"Parsed {len(results)} tickers on this page (total: {total})")

    # Build message
    lines = [f"📡 *Tech Screener — {esc(today)}*\n"]

    if not results:
        lines.append("_No stocks matched today\\._")
        lines.append("\n_Criteria: D/E \\< 1 · EPS 3Y \\> 20% · Sales 3Y \\> 20%_")
        lines.append("_Est\\. LT Growth \\> 20% · PEG \\< 1 · P/E \\< 50_")
        send_telegram("\n".join(lines))
        return

    n = total if total else len(results)
    lines.append(f"*{n} stock{'s' if n != 1 else ''}* matched your criteria:\n")
    lines.append("_D/E \\< 1 · EPS 3Y \\> 20% · Sales 3Y \\> 20%_")
    lines.append("_Est\\. LT Growth \\> 20% · PEG \\< 1 · P/E \\< 50_\n")

    for ticker, company, price, change in results:
        line = f"• *{esc(ticker)}*"
        if company:
            line += f"   {esc(company[:30])}"
        if price:
            line += f"   \\${esc(price)}"
        if change:
            arrow = "▲" if change.startswith("+") else ("▼" if change.startswith("-") else "")
            line += f"   {arrow}{esc(change)}"
        lines.append(line)

    if total and total > len(results):
        remaining = total - len(results)
        lines.append(f"\n_\\+{remaining} more — view all at [finviz\\.com]"
                      f"(https://finviz.com/screener.ashx?v=111&ft=4"
                      f"&f=fa_debteq_u1,fa_eps3years_o20,fa_estltgrowth_o20,"
                      f"fa_pe_u50,fa_peg_u1,fa_sales3years_o20,sec_technology)_")

    msg = "\n".join(lines)
    log(f"\nMessage preview:\n{msg}\n")
    send_telegram(msg)
    log("=== Done ===")


if __name__ == "__main__":
    main()
