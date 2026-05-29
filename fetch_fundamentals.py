#!/usr/bin/env python3
"""
Fetch fundamental data for portfolio tickers using yfinance.
Writes fundamentals.json to the repo root for GitHub Pages to serve.
Run via GitHub Actions daily.
"""

import json
import math
import sys
import time
from datetime import datetime

import yfinance as yf

# ── Load tickers from file ────────────────────────────────────────────────────
try:
    with open('tickers.txt') as f:
        TICKERS = [t.strip().upper() for t in f if t.strip()]
except FileNotFoundError:
    print("tickers.txt not found — using defaults")
    TICKERS = ['META', 'ONTO', 'SMH']

print(f"Fetching fundamentals for: {TICKERS}")

# ── Helpers ───────────────────────────────────────────────────────────────────
def safe(val):
    """Convert numpy/nan values to Python native types."""
    if val is None:
        return None
    try:
        if math.isnan(float(val)):
            return None
        return float(val)
    except (TypeError, ValueError):
        return str(val) if val else None


def cagr(start, end, years):
    try:
        s, e = float(start), float(end)
        if s <= 0 or e <= 0 or years <= 0:
            return None
        return round((e / s) ** (1 / years) - 1, 5)
    except Exception:
        return None


def series_to_list(series):
    """Convert a pandas Series (sorted ascending by date) to a clean float list."""
    if series is None or series.empty:
        return []
    result = []
    for v in series:
        try:
            f = float(v)
            result.append(None if math.isnan(f) else f)
        except Exception:
            result.append(None)
    return result


# ── Fetch ─────────────────────────────────────────────────────────────────────
output = {}

for sym in TICKERS:
    print(f"\n→ {sym}")
    try:
        t = yf.Ticker(sym)
        info = t.info or {}

        # ── Basic fundamentals from info ──────────────────────────────────────
        rec = {
            'industry':      info.get('industry') or info.get('sector') or '',
            'trailingPE':    safe(info.get('trailingPE')),
            'forwardPE':     safe(info.get('forwardPE')),
            'pegRatio':      safe(info.get('pegRatio')),
            'debtToEquity':  safe(info.get('debtToEquity')),   # Yahoo returns as % (e.g. 45.2 = D/E 0.45)
            'freeCashflow':  safe(info.get('freeCashflow')),
            'grossMargins':  safe(info.get('grossMargins')),
            'profitMargins': safe(info.get('profitMargins')),
            'returnOnEquity':safe(info.get('returnOnEquity')),
            'eps3y': None, 'eps5y': None,
            'rev3y': None, 'rev5y': None,
            'epsNextY': None, 'revNext5y': None,
        }

        # ── Forward EPS growth (next 1Y) ──────────────────────────────────────
        try:
            fwd = safe(info.get('forwardEps'))
            trail = safe(info.get('trailingEps'))
            if fwd and trail and trail > 0:
                rec['epsNextY'] = round(fwd / trail - 1, 5)
        except Exception:
            pass

        # ── Analyst long-term growth estimate (next 5Y revenue) ───────────────
        try:
            gt = t.growth_estimates
            if gt is not None and not gt.empty and '+5y' in gt.index:
                row = gt.loc['+5y']
                # row may have multiple columns (industry, sector, sp500, stock)
                val = None
                for col in row.index:
                    v = safe(row[col])
                    if v is not None:
                        val = v
                        break
                rec['revNext5y'] = val
        except Exception:
            pass

        # ── Annual income statement for CAGR ──────────────────────────────────
        try:
            fin = t.income_stmt          # columns = dates (newest first), rows = metrics
            if fin is not None and not fin.empty:
                fin_asc = fin[sorted(fin.columns)]   # ascending date order

                # EPS CAGR
                for eps_row in ['Basic EPS', 'Diluted EPS']:
                    if eps_row in fin_asc.index:
                        eps_vals = series_to_list(fin_asc.loc[eps_row])
                        eps_vals = [v for v in eps_vals if v is not None]
                        if len(eps_vals) >= 4:
                            rec['eps3y'] = cagr(eps_vals[-4], eps_vals[-1], 3)
                        if len(eps_vals) >= 2:
                            n = len(eps_vals) - 1
                            rec['eps5y'] = cagr(eps_vals[0], eps_vals[-1], n)
                        break

                # Revenue CAGR
                if 'Total Revenue' in fin_asc.index:
                    rev_vals = series_to_list(fin_asc.loc['Total Revenue'])
                    rev_vals = [v for v in rev_vals if v is not None]
                    if len(rev_vals) >= 4:
                        rec['rev3y'] = cagr(rev_vals[-4], rev_vals[-1], 3)
                    if len(rev_vals) >= 2:
                        n = len(rev_vals) - 1
                        rec['rev5y'] = cagr(rev_vals[0], rev_vals[-1], n)

        except Exception as e:
            print(f"  Income stmt error: {e}")

        output[sym] = rec
        print(f"  PE={rec['trailingPE']}  PEG={rec['pegRatio']}  D/E={rec['debtToEquity']}  FCF={rec['freeCashflow']}")
        print(f"  EPS 3Y={rec['eps3y']}  EPS 5Y={rec['eps5y']}  Rev 3Y={rec['rev3y']}  Rev 5Y={rec['rev5y']}")

    except Exception as e:
        print(f"  ERROR: {e}")
        output[sym] = {'error': str(e)}

    # Rate limit — avoid Yahoo Finance blocking
    time.sleep(0.5)

output['_updated'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
output['_tickers'] = TICKERS

def sanitize(obj):
    """Recursively replace NaN/Infinity with None for valid JSON."""
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    return obj

with open('fundamentals.json', 'w') as f:
    json.dump(sanitize(output), f, indent=2)

print(f"\n✅ fundamentals.json written for {len(TICKERS)} tickers")
