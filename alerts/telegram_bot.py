"""
telegram_bot.py — Sends trade alerts via Telegram.
All message formatting lives here — clear, actionable, no noise.
"""

import requests
from datetime import datetime
from core.config import Config
from core.state  import WatchedStock, OpenPosition


def send_message(text: str) -> bool:
    """Send a plain text message to your Telegram chat."""
    if not Config.TELEGRAM_TOKEN or not Config.TELEGRAM_CHAT_ID:
        print(f"[Telegram] Token or chat ID missing — message not sent:\n{text}")
        return False

    url  = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id":    Config.TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    }
    try:
        r = requests.post(url, data=data, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[Telegram] Send failed: {e}")
        return False


def now_str() -> str:
    from pytz import timezone
    mt = timezone("America/Edmonton")
    return datetime.now(mt).strftime("%A %b %d  |  %I:%M %p MT")


# ── Alert Messages ────────────────────────────────────────────────────────────

def alert_entry_zone(stock: WatchedStock, current_price: float):
    """
    Sent when price reaches the entry zone.
    Full trade plan included — you have everything to act immediately.
    """
    risk  = stock.entry_price - stock.stop_price
    rew1  = stock.target1 - stock.entry_price
    rew2  = stock.target2 - stock.entry_price

    confirmations = "\n".join(f"   + {c}" for c in stock.confirmations[:5])
    warnings_text = ""
    if stock.warnings:
        warnings_text = "\n\n⚠️ <b>WARNINGS</b>\n" + "\n".join(
            f"   ! {w}" for w in stock.warnings[:3])

    msg = f"""
🚨 <b>ENTRY ALERT — {stock.ticker}</b>

Price: <b>${current_price:.2f}</b>  (entry zone: ${stock.entry_price:.2f})
Sector: {stock.sector}  |  Score: {stock.score}/100  |  Grade: {stock.grade}

📊 <b>PATTERN</b>
{stock.pattern}
Stage: {stock.stage}
Dow Phase: {stock.dow_phase}

💰 <b>TRADE PLAN</b>
Entry:    <b>${stock.entry_price:.2f}</b>  (place limit order now)
Stop:     <b>${stock.stop_price:.2f}</b>  (if hit → exit, no hesitation)
Target 1: <b>${stock.target1:.2f}</b>  (exit 50% of position here)
Target 2: <b>${stock.target2:.2f}</b>  (exit remainder here)

Risk/share: ${risk:.2f}  |  R:R: {stock.rrr:.1f}:1

📐 <b>POSITION SIZE</b>  (2% risk / ${Config.ACCOUNT_SIZE:,.0f})
Shares: <b>{stock.shares}</b>  |  Capital: <b>${stock.capital:,.0f}</b>
Max loss if stopped out: <b>${risk * stock.shares:.0f}</b>

✅ <b>CHECKLIST CONFIRMED</b>
{confirmations}{warnings_text}

⏰ {now_str()}
""".strip()

    return send_message(msg)


def alert_stop_approaching(pos: OpenPosition, current_price: float):
    """Sent when price is within 1.5% of stop level."""
    loss = (current_price - pos.entry_price) * pos.shares

    msg = f"""
🛑 <b>STOP APPROACHING — {pos.ticker}</b>

Current price: <b>${current_price:.2f}</b>
Stop level:    <b>${pos.stop_price:.2f}</b>
Distance:      {pos.stop_distance_pct:.1f}% away

Entry was: ${pos.entry_price:.2f}
Current P&L: {'🔴' if loss < 0 else '🟢'} ${loss:.0f}  ({pos.pnl_pct:.1f}%)

<b>ACTION: Watch this closely.</b>
If daily candle closes below ${pos.stop_price:.2f} → EXIT.
Do not move stop lower to avoid the loss.

Pattern was: {pos.pattern}

⏰ {now_str()}
""".strip()

    return send_message(msg)


def alert_stop_hit(pos: OpenPosition, current_price: float):
    """Sent when price crosses below stop level."""
    loss = (current_price - pos.entry_price) * pos.shares

    msg = f"""
🔴 <b>STOP HIT — {pos.ticker}</b>

Price crossed below stop: <b>${pos.stop_price:.2f}</b>
Current price: ${current_price:.2f}

Entry: ${pos.entry_price:.2f}  →  Now: ${current_price:.2f}
Loss: <b>${loss:.0f}</b>  ({pos.pnl_pct:.1f}%)
Shares: {pos.shares}

<b>ACTION: EXIT position now.</b>
Place sell order at market or limit near current price.
This loss is normal — part of the system.
Max planned loss was ${(pos.entry_price - pos.stop_price) * pos.shares:.0f}.

✏️ Record in journal: pattern, entry, exit, lesson.

⏰ {now_str()}
""".strip()

    return send_message(msg)


def alert_target1_hit(pos: OpenPosition, current_price: float):
    """Sent when price reaches Target 1 — exit 50%."""
    gain = (current_price - pos.entry_price) * (pos.shares // 2)
    shares_exit = pos.shares // 2
    shares_hold = pos.shares - shares_exit

    msg = f"""
🎯 <b>TARGET 1 HIT — {pos.ticker}</b>

Price reached: <b>${current_price:.2f}</b>
Target 1 was:  ${pos.target1:.2f}

Entry: ${pos.entry_price:.2f}  |  Gain/share: ${current_price - pos.entry_price:.2f}

<b>ACTION: Sell {shares_exit} shares now</b>
Locked-in gain: <b>+${gain:.0f}</b>

Keep {shares_hold} shares running toward Target 2: ${pos.target2:.2f}
Move stop to breakeven (${pos.entry_price:.2f}) on remaining shares.
This is now a <b>risk-free trade</b> on the remainder.

⏰ {now_str()}
""".strip()

    return send_message(msg)


def alert_target2_hit(pos: OpenPosition, current_price: float):
    """Sent when price reaches Target 2 — full exit."""
    total_gain = (current_price - pos.entry_price) * pos.shares

    msg = f"""
✅ <b>TARGET 2 HIT — {pos.ticker}</b>

Price reached: <b>${current_price:.2f}</b>
Target 2 was:  ${pos.target2:.2f}

Full trade P&L:
  Entry:  ${pos.entry_price:.2f}
  Exit:   ${current_price:.2f}
  Shares: {pos.shares}
  <b>Total gain: +${total_gain:.0f}  ({pos.pnl_pct:.1f}%)</b>

<b>ACTION: Exit remaining position.</b>

✏️ Record full trade in journal.
Well executed — the system worked.

⏰ {now_str()}
""".strip()

    return send_message(msg)


def alert_volume_spike(ticker: str, current_price: float,
                        vol_ratio: float, sector: str):
    """Sent when unusual volume detected on a watchlist stock."""
    msg = f"""
📊 <b>VOLUME SPIKE — {ticker}</b>

Volume: <b>{vol_ratio:.1f}x average</b>  {'(Zanger signal!)' if vol_ratio >= 2.0 else '(O\'Neil signal)'}
Price: ${current_price:.2f}
Sector: {sector}

High volume = institutional activity.
Check chart — pattern may be forming or breaking out.

⏰ {now_str()}
""".strip()

    return send_message(msg)


def alert_breakout_detected(ticker: str, current_price: float,
                              pattern: str, score: int,
                              entry: float, stop: float,
                              target1: float, target2: float,
                              rrr: float, shares: int,
                              capital: float, confirmations: list,
                              warnings: list):
    """
    Sent when daily scanner detects a new high-quality setup.
    This is the main daily signal message.
    """
    risk  = entry - stop
    conf_text = "\n".join(f"   + {c}" for c in confirmations[:5])
    warn_text = ""
    if warnings:
        warn_text = "\n\n⚠️ <b>WARNINGS</b>\n" + "\n".join(
            f"   ! {w}" for w in warnings[:3])

    msg = f"""
🔍 <b>NEW SETUP DETECTED — {ticker}</b>

Score: <b>{score}/100</b>
Pattern: <b>{pattern}</b>
Price: ${current_price:.2f}

💰 <b>TRADE PLAN</b>
Entry:    <b>${entry:.2f}</b>
Stop:     <b>${stop:.2f}</b>  (${risk:.2f}/share risk)
Target 1: <b>${target1:.2f}</b>  (exit 50%)
Target 2: <b>${target2:.2f}</b>  (exit rest)
R:R: <b>{rrr:.1f}:1</b>

📐 <b>POSITION SIZE</b>
Shares: {shares}  |  Capital: ${capital:,.0f}

✅ <b>CONFIRMED</b>
{conf_text}{warn_text}

Add to watchlist? Reply: <b>/watch {ticker}</b>

⏰ {now_str()}
""".strip()

    return send_message(msg)


# ── Daily Report Messages ─────────────────────────────────────────────────────

def send_daily_summary(enter_plans: list, watch_plans: list,
                        total_capital: float):
    """Morning summary of today's opportunities."""
    if not enter_plans and not watch_plans:
        msg = f"""
📋 <b>DAILY SCAN — No setups today</b>

No stocks meet all checklist criteria today.
Patience is a position.

Watchlist is being monitored.
Next scan: tomorrow after market close.

⏰ {now_str()}
""".strip()
        return send_message(msg)

    enter_lines = ""
    for p in enter_plans[:4]:
        enter_lines += (
            f"\n  ✅ <b>{p.ticker}</b>  Score:{p.score}  "
            f"Entry:${p.entry_price:.2f}  "
            f"Stop:${p.stop_price:.2f}  "
            f"R:R:{p.rrr:.1f}"
        )

    watch_lines = ""
    for p in watch_plans[:3]:
        watch_lines += f"\n  ⏳ <b>{p.ticker}</b>  {p.primary_pattern}"

    msg = f"""
📋 <b>DAILY SCAN COMPLETE</b>

<b>ENTER NOW ({len(enter_plans)} setup{'s' if len(enter_plans) != 1 else ''}):</b>
{enter_lines if enter_lines else '  None'}

<b>WATCHING ({len(watch_plans)} developing):</b>
{watch_lines if watch_lines else '  None'}

Capital to deploy: ${total_capital:,.0f} of ${Config.ACCOUNT_SIZE:,.0f}

Price alerts are active.
You will be notified when entry zones are hit.

⏰ {now_str()}
""".strip()

    return send_message(msg)


def send_portfolio_update(positions: dict):
    """Sent at market open showing all open positions."""
    if not positions:
        return send_message(
            f"📊 <b>Portfolio Update</b>\n\nNo open positions.\n\n⏰ {now_str()}"
        )

    lines = ""
    total_pnl = 0
    for ticker, pos in positions.items():
        pnl   = pos.unrealized_pnl
        emoji = "🟢" if pnl >= 0 else "🔴"
        total_pnl += pnl
        lines += (
            f"\n{emoji} <b>{ticker}</b>  ${pos.current_price:.2f}  "
            f"P&L: ${pnl:.0f} ({pos.pnl_pct:.1f}%)"
            f"\n   Stop: ${pos.stop_price:.2f} ({pos.stop_distance_pct:.1f}% away)"
            f"  T1: ${pos.target1:.2f} ({pos.target1_distance_pct:.1f}% away)\n"
        )

    total_emoji = "🟢" if total_pnl >= 0 else "🔴"
    msg = f"""
📊 <b>PORTFOLIO UPDATE</b>
{lines}
{total_emoji} <b>Total unrealized P&L: ${total_pnl:.0f}</b>

⏰ {now_str()}
""".strip()

    return send_message(msg)


def send_startup_message():
    """Sent when the system starts up."""
    msg = f"""
🚀 <b>TSX Scanner Online</b>

System is running and monitoring your watchlist.

Scheduled jobs:
  • Every 5 min (7:00 AM – 2:30 PM MT): price checks
  • 7:00 AM MT daily: pre-market briefing
  • 7:35 AM MT daily: portfolio update
  • 4:15 PM MT daily: full scanner run
  • Saturday 8 AM MT: weekly review

Commands:
  /watchlist — see current watchlist
  /positions — see open trades
  /scan — run scanner now
  /help — all commands

⏰ {now_str()}
""".strip()
    return send_message(msg)


def send_premarket_briefing(watched: dict, prices: dict):
    """7:00 AM MT — shows which watchlist stocks are near entry zones before open."""
    if not watched:
        return send_message(
            f"🌅 <b>Pre-Market Briefing</b>\n\nWatchlist is empty.\n\n⏰ {now_str()}"
        )

    near_entry = []
    lines = []

    for ticker, stock in watched.items():
        price_data = prices.get(ticker)
        if not price_data:
            lines.append(f"  ❓ <b>{ticker}</b>  no data  (entry: ${stock.entry_price:.2f})")
            continue

        curr      = price_data["price"]
        entry     = stock.entry_price
        dist_pct  = (curr - entry) / entry * 100

        if abs(dist_pct) <= 1.0:
            zone = "🚨 AT ENTRY"
            near_entry.append(ticker)
        elif -3.0 <= dist_pct <= 3.0:
            zone = "🟡 NEAR"
            near_entry.append(ticker)
        elif dist_pct < -3.0:
            zone = "⬇️  below"
        else:
            zone = "⬆️  above"

        lines.append(
            f"  {zone}  <b>{ticker}</b>  ${curr:.2f}"
            f"  (entry ${entry:.2f} | {dist_pct:+.1f}%)"
        )

    body = "\n".join(lines) if lines else "  No price data."
    alert = (
        f"\n⚡ <b>Near entry:</b> {', '.join(near_entry)}"
        if near_entry else "\n  No stocks near entry zones."
    )

    msg = f"""
🌅 <b>PRE-MARKET BRIEFING</b>  —  {len(watched)} stocks watched

{body}
{alert}

TSX opens 7:30 AM MT — 30 min to open.
⏰ {now_str()}
""".strip()

    return send_message(msg)


def send_watchlist_summary(watched: dict):
    """Show current watchlist with all levels."""
    if not watched:
        return send_message(
            "📋 <b>Watchlist</b>\n\nNo stocks on watchlist.\n\n"
            "Run /scan to find setups."
        )

    lines = ""
    for ticker, stock in watched.items():
        lines += (
            f"\n📌 <b>{ticker}</b>  ${stock.entry_price:.2f}"
            f"\n   Stop: ${stock.stop_price:.2f}  "
            f"T1: ${stock.target1:.2f}  T2: ${stock.target2:.2f}"
            f"\n   Pattern: {stock.pattern}  |  R:R: {stock.rrr:.1f}\n"
        )

    msg = f"📋 <b>WATCHLIST ({len(watched)} stocks)</b>\n{lines}\n⏰ {now_str()}"
    return send_message(msg)
