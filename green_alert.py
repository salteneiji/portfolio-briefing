#!/usr/bin/env python3
"""
Green Across the Board Alert — Telegram Bot
Reads fundamentals.json from GitHub Pages and sends stocks that are
green on every tracked metric. Runs daily via GitHub Actions.

Green thresholds (matching index.html color rules):
  P/E          < 20
  PEG          < 1
  D/E          < 1      (Yahoo returns x100, so raw < 100)
  Free CF      > 0
  EPS 3Y       > 20%
  EPS 1Y Next  > 20%
  Rev 3Y       > 20%
  Rev TTM      > 20%
  Gross Margin > 50%
  ROE          > 15%
  Current Ratio> 1.5
"""

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
BOT_TOKEN        = "8668525958:AAG7LRqZbNuDVUXPLeqQmkSa66hi-NgSzpQ"
CHAT_ID          = "6050679787"
FUNDAMENTALS_URL = "https://salteneiji.github.io/portfolio-briefing/fundamentals.json"
# ──────────────────────────────────────────────────────────────────────────────

CRITERIA = {
    'trailingPE':    lambda v: v < 50,
    'pegRatio':      lambda v: v < 1,
    'debtToEquity':  lambda v: v < 100,   # Yahoo stores as % e.g. 45 = D/E 0.45
    'freeCashflow':  lambda v: v > 0,
    'eps3y':         lambda v: v > 0.20,
    'epsNextY':      lambda v: v > 0.20,
    'rev3y':         lambda v: v > 0.20,
    'revenueGrowth': lambda v: v > 0.20,
    'grossMargins':  lambda v: v > 0.50,
    'returnOnEquity':lambda v: v > 0.15,
    'currentRatio':  lambda v: v > 1.5,
}

LABELS = {
    'trailingPE':    'P/E',
    'pegRatio':      'PEG',
    'debtToEquity':  'D/E',
    'freeCashflow':  'FCF',
    'eps3y':         'EPS 3Y',
    'epsNextY':      'EPS 1Y Next',
    'rev3y':         'Rev 3Y',
    'revenueGrowth': 'Rev TTM',
    'grossMargins':  'Gross Margin',
    'returnOnEquity':'ROE',
    'currentRatio':  'Current Ratio',
}


def log(msg):
    print(msg, flush=True)


def fetch_fundamentals():
    log(f"Fetching {FUNDAMENTALS_URL} ...")
    req = urllib.request.Request(FUNDAMENTALS_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def score_ticker(data):
    """Return (pass_count, [failed_label, ...]) for a ticker's data dict."""
    passed = 0
    failed = []
    for field, check in CRITERIA.items():
        val = data.get(field)
        try:
            if val is not None and check(float(val)):
                passed += 1
            else:
                failed.append(LABELS[field])
        except (TypeError, ValueError):
            failed.append(LABELS[field])
    return passed, failed


def esc(text):
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
            log("✅ Sent.")
        else:
            log(f"Telegram error: {result}")
            sys.exit(1)


def main():
    log("=== Green Across the Board Alert ===")

    try:
        fund = fetch_fundamentals()
    except Exception as e:
        send_telegram(f"⚠️ Could not fetch fundamentals\\.json: {esc(str(e))}")
        sys.exit(1)

    updated = fund.get('_updated', '')
    tickers = [k for k in fund if not k.startswith('_')]

    all_green   = []   # 11/11
    almost_green = []  # 9–10/11

    for ticker in tickers:
        d = fund[ticker]
        if not isinstance(d, dict) or d.get('error'):
            continue
        count, failed = score_ticker(d)
        if count == 11:
            all_green.append((ticker, d, failed))
        elif count >= 9:
            almost_green.append((ticker, d, failed, count))

    # Sort almost_green by score desc
    almost_green.sort(key=lambda x: x[3], reverse=True)

    today = datetime.now().strftime("%A, %b %d %Y")
    lines = [f"📊 *Daily Stock Alert — {esc(today)}*\n"]

    # ── 🟢 All green ─────────────────────────────────────────────────────────
    lines.append(f"🟢 *All Green \\(11/11\\)* — {len(all_green)} stock{'s' if len(all_green)!=1 else ''}")
    if not all_green:
        lines.append("_None today\\._")
    else:
        for ticker, d, _ in all_green:
            pe  = f"PE={d['trailingPE']:.1f}"     if d.get('trailingPE') else ''
            peg = f"PEG={d['pegRatio']:.2f}"       if d.get('pegRatio')   else ''
            eps = f"EPS3Y={d['eps3y']*100:.1f}%"   if d.get('eps3y')      else ''
            industry = esc(d.get('industry', '')[:25])
            lines.append(f"• *{esc(ticker)}*  {industry}  _{esc(pe)} · {esc(peg)} · {esc(eps)}_")

    lines.append("")

    # ── 🟡 Almost green ───────────────────────────────────────────────────────
    lines.append(f"🟡 *Almost Green \\(9–10/11\\)* — {len(almost_green)} stock{'s' if len(almost_green)!=1 else ''}")
    if not almost_green:
        lines.append("_None today\\._")
    else:
        for ticker, d, failed, count in almost_green:
            pe  = f"PE={d['trailingPE']:.1f}"     if d.get('trailingPE') else ''
            peg = f"PEG={d['pegRatio']:.2f}"       if d.get('pegRatio')   else ''
            industry = esc(d.get('industry', '')[:25])
            missing = esc(', '.join(failed))
            lines.append(f"• *{esc(ticker)}* \\({count}/11\\)  {industry}  _{esc(pe)} · {esc(peg)}_")
            lines.append(f"  ↳ Missing: _{missing}_")

    lines.append(f"\n_Criteria: P/E\\<50 · PEG\\<1 · D/E\\<1 · FCF\\>0 · EPS 3Y\\>20% · EPS Next\\>20% · Rev 3Y\\>20% · Rev TTM\\>20% · Gross Margin\\>50% · ROE\\>15% · Current Ratio\\>1\\.5_")

    send_telegram("\n".join(lines))
    log("=== Done ===")


if __name__ == "__main__":
    main()
