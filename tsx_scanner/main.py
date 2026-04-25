"""
TSX SWING TRADE SCANNER — Main Runner
Orchestrates all 5 layers:
  Layer 1: Data fetch + indicators
  Layer 2: Pattern detection
  Layer 3: Trend context + S&R
  Layer 4: Scoring + trade plan
  Layer 5: Plain English report

Usage:
  python main.py                 # scan full watchlist
  python main.py SU.TO CNQ.TO   # scan specific tickers
"""

import sys
import time
from datetime import datetime

from layers.layer1_data    import (fetch_data, fetch_weekly, add_all_indicators,
                                    passes_liquidity, WATCHLIST, ALL_TICKERS)
from layers.layer2_patterns import detect_all_patterns
from layers.layer3_context  import detect_stage, detect_dow_phase, detect_sr_zones
from layers.layer4_scoring  import score_setup
from layers.layer5_report   import generate_daily_report

ACCOUNT_SIZE = 1490.0


def scan_ticker(ticker: str, sector: str) -> object:
    """Run complete 5-layer scan on a single ticker."""

    # Layer 1 — Data
    df = fetch_data(ticker, period="1y")
    if df.empty:
        return None

    if not passes_liquidity(df):
        print(f"  [{ticker}] Skipped — insufficient liquidity")
        return None

    df_weekly = fetch_weekly(ticker)
    df = add_all_indicators(df)

    # Layer 2 — Patterns
    patterns = detect_all_patterns(df)

    # Layer 3 — Context
    trend  = detect_stage(df, df_weekly)
    phase  = detect_dow_phase(df)
    zones  = detect_sr_zones(df, lookback=252)

    # Layer 4 — Score
    plan = score_setup(
        ticker=ticker,
        sector=sector,
        df=df,
        patterns=patterns,
        trend=trend,
        zones=zones,
        dow_phase=phase,
        account_size=ACCOUNT_SIZE,
    )

    return plan


def run_scanner(tickers: list[str] = None) -> list:
    """Scan all tickers and return sorted trade plans."""

    if tickers:
        # Build sector lookup for specified tickers
        sector_map = {t: "Custom" for t in tickers}
        for sector, stocks in WATCHLIST.items():
            for s in stocks:
                if s in sector_map:
                    sector_map[s] = sector
        scan_list = [(t, sector_map.get(t, "Custom")) for t in tickers]
    else:
        scan_list = [
            (ticker, sector)
            for sector, tickers in WATCHLIST.items()
            for ticker in tickers
        ]

    print(f"\nTSX Scanner starting — {len(scan_list)} stocks to scan")
    print(f"Time: {datetime.now().strftime('%I:%M %p MT')}\n")

    plans = []
    for i, (ticker, sector) in enumerate(scan_list, 1):
        print(f"  [{i:2}/{len(scan_list)}] Scanning {ticker}...", end=" ")
        try:
            plan = scan_ticker(ticker, sector)
            if plan:
                plans.append(plan)
                print(f"Score: {plan.score}/100  {plan.action}")
            else:
                print("No setup")
        except Exception as e:
            print(f"Error: {e}")

        # Small delay to avoid Yahoo Finance rate limiting
        time.sleep(0.3)

    # Sort by score descending
    plans.sort(key=lambda p: p.score, reverse=True)

    # Generate report
    report = generate_daily_report(plans, ACCOUNT_SIZE)
    print("\n" + report)

    # Save report to file
    date_str  = datetime.now().strftime("%Y-%m-%d")
    filename  = f"tsx_report_{date_str}.txt"
    with open(filename, "w") as f:
        f.write(report)
    print(f"\nReport saved: {filename}")

    return plans


if __name__ == "__main__":
    custom_tickers = sys.argv[1:] if len(sys.argv) > 1 else None
    run_scanner(custom_tickers)
