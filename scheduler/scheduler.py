"""
scheduler.py — Runs all jobs on schedule.
Uses APScheduler for reliable job management.

Jobs:
  • Every 5 min (market hours): price monitor
  • 4:15 PM MT weekdays: daily scanner
  • 9:30 AM MT weekdays: portfolio update
  • Saturday 8 AM MT: weekly review
"""

import sys
import os
import pytz
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron      import CronTrigger
from apscheduler.triggers.interval  import IntervalTrigger

# Add parent dir to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.config  import Config
from core.monitor import run_price_check
from data.prices  import is_market_open
from alerts.telegram_bot import (
    send_portfolio_update, send_daily_summary, send_startup_message
)
from core.state import state

MT = pytz.timezone("America/Edmonton")


# ── Job Functions ─────────────────────────────────────────────────────────────

def job_price_monitor():
    """Every 5 minutes during market hours."""
    if is_market_open():
        run_price_check()


def job_daily_scanner():
    """
    4:15 PM MT weekdays — after TSX close.
    Runs full scanner, sends results to Telegram,
    auto-populates watchlist with A+ and B setups.
    """
    print(f"\n[scheduler] Running daily scanner at {datetime.now(MT).strftime('%I:%M %p MT')}")

    try:
        # Import scanner components
        import sys, os
        scanner_path = os.path.join(os.path.dirname(__file__), "..", "..", "tsx_scanner")
        sys.path.insert(0, scanner_path)

        from layers.layer1_data    import fetch_data, fetch_weekly, add_all_indicators, passes_liquidity
        from layers.layer2_patterns import detect_all_patterns
        from layers.layer3_context  import detect_stage, detect_dow_phase, detect_sr_zones
        from layers.layer4_scoring  import score_setup
        from layers.layer5_report   import generate_daily_report

        import time
        all_plans = []

        for sector, tickers in Config.WATCHLIST.items():
            for ticker in tickers:
                try:
                    df = fetch_data(ticker, period="1y")
                    if df.empty or not passes_liquidity(df):
                        continue
                    df_weekly = fetch_weekly(ticker)
                    df        = add_all_indicators(df)
                    patterns  = detect_all_patterns(df)
                    trend     = detect_stage(df, df_weekly)
                    phase     = detect_dow_phase(df)
                    zones     = detect_sr_zones(df)
                    plan      = score_setup(ticker, sector, df, patterns,
                                            trend, zones, phase, Config.ACCOUNT_SIZE)
                    if plan:
                        all_plans.append(plan)
                    time.sleep(0.3)
                except Exception as e:
                    print(f"  [{ticker}] Error: {e}")

        all_plans.sort(key=lambda p: p.score, reverse=True)

        enter_plans = [p for p in all_plans if p.action == "ENTER"]
        watch_plans = [p for p in all_plans if p.action == "WATCH"]
        total_cap   = sum(p.capital_deployed for p in enter_plans)

        # Send daily summary to Telegram
        send_daily_summary(enter_plans, watch_plans, total_cap)

        # Auto-add A+ and B setups to watchlist
        from core.state import WatchedStock
        from datetime import datetime as dt

        for plan in enter_plans:
            if plan.grade in ("A+", "B"):
                stock = WatchedStock(
                    ticker=plan.ticker,
                    sector=plan.sector,
                    entry_price=plan.entry_price,
                    stop_price=plan.stop_price,
                    target1=plan.target1_price,
                    target2=plan.target2_price,
                    rrr=plan.rrr,
                    pattern=plan.primary_pattern,
                    stage=plan.stage_label,
                    dow_phase=plan.dow_phase,
                    score=plan.score,
                    grade=plan.grade,
                    shares=plan.shares_at_2pct,
                    capital=plan.capital_deployed,
                    confirmations=plan.checklist_items,
                    warnings=plan.warnings,
                    added_date=dt.now().strftime("%Y-%m-%d"),
                )
                state.add_to_watchlist(stock)
                print(f"  [{plan.ticker}] Added to watchlist — {plan.grade} setup")

        print(f"[scheduler] Daily scan complete — {len(enter_plans)} ENTER, {len(watch_plans)} WATCH")

    except Exception as e:
        print(f"[scheduler] Daily scanner error: {e}")
        from alerts.telegram_bot import send_message
        send_message(f"⚠️ Daily scanner error: {e}")


def job_portfolio_update():
    """9:30 AM MT weekdays — market open check-in."""
    from datetime import datetime
    today = datetime.now(MT).weekday()
    if today >= 5:   # Skip weekends
        return

    positions = state.get_positions()

    # Fetch current prices for positions
    if positions:
        from data.prices import get_current_prices
        tickers = list(positions.keys())
        prices  = get_current_prices(tickers)
        for ticker, data in prices.items():
            state.update_position_price(ticker, data["price"])

    positions = state.get_positions()
    send_portfolio_update(positions)


def job_weekly_review():
    """Saturday 8 AM MT — weekly chart review."""
    from alerts.telegram_bot import send_message
    send_message(
        "📅 <b>Weekly Review Time</b>\n\n"
        "Run the scanner on weekly charts.\n"
        "Update your watchlist for next week.\n\n"
        "Reply /scan to run the full scanner now."
    )


# ── Main Scheduler ────────────────────────────────────────────────────────────

def start():
    """Start the scheduler — runs forever."""
    Config.validate()

    scheduler = BlockingScheduler(timezone=MT)

    # Price monitor — every 5 minutes
    scheduler.add_job(
        job_price_monitor,
        trigger=IntervalTrigger(seconds=Config.PRICE_CHECK_INTERVAL),
        id="price_monitor",
        name="Price Monitor",
        misfire_grace_time=60,
    )

    # Daily scanner — 4:15 PM MT, Mon-Fri
    scheduler.add_job(
        job_daily_scanner,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=16, minute=15,
            timezone=MT
        ),
        id="daily_scanner",
        name="Daily Scanner",
    )

    # Portfolio update — 9:30 AM MT, Mon-Fri
    scheduler.add_job(
        job_portfolio_update,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=9, minute=35,
            timezone=MT
        ),
        id="portfolio_update",
        name="Portfolio Update",
    )

    # Weekly review reminder — Saturday 8 AM MT
    scheduler.add_job(
        job_weekly_review,
        trigger=CronTrigger(
            day_of_week="sat",
            hour=8, minute=0,
            timezone=MT
        ),
        id="weekly_review",
        name="Weekly Review",
    )

    send_startup_message()
    print(f"\n[scheduler] All jobs scheduled. System running.")
    print(f"[scheduler] Price checks every {Config.PRICE_CHECK_INTERVAL}s during market hours")
    print(f"[scheduler] Daily scanner: 4:15 PM MT weekdays")
    print(f"[scheduler] Portfolio update: 9:35 AM MT weekdays\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n[scheduler] Stopped by user.")
        scheduler.shutdown()
