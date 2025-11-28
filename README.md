# Telegram VIP Signal Auto-Trader for MetaTrader 5

An automated high-frequency trading bot that reads Arabic and English trade signals from Telegram channels and executes them on MetaTrader 5 (MT5) with minimal delay. Built for reliability: handles RTL text, filters risky conditions, and provides remote control via a private Telegram controller bot.

---

## Key Features

* **Arabic & Unicode handling** — Normalizes Arabic text and removes invisible direction markers that break parsing.
* **Smart target selection** — Chooses secondary profit target (TP2) automatically when its risk/reward profile is better than TP1.
* **Equity protection** — Automatic hard stop that disables new trades when equity falls below a configurable threshold.
* **Spread and news filter** — Blocks order execution during abnormally wide spreads or defined news events.
* **Remote Telegram controller** — Start, stop, change lot size, set SL/safety limits, and close positions from a private bot.
* **Lightweight and extensible** — Parsing rules live in one place (easy to update when signal format changes).

---

## Installation

### Requirements

* Python 3.8 or newer
* MetaTrader 5 terminal installed and logged in on the same machine where the bot runs
* Telegram account (for the listener) and a Telegram bot token (for remote control)

### Setup

```bash
git clone https://github.com/your/repo.git
cd mt5-signal-sniper
pip install -r requirements.txt
```

Example `requirements.txt` (create if missing):

```
python-telegram-bot
telethon
MetaTrader5
python-dotenv
asyncio
```

---

## Configuration

Create a `.env` file in the repository root. Required variables:

```ini
# Listener (user account) credentials from my.telegram.org
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION_NAME=sniper_session

# Controller (BotFather) credentials
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_BOT_CHAT_IDS=123456789,987654321

# Signal source (channel ID usually starts with -100)
TELEGRAM_SOURCE_CHANNEL_ID=-100123456789

# MetaTrader 5 credentials and path
MT5_ACCOUNT=12345678
MT5_PASSWORD=your_broker_password
MT5_SERVER=Broker-Server
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
```

* `TELEGRAM_API_ID` / `TELEGRAM_API_HASH`: Create at [https://my.telegram.org](https://my.telegram.org) → API development tools.
* `TELEGRAM_BOT_TOKEN`: Create via @BotFather.
* `TELEGRAM_BOT_CHAT_IDS`: Admin chat IDs allowed to control the bot. Obtain with @userinfobot.
* `TELEGRAM_SOURCE_CHANNEL_ID`: Use the included helper script to resolve channel IDs if needed.

---

## Signal Parsing: how it works

Parsing logic resides in `parse_signal(message: str)`.

Steps performed on every incoming message:

1. **Normalize**
   Convert to Unicode Normalization Form KC (`NFKC`) to unify character variants (important for Arabic variations and Arabic-Indic digits).

2. **Clean**
   Strip invisible Unicode markers used for RTL/LTR control (e.g., `\u200f`, `\u200e`) and other non-printing characters that break regex patterns.

3. **Tokenize & lower**
   Convert to a predictable case and split into tokens for keyword detection while preserving numbers and decimal separators.

4. **Extract with Regex**
   Use targeted regular expressions to locate: action (buy/sell), entry price, stop loss (SL), profit targets (TP1, TP2, …), and optional metadata (expiry, symbol, timeframe).

5. **Validate**
   Confirm prices are in a plausible range for the detected symbol and that required fields exist before sending to MT5.

---

## Common Regex examples & replacements

Change patterns in `main.py` under `parse_signal` when the provider changes formatting.

* Arabic entry (example):

```python
entry_match = re.search(r'الدخول:\s*(\d+\.?\d*)', message)
```

* English entry (case-insensitive):

```python
entry_match = re.search(r'Buy At\s*[:\-]?\s*(\d+\.?\d*)', message, re.IGNORECASE)
```

* TP bullet to alternative format:

```python
tp1_match = re.search(r'•\s*TP1:\s*(\d+\.?\d*)', message)
# To support "Target 1 - 1.2345":
tp1_match = re.search(r'Target\s*1\s*[-:]\s*(\d+\.?\d*)', message, re.IGNORECASE)
```

* Action keyword (Arabic & English):

```python
action_match = re.search(r'(شراء|بيع|BUY|SELL)', message, re.IGNORECASE)
```

Keep numeric capture groups flexible: allow both dot and comma decimals when necessary, then normalize to dot `.` before converting to float.

---

## Telegram Admin Commands

Control the bot via the controller bot using these commands from authorized chat IDs:

* `/start` — Enable live trading and signal processing.
* `/stop` — Disable live trading (listener remains active but won’t execute orders).
* `/status` — Return current balance, equity, opened trades, and settings.
* `/baselot <size>` — Set the base lot size (e.g., `/baselot 0.1`).
* `/safety <percent>` — Set equity drawdown protection (e.g., `/safety 30` to stop if equity drops 30%).
* `/smarttargets` — Toggle the dynamic TP selection feature.
* `/close` — Force-close all open positions immediately.

---

## Running the Bot

1. Ensure MetaTrader 5 terminal is running and logged in.
2. Start the script:

```bash
python main.py
```

3. On first run, the listener will prompt for your phone number and the Telegram login code to create the session file specified by `TELEGRAM_SESSION_NAME`.

---

## Safety and testing

* Always test on a demo account before enabling live trading.
* Use conservative lot sizing while verifying parsing correctness and execution flow.
* Monitor spread filters and news events during initial runs to tune thresholds.
* Keep a separate logging channel or file for every signal and execution attempt for audit and debugging.

---

## Troubleshooting tips

* **MT5 not connecting**: Confirm `MT5_PATH` points to the running terminal and that the account is logged in.
* **Missed signals**: Check listener session validity and channel ID correctness; verify message text contains expected keywords.
* **Parsing errors on RTL text**: Ensure normalization and invisible-character-stripping steps run before regex matching. Log the raw incoming message to inspect hidden characters.
* **Orders rejected by broker**: Validate lot size, symbol notation, and available margin; check server name matches broker’s server string.

---

## License & Disclaimer

This software is provided without warranty. Trading involves risk; the author is not responsible for any losses incurred. Use the software at your own risk. Test thoroughly on demo accounts before trading with real funds.
