"""
state.py — Manages watchlist, open positions, and alert levels.
Everything persists to JSON files so state survives restarts.
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional


STATE_DIR   = "state"
WATCH_FILE  = os.path.join(STATE_DIR, "watchlist.json")
POS_FILE    = os.path.join(STATE_DIR, "positions.json")
ALERTS_FILE = os.path.join(STATE_DIR, "alerts.json")
FIRED_FILE  = os.path.join(STATE_DIR, "fired_alerts.json")

os.makedirs(STATE_DIR, exist_ok=True)


# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class WatchedStock:
    """A stock being monitored for entry."""
    ticker:      str
    sector:      str
    entry_price: float        # Limit order entry level
    stop_price:  float        # Stop loss level
    target1:     float        # First target (partial exit)
    target2:     float        # Second target (full exit)
    rrr:         float        # Reward/risk ratio
    pattern:     str          # Pattern that triggered the watch
    stage:       str          # Weinstein stage
    dow_phase:   str          # Dow Theory phase
    score:       int          # Scanner score 0-100
    grade:       str          # A+, B, C
    shares:      int          # Shares at 2% risk
    capital:     float        # Capital to deploy
    confirmations: list       # What the checklist confirmed
    warnings:    list         # What to watch for
    added_date:  str          # When added to watchlist
    notes:       str = ""     # Manual notes


@dataclass
class OpenPosition:
    """A live trade currently open."""
    ticker:       str
    sector:       str
    entry_price:  float
    entry_date:   str
    shares:       int
    stop_price:   float
    target1:      float
    target2:      float
    pattern:      str
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    pnl_pct:      float = 0.0
    stop_distance_pct: float = 0.0
    target1_distance_pct: float = 0.0
    trailing_stop: Optional[float] = None
    partial_exited: bool = False
    notes:        str = ""


@dataclass
class PriceAlert:
    """A specific price alert (entry hit, stop hit, etc.)."""
    ticker:      str
    alert_type:  str    # 'entry', 'stop', 'target1', 'target2', 'volume_spike'
    price_level: float
    description: str
    active:      bool = True


# ── State Manager ─────────────────────────────────────────────────────────────

class StateManager:

    def __init__(self):
        self._watched   = self._load(WATCH_FILE, {})
        self._positions = self._load(POS_FILE, {})
        self._alerts    = self._load(ALERTS_FILE, {})
        self._fired     = self._load(FIRED_FILE, {})

    # ── Persistence ───────────────────────────────────────

    def _load(self, path: str, default) -> dict:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return default

    def _save(self, path: str, data: dict):
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def save_all(self):
        self._save(WATCH_FILE,  self._watched)
        self._save(POS_FILE,    self._positions)
        self._save(ALERTS_FILE, self._alerts)
        self._save(FIRED_FILE,  self._fired)

    # ── Watchlist Management ──────────────────────────────

    def add_to_watchlist(self, stock: WatchedStock):
        """Add a stock to the watchlist with full trade plan."""
        self._watched[stock.ticker] = asdict(stock)
        # Auto-create entry alert
        self.add_alert(PriceAlert(
            ticker=stock.ticker,
            alert_type="entry",
            price_level=stock.entry_price,
            description=f"Entry zone reached for {stock.ticker}"
        ))
        self.save_all()

    def remove_from_watchlist(self, ticker: str):
        self._watched.pop(ticker, None)
        # Remove related alerts
        self._alerts = {k: v for k, v in self._alerts.items()
                        if not k.startswith(ticker)}
        self.save_all()

    def get_watchlist(self) -> dict[str, WatchedStock]:
        return {k: WatchedStock(**v) for k, v in self._watched.items()}

    def get_watched_tickers(self) -> list[str]:
        return list(self._watched.keys())

    # ── Position Management ───────────────────────────────

    def open_position(self, pos: OpenPosition):
        """Record a new open trade."""
        self._positions[pos.ticker] = asdict(pos)
        # Auto-create stop and target alerts
        self.add_alert(PriceAlert(
            ticker=pos.ticker,
            alert_type="stop",
            price_level=pos.stop_price,
            description=f"STOP approaching for {pos.ticker} — review now"
        ))
        self.add_alert(PriceAlert(
            ticker=pos.ticker,
            alert_type="target1",
            price_level=pos.target1,
            description=f"Target 1 hit for {pos.ticker} — exit 50%"
        ))
        self.add_alert(PriceAlert(
            ticker=pos.ticker,
            alert_type="target2",
            price_level=pos.target2,
            description=f"Target 2 hit for {pos.ticker} — exit remainder"
        ))
        # Remove from watchlist
        self._watched.pop(pos.ticker, None)
        self.save_all()

    def update_position_price(self, ticker: str, current_price: float):
        """Update live price and recalculate P&L."""
        if ticker not in self._positions:
            return
        pos = self._positions[ticker]
        entry = pos["entry_price"]
        shares = pos["shares"]
        stop  = pos["stop_price"]
        t1    = pos["target1"]

        unrealized = (current_price - entry) * shares
        pnl_pct    = (current_price - entry) / entry * 100
        stop_dist  = (current_price - stop) / current_price * 100
        t1_dist    = (t1 - current_price) / current_price * 100

        pos["current_price"]          = current_price
        pos["unrealized_pnl"]         = round(unrealized, 2)
        pos["pnl_pct"]                = round(pnl_pct, 2)
        pos["stop_distance_pct"]      = round(stop_dist, 2)
        pos["target1_distance_pct"]   = round(t1_dist, 2)
        self._positions[ticker] = pos
        self.save_all()

    def close_position(self, ticker: str):
        self._positions.pop(ticker, None)
        self._alerts = {k: v for k, v in self._alerts.items()
                        if not k.startswith(ticker)}
        self.save_all()

    def get_positions(self) -> dict[str, OpenPosition]:
        return {k: OpenPosition(**v) for k, v in self._positions.items()}

    def get_position_tickers(self) -> list[str]:
        return list(self._positions.keys())

    # ── Alert Management ──────────────────────────────────

    def add_alert(self, alert: PriceAlert):
        key = f"{alert.ticker}_{alert.alert_type}"
        self._alerts[key] = asdict(alert)
        self.save_all()

    def get_active_alerts(self) -> list[PriceAlert]:
        return [PriceAlert(**v) for v in self._alerts.values()
                if v.get("active", True)]

    def mark_alert_fired(self, ticker: str, alert_type: str):
        """Prevent duplicate alerts for same event."""
        key = f"{ticker}_{alert_type}"
        fire_key = f"{key}_{datetime.now().strftime('%Y%m%d')}"
        self._fired[fire_key] = datetime.now().isoformat()
        # Deactivate the alert
        if key in self._alerts:
            self._alerts[key]["active"] = False
        self.save_all()

    def was_fired_today(self, ticker: str, alert_type: str) -> bool:
        key = f"{ticker}_{alert_type}_{datetime.now().strftime('%Y%m%d')}"
        return key in self._fired

    def get_all_monitored_tickers(self) -> list[str]:
        """All tickers we need price data for."""
        tickers = set()
        tickers.update(self.get_watched_tickers())
        tickers.update(self.get_position_tickers())
        return list(tickers)


# Singleton instance
state = StateManager()
