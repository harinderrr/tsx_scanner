"""
config.py — Loads all settings from .env file
Never hardcode credentials in code.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Telegram
    TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # Account
    ACCOUNT_SIZE = float(os.getenv("ACCOUNT_SIZE", 1490))
    RISK_PCT     = float(os.getenv("RISK_PCT", 0.02))

    # Scanner
    MIN_VOLUME = int(os.getenv("MIN_VOLUME", 500_000))
    MIN_RRR    = float(os.getenv("MIN_RRR", 1.5))

    # Price monitor interval (seconds)
    PRICE_CHECK_INTERVAL = int(os.getenv("PRICE_CHECK_INTERVAL", 300))

    # TSX market hours (Mountain Time)
    MARKET_OPEN_HOUR  = 9
    MARKET_OPEN_MIN   = 30
    MARKET_CLOSE_HOUR = 16
    MARKET_CLOSE_MIN  = 0
    MARKET_TIMEZONE   = "America/Edmonton"

    # Watchlist
    WATCHLIST = {
        "Energy":      ["SU.TO", "CNQ.TO", "TRP.TO", "ENB.TO", "IMO.TO"],
        "Miners":      ["AEM.TO", "WPM.TO", "ABX.TO", "K.TO", "CCO.TO"],
        "Financials":  ["RY.TO", "TD.TO", "BNS.TO", "BMO.TO", "CM.TO", "MFC.TO"],
        "Industrials": ["CNR.TO", "CP.TO", "CLS.TO"],
        "Consumer":    ["L.TO", "ATD.TO"],
    }

    ALL_TICKERS = [t for s in WATCHLIST.values() for t in s]

    @classmethod
    def validate(cls):
        """Check critical config is present before starting."""
        errors = []
        if not cls.TELEGRAM_TOKEN or cls.TELEGRAM_TOKEN == "your_new_token_here":
            errors.append("TELEGRAM_TOKEN not set in .env file")
        if not cls.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID not set in .env file")
        if errors:
            raise ValueError(
                "Missing configuration:\n" + "\n".join(f"  - {e}" for e in errors)
            )
        return True
