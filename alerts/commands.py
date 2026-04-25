"""
commands.py — Handle commands you send TO the bot.
You control the system by messaging your bot on Telegram.

Available commands:
  /watchlist     — show current watchlist
  /positions     — show open trades
  /add TICKER entry stop t1 t2 — manually add to watchlist
  /entered TICKER — mark as entered (moves to positions)
  /exit TICKER   — close a position
  /scan          — trigger scanner now
  /help          — show all commands
"""

import sys
import os
import requests
import time
import datetime as dt_module
from core.config import Config
from core.state  import state, WatchedStock, OpenPosition
from alerts.telegram_bot import (
    send_message, send_watchlist_summary, send_portfolio_update
)


def get_updates(offset: int = 0) -> list:
    """Poll Telegram for new messages."""
    url    = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": 30, "allowed_updates": ["message"]}
    try:
        r = requests.get(url, params=params, timeout=35)
        if r.status_code == 200:
            return r.json().get("result", [])
    except Exception:
        pass
    return []


def handle_command(text: str):
    """Process a command sent to the bot."""
    text   = text.strip()
    parts  = text.split()
    cmd    = parts[0].lower() if parts else ""

    # ── /help ─────────────────────────────────────────────
    if cmd == "/help":
        send_message(
            "📖 <b>TSX Scanner Commands</b>\n\n"
            "/watchlist — current watchlist with trade plans\n"
            "/positions — open trades with live P&L\n"
            "/scan — run scanner now (takes ~2 mins)\n\n"
            "<b>Manual entries:</b>\n"
            "/add TICKER entry stop t1 t2\n"
            "  Example: /add SU.TO 88.00 83.00 92.00 96.00\n\n"
            "/entered TICKER price — record entry\n"
            "  Example: /entered SU.TO 88.12\n\n"
            "/exit TICKER — close a position\n"
            "  Example: /exit SU.TO\n\n"
            "/remove TICKER — remove from watchlist\n"
            "/status — system status"
        )

    # ── /watchlist ────────────────────────────────────────
    elif cmd == "/watchlist":
        watched = state.get_watchlist()
        send_watchlist_summary(watched)

    # ── /positions ────────────────────────────────────────
    elif cmd == "/positions":
        from data.prices import get_current_prices
        positions = state.get_positions()
        if positions:
            tickers = list(positions.keys())
            prices  = get_current_prices(tickers)
            for ticker, data in prices.items():
                state.update_position_price(ticker, data["price"])
            positions = state.get_positions()
        send_portfolio_update(positions)

    # ── /scan ─────────────────────────────────────────────
    elif cmd == "/scan":
        send_message("🔍 Running scanner... This takes ~2 minutes.")
        try:
            from scheduler.scheduler import job_daily_scanner
            job_daily_scanner()
        except Exception as e:
            send_message(f"Scanner error: {e}")

    # ── /add TICKER entry stop t1 t2 ─────────────────────
    elif cmd == "/add" and len(parts) >= 6:
        try:
            ticker = parts[1].upper()
            if not ticker.endswith(".TO"):
                ticker += ".TO"
            entry  = float(parts[2])
            stop   = float(parts[3])
            t1     = float(parts[4])
            t2     = float(parts[5])
            rrr    = round((t1 - entry) / (entry - stop), 2) if entry > stop else 0

            if rrr < Config.MIN_RRR:
                send_message(
                    f"⚠️ R:R {rrr:.1f} is below minimum {Config.MIN_RRR}.\n"
                    f"Adjust your levels or override with /addforce"
                )
                return

            from data.prices import get_single_price
            price_data = get_single_price(ticker)
            current    = price_data.get("price", entry)

            # Estimate shares at 2% risk
            risk_amt  = Config.ACCOUNT_SIZE * Config.RISK_PCT
            risk_share = entry - stop
            shares    = int(risk_amt / risk_share) if risk_share > 0 else 0
            capital   = round(shares * entry, 2)

            # Find sector
            sector = "Custom"
            for sec, tickers_list in Config.WATCHLIST.items():
                if ticker in tickers_list:
                    sector = sec
                    break

            stock = WatchedStock(
                ticker=ticker, sector=sector,
                entry_price=entry, stop_price=stop,
                target1=t1, target2=t2, rrr=rrr,
                pattern="Manual entry",
                stage="Manual", dow_phase="Manual",
                score=0, grade="Manual",
                shares=shares, capital=capital,
                confirmations=["Manually added"],
                warnings=[],
                added_date=dt_module.datetime.now().strftime("%Y-%m-%d"),
            )
            state.add_to_watchlist(stock)
            send_message(
                f"✅ <b>{ticker} added to watchlist</b>\n\n"
                f"Entry: ${entry:.2f}  Stop: ${stop:.2f}\n"
                f"T1: ${t1:.2f}  T2: ${t2:.2f}\n"
                f"R:R: {rrr:.1f}  Shares: {shares}  Capital: ${capital:,.0f}\n\n"
                f"You'll be alerted when entry zone is hit."
            )
        except (ValueError, IndexError):
            send_message(
                "❌ Format: /add TICKER entry stop target1 target2\n"
                "Example: /add SU.TO 88.00 83.00 92.00 96.00"
            )

    # ── /entered TICKER price ─────────────────────────────
    elif cmd == "/entered" and len(parts) >= 3:
        try:
            ticker = parts[1].upper()
            if not ticker.endswith(".TO"):
                ticker += ".TO"
            entry_price = float(parts[2])

            # Find in watchlist
            watched = state.get_watchlist()
            if ticker not in watched:
                send_message(f"❌ {ticker} not in watchlist. Use /add first.")
                return

            stock = watched[ticker]
            pos   = OpenPosition(
                ticker=ticker,
                sector=stock.sector,
                entry_price=entry_price,
                entry_date=dt_module.datetime.now().strftime("%Y-%m-%d %H:%M"),
                shares=stock.shares,
                stop_price=stock.stop_price,
                target1=stock.target1,
                target2=stock.target2,
                pattern=stock.pattern,
                current_price=entry_price,
            )
            state.open_position(pos)
            send_message(
                f"📈 <b>Position opened — {ticker}</b>\n\n"
                f"Entry: ${entry_price:.2f}  ({stock.shares} shares)\n"
                f"Stop: ${stock.stop_price:.2f}\n"
                f"Target 1: ${stock.target1:.2f}\n"
                f"Target 2: ${stock.target2:.2f}\n\n"
                f"Stop and target alerts are now active.\n"
                f"Do nothing until stop or target is hit."
            )
        except (ValueError, IndexError):
            send_message(
                "❌ Format: /entered TICKER price\n"
                "Example: /entered SU.TO 88.12"
            )

    # ── /exit TICKER ──────────────────────────────────────
    elif cmd == "/exit" and len(parts) >= 2:
        ticker = parts[1].upper()
        if not ticker.endswith(".TO"):
            ticker += ".TO"
        positions = state.get_positions()
        if ticker not in positions:
            send_message(f"❌ {ticker} not in open positions.")
            return
        pos = positions[ticker]
        from data.prices import get_single_price
        price_data = get_current_prices_single(ticker)
        exit_price = price_data if price_data else pos.entry_price
        pnl = (exit_price - pos.entry_price) * pos.shares
        state.close_position(ticker)
        send_message(
            f"🔒 <b>Position closed — {ticker}</b>\n\n"
            f"Entry: ${pos.entry_price:.2f}  Exit: ${exit_price:.2f}\n"
            f"Shares: {pos.shares}\n"
            f"P&L: {'🟢' if pnl >= 0 else '🔴'} ${pnl:.0f}\n\n"
            f"Record in trade journal."
        )

    # ── /remove TICKER ────────────────────────────────────
    elif cmd == "/remove" and len(parts) >= 2:
        ticker = parts[1].upper()
        if not ticker.endswith(".TO"):
            ticker += ".TO"
        state.remove_from_watchlist(ticker)
        send_message(f"✅ {ticker} removed from watchlist.")

    # ── /status ───────────────────────────────────────────
    elif cmd == "/status":
        watched   = len(state.get_watchlist())
        positions = len(state.get_positions())
        alerts    = len(state.get_active_alerts())
        from datetime import datetime as _dt
        from pytz import timezone
        mt = timezone("America/Edmonton")
        now = _dt.now(mt).strftime("%I:%M %p MT")
        send_message(
            f"⚙️ <b>System Status</b>\n\n"
            f"Watchlist: {watched} stocks\n"
            f"Open positions: {positions}\n"
            f"Active alerts: {alerts}\n"
            f"Time: {now}\n\n"
            f"System is running normally."
        )

    else:
        if text.startswith("/"):
            send_message("❓ Unknown command. Send /help for all commands.")


def get_current_prices_single(ticker: str) -> float:
    """Quick price fetch for exit command."""
    from data.prices import get_single_price
    data = get_single_price(ticker)
    return data.get("price", 0)


def run_command_listener():
    """
    Long-poll Telegram for commands.
    Runs in a separate thread alongside the scheduler.
    """
    print("[commands] Telegram command listener started")
    offset = 0

    while True:
        try:
            updates = get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                msg    = update.get("message", {})
                text   = msg.get("text", "")
                chat   = str(msg.get("chat", {}).get("id", ""))

                # Only accept commands from your chat ID
                if chat != str(Config.TELEGRAM_CHAT_ID):
                    continue

                if text:
                    print(f"[commands] Received: {text}")
                    handle_command(text)

        except Exception as e:
            print(f"[commands] Error: {e}")
            time.sleep(5)
