"""
monitor.py — Core price monitoring engine.
Runs every 5 minutes during TSX market hours.
Checks entry zones, stop levels, targets, volume spikes.
"""

from datetime import datetime
from data.prices  import get_current_prices, price_near_level, price_crossed_level
from core.state   import state, OpenPosition
from core.config  import Config
from alerts.telegram_bot import (
    alert_entry_zone, alert_stop_approaching, alert_stop_hit,
    alert_target1_hit, alert_target2_hit, alert_volume_spike
)


# Track previous prices between checks
_prev_prices: dict[str, float] = {}


def run_price_check():
    """
    Main monitoring function — called every 5 minutes.
    Checks all watchlist and position tickers.
    """
    tickers = state.get_all_monitored_tickers()
    if not tickers:
        return

    print(f"[monitor] Checking {len(tickers)} tickers at "
          f"{datetime.now().strftime('%H:%M')}")

    prices = get_current_prices(tickers)
    if not prices:
        print("[monitor] No price data received")
        return

    # ── Check watchlist entries ───────────────────────────
    _check_entries(prices)

    # ── Check open position stops and targets ─────────────
    _check_positions(prices)

    # ── Check for unusual volume on all monitored stocks ──
    _check_volume_spikes(prices)

    # Update previous prices cache
    for ticker, data in prices.items():
        _prev_prices[ticker] = data["price"]


def _check_entries(prices: dict):
    """Check if any watchlist stock has reached its entry zone."""
    watched = state.get_watchlist()

    for ticker, stock in watched.items():
        if ticker not in prices:
            continue

        price_data  = prices[ticker]
        curr_price  = price_data["price"]
        entry_level = stock.entry_price

        # Alert when price is within 1% of entry level
        if price_near_level(curr_price, entry_level, tolerance_pct=1.0):
            if not state.was_fired_today(ticker, "entry"):
                print(f"[monitor] ENTRY ZONE: {ticker} @ ${curr_price}")
                alert_entry_zone(stock, curr_price)
                state.mark_alert_fired(ticker, "entry")

        # Also alert if price broke above entry (in case you missed it)
        prev = _prev_prices.get(ticker, 0)
        if prev and price_crossed_level(curr_price, prev, entry_level, "above"):
            if not state.was_fired_today(ticker, "entry_cross"):
                print(f"[monitor] ENTRY CROSSED: {ticker} @ ${curr_price}")
                alert_entry_zone(stock, curr_price)
                state.mark_alert_fired(ticker, "entry_cross")


def _check_positions(prices: dict):
    """Check stop and target levels for all open positions."""
    positions = state.get_positions()

    for ticker, pos in positions.items():
        if ticker not in prices:
            continue

        price_data = prices[ticker]
        curr_price = price_data["price"]
        prev_price = _prev_prices.get(ticker, curr_price)

        # Update live P&L
        state.update_position_price(ticker, curr_price)

        # ── Stop Loss Checks ──────────────────────────────
        # Alert when approaching stop (within 1.5%)
        if price_near_level(curr_price, pos.stop_price, tolerance_pct=1.5):
            if not state.was_fired_today(ticker, "stop_approach"):
                print(f"[monitor] STOP APPROACHING: {ticker} @ ${curr_price}")
                pos.current_price = curr_price
                pos.pnl_pct = (curr_price - pos.entry_price) / pos.entry_price * 100
                pos.stop_distance_pct = (curr_price - pos.stop_price) / curr_price * 100
                alert_stop_approaching(pos, curr_price)
                state.mark_alert_fired(ticker, "stop_approach")

        # Alert when stop is crossed
        if price_crossed_level(curr_price, prev_price, pos.stop_price, "below"):
            if not state.was_fired_today(ticker, "stop_hit"):
                print(f"[monitor] STOP HIT: {ticker} @ ${curr_price}")
                pos.current_price = curr_price
                pos.pnl_pct = (curr_price - pos.entry_price) / pos.entry_price * 100
                alert_stop_hit(pos, curr_price)
                state.mark_alert_fired(ticker, "stop_hit")

        # ── Target Checks ─────────────────────────────────
        # Target 1 hit
        if (not pos.partial_exited
                and price_crossed_level(curr_price, prev_price, pos.target1, "above")):
            if not state.was_fired_today(ticker, "target1"):
                print(f"[monitor] TARGET 1 HIT: {ticker} @ ${curr_price}")
                pos.current_price = curr_price
                pos.pnl_pct = (curr_price - pos.entry_price) / pos.entry_price * 100
                alert_target1_hit(pos, curr_price)
                state.mark_alert_fired(ticker, "target1")
                # Mark partial exit done
                p = state._positions.get(ticker, {})
                p["partial_exited"] = True
                state._positions[ticker] = p
                state.save_all()

        # Target 2 hit
        if price_crossed_level(curr_price, prev_price, pos.target2, "above"):
            if not state.was_fired_today(ticker, "target2"):
                print(f"[monitor] TARGET 2 HIT: {ticker} @ ${curr_price}")
                pos.current_price = curr_price
                pos.pnl_pct = (curr_price - pos.entry_price) / pos.entry_price * 100
                alert_target2_hit(pos, curr_price)
                state.mark_alert_fired(ticker, "target2")


def _check_volume_spikes(prices: dict):
    """Alert on unusual volume — potential institutional activity."""
    sector_map = {}
    for sector, tickers in Config.WATCHLIST.items():
        for t in tickers:
            sector_map[t] = sector

    for ticker, data in prices.items():
        vol_ratio = data.get("vol_ratio", 1.0)

        # Zanger threshold: 2x average = institutional signal
        # Only alert once per day per stock
        if vol_ratio >= 2.0:
            if not state.was_fired_today(ticker, "volume_spike"):
                sector = sector_map.get(ticker, "Unknown")
                print(f"[monitor] VOLUME SPIKE: {ticker} {vol_ratio:.1f}x")
                alert_volume_spike(ticker, data["price"], vol_ratio, sector)
                state.mark_alert_fired(ticker, "volume_spike")
