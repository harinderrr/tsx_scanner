"""
prices.py — Fetches current prices during market hours.
Uses yfinance for free near-real-time quotes (15-min delay).
For swing trading this is perfectly adequate.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz


MT = pytz.timezone("America/Edmonton")


def is_market_open() -> bool:
    """Check if TSX is currently open (7:30 AM - 2:00 PM MT, weekdays)."""
    now = datetime.now(MT)
    if now.weekday() >= 5:   # Saturday=5, Sunday=6
        return False
    market_open  = now.replace(hour=7,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=14, minute=0,  second=0, microsecond=0)
    return market_open <= now <= market_close


def is_monitoring_window() -> bool:
    """Check if we're in the price-monitoring window (7:00 AM - 2:30 PM MT, weekdays)."""
    now = datetime.now(MT)
    if now.weekday() >= 5:
        return False
    window_open  = now.replace(hour=7,  minute=0,  second=0, microsecond=0)
    window_close = now.replace(hour=14, minute=30, second=0, microsecond=0)
    return window_open <= now <= window_close


def get_current_prices(tickers: list[str]) -> dict[str, dict]:
    """
    Fetch current price + volume for a list of tickers.
    Returns dict: {ticker: {price, volume, vol_avg, change_pct, high, low}}
    """
    if not tickers:
        return {}

    results = {}

    try:
        # Batch download for efficiency
        data = yf.download(
            tickers,
            period="5d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            group_by="ticker"
        )

        for ticker in tickers:
            try:
                if len(tickers) == 1:
                    df = data
                else:
                    df = data[ticker] if ticker in data.columns.get_level_values(0) else pd.DataFrame()

                if df.empty or len(df) < 2:
                    continue

                # Flatten columns if needed
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                df = df.dropna()
                if df.empty:
                    continue

                latest   = df.iloc[-1]
                previous = df.iloc[-2]

                current_price = float(latest.get("Close", latest.get("close", 0)))
                prev_close    = float(previous.get("Close", previous.get("close", 0)))
                current_vol   = float(latest.get("Volume", latest.get("volume", 0)))
                avg_vol       = float(df["Volume"].tail(10).mean()
                                      if "Volume" in df.columns
                                      else df["volume"].tail(10).mean())

                change_pct = ((current_price - prev_close) / prev_close * 100
                              if prev_close > 0 else 0)
                vol_ratio  = current_vol / avg_vol if avg_vol > 0 else 1.0

                results[ticker] = {
                    "price":      round(current_price, 2),
                    "prev_close": round(prev_close, 2),
                    "change_pct": round(change_pct, 2),
                    "volume":     int(current_vol),
                    "vol_avg":    int(avg_vol),
                    "vol_ratio":  round(vol_ratio, 2),
                    "high":       round(float(latest.get("High", latest.get("high", 0))), 2),
                    "low":        round(float(latest.get("Low",  latest.get("low",  0))), 2),
                }

            except Exception:
                continue

    except Exception as e:
        print(f"[prices] Batch fetch error: {e}")

    return results


def get_single_price(ticker: str) -> dict:
    """Get price data for a single ticker."""
    result = get_current_prices([ticker])
    return result.get(ticker, {})


def price_near_level(current: float, level: float,
                      tolerance_pct: float = 1.0) -> bool:
    """Check if current price is within tolerance% of a target level."""
    if level <= 0:
        return False
    return abs(current - level) / level * 100 <= tolerance_pct


def price_crossed_level(current: float, prev: float,
                         level: float, direction: str = "above") -> bool:
    """
    Check if price crossed a level between previous and current check.
    direction: 'above' (price moved up through level)
               'below' (price moved down through level)
    """
    if direction == "above":
        return prev < level <= current
    else:
        return prev > level >= current
