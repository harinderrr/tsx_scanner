# TSX Real-Time Trading System — Setup Guide

## What this system does

- Scans your TSX watchlist every day at 4:15 PM MT after market close
- Monitors prices every 5 minutes during market hours
- Sends Telegram alerts when entry zones, stops, or targets are hit
- You control it by messaging your Telegram bot

---

## Step 1 — Install Python (if not already installed)

Download from python.org — version 3.10 or higher.

---

## Step 2 — Set up your .env file

1. Copy `.env.example` to `.env` (same folder)
2. Open `.env` in Notepad
3. Replace `your_new_token_here` with your Telegram bot token
4. Save the file

Your .env should look like:
```
TELEGRAM_TOKEN=8567518723:AAH...your_actual_token...
TELEGRAM_CHAT_ID=6373753187
ACCOUNT_SIZE=1490
RISK_PCT=0.02
```

NEVER share your .env file or commit it to GitHub.

---

## Step 3 — Install dependencies

Open Command Prompt in the tsx_realtime folder and run:

```
pip install -r requirements.txt
```

---

## Step 4 — Test locally first

```
python main.py
```

You should receive a Telegram message:
"🚀 TSX Scanner Online"

Test commands by messaging your bot:
- `/help` — shows all commands
- `/status` — shows system status
- `/watchlist` — shows current watchlist (empty at first)

---

## Step 5 — Deploy to Railway (free cloud hosting)

### 5a — Push to GitHub

1. Create a free account at github.com
2. Create a new repository called `tsx-scanner`
3. Upload all files EXCEPT `.env` (the .gitignore handles this)

### 5b — Deploy on Railway

1. Go to railway.app — sign up free
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your `tsx-scanner` repository
4. Railway detects Python automatically

### 5c — Add environment variables on Railway

In Railway dashboard → your project → Variables tab:
- Add `TELEGRAM_TOKEN` = your bot token
- Add `TELEGRAM_CHAT_ID` = 6373753187
- Add `ACCOUNT_SIZE` = 1490
- Add `RISK_PCT` = 0.02

This is how credentials are stored safely in the cloud.

### 5d — Deploy

Click "Deploy" — Railway installs requirements and starts main.py.

You receive a Telegram message: "🚀 TSX Scanner Online"

Done. The system runs 24/7 for free.

---

## Daily workflow

**You do nothing** — the system runs automatically.

**4:15 PM MT daily:** You receive a Telegram message with:
- Which stocks have ENTER setups
- Full trade plan (entry, stop, targets, shares, capital)
- What the checklist confirmed

**During market hours:** You receive alerts when:
- Entry zone is hit → "Place your limit order now"
- Stop is approaching → "Watch this closely"
- Stop is hit → "Exit position now"
- Target 1 hit → "Sell 50% now"
- Target 2 hit → "Exit remainder — well done"

**You reply to the bot:**
- `/entered SU.TO 88.12` — after you place a trade
- `/exit SU.TO` — after you close a trade
- `/positions` — check your live P&L anytime
- `/watchlist` — see what's being monitored

---

## Manual watchlist management

Add a stock manually with custom levels:
```
/add SU.TO 88.00 83.00 92.00 96.00
```
Format: /add TICKER entry stop target1 target2

The system validates R:R before accepting.

---

## File structure

```
tsx_realtime/
├── main.py              ← Run this
├── requirements.txt     ← Dependencies
├── railway.toml         ← Deployment config
├── .env                 ← YOUR CREDENTIALS (never share)
├── .env.example         ← Template (safe to share)
├── .gitignore           ← Keeps .env out of GitHub
├── core/
│   ├── config.py        ← All settings
│   ├── state.py         ← Watchlist + position tracking
│   └── monitor.py       ← Price checking engine
├── data/
│   └── prices.py        ← Live price fetching
├── alerts/
│   ├── telegram_bot.py  ← All message formatting
│   └── commands.py      ← Bot command handler
└── scheduler/
    └── scheduler.py     ← Job scheduling
```

The `state/` folder is created automatically and stores:
- `watchlist.json` — your watched stocks
- `positions.json` — open trades
- `alerts.json` — active price alerts

---

## Troubleshooting

**Not receiving messages:**
- Check your bot token in .env
- Make sure you started a conversation with your bot on Telegram
- Send `/start` to your bot

**Price data errors:**
- Yahoo Finance has occasional outages — system retries automatically
- Check internet connection on your Railway server

**Railway goes to sleep:**
- Free tier stays active as long as there's activity
- The price check every 5 minutes keeps it awake during market hours
