"""
main.py — Entry point for the TSX Real-Time System.
Starts three concurrent processes:
  1. Scheduler (price checks + daily scanner)
  2. Telegram command listener (responds to your messages)

Usage:
  python main.py
"""

import sys
import os
import threading

# Make sure all imports work
sys.path.insert(0, os.path.dirname(__file__))

from core.config import Config


def main():
    print("=" * 50)
    print("  TSX Real-Time Trading System")
    print("=" * 50)

    # Validate config
    try:
        Config.validate()
        print("  Config: OK")
    except ValueError as e:
        print(f"\n  ERROR: {e}")
        print("\n  Fix: Copy .env.example to .env and fill in your values")
        sys.exit(1)

    print(f"  Account: ${Config.ACCOUNT_SIZE:,.0f}")
    print(f"  Risk/trade: {Config.RISK_PCT*100:.0f}%  (${Config.ACCOUNT_SIZE * Config.RISK_PCT:.0f} max loss)")
    print(f"  Watchlist: {len(Config.ALL_TICKERS)} stocks")
    print(f"  Price checks: every {Config.PRICE_CHECK_INTERVAL}s during market hours")
    print("=" * 50 + "\n")

    # Start command listener in background thread
    from alerts.commands import run_command_listener
    cmd_thread = threading.Thread(
        target=run_command_listener,
        daemon=True,
        name="CommandListener"
    )
    cmd_thread.start()
    print("[main] Command listener started in background")

    # Start scheduler (blocking — runs forever)
    from scheduler.scheduler import start
    start()


if __name__ == "__main__":
    main()
