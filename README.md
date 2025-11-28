# Telegram-VIP-Signal-Auto-Trading-Bot-for-MT5

````markdown
An automated high-frequency trading bot that parses Arabic and English trade signals from Telegram channels and executes them instantly on MetaTrader 5 (MT5).

## ⚡ Features

* **Unicode/Arabic Support:** specialized normalization to handle Right-to-Left (RTL) text and invisible formatting characters.
* **Smart TP Selection:** Automatically chooses TP2 over TP1 if the risk/reward ratio is favorable.
* **Equity Guard:** Hard-stop mechanism that disables trading if equity drops below a defined percentage.
* **Spread Filter:** Prevents execution during high-spread news events.
* **Telegram Control:** Full remote control via a private bot (Start, Stop, modify Lot Size/SL).

---

## 🛠️ Installation

### 1. Prerequisites
* **Python 3.8+**
* **MetaTrader 5 Terminal:** Must be installed and **running** on the machine.
* **Telegram Account:** To listen to the signal channel.

### 2. Setup
Clone the repository and install dependencies:

```bash
git clone [https://github.com/yourusername/mt5-signal-sniper.git](https://github.com/yourusername/mt5-signal-sniper.git)
cd mt5-signal-sniper
pip install -r requirements.txt
````

*Create a `requirements.txt` with the following content if you haven't already:*

```text
python-telegram-bot
telethon
MetaTrader5
python-dotenv
asyncio
```

-----

## 🔑 Configuration & Credentials

You must create a `.env` file in the root directory.

### Step 1: Get Telegram API (The Listener)

This allows the bot to "read" messages as your user account.

1.  Go to [my.telegram.org](https://my.telegram.org) and login.
2.  Select **API development tools**.
3.  Create a new app. Copy the `API_ID` and `API_HASH`.

### Step 2: Get Bot Token (The Controller)

This is the interface you use to send commands.

1.  Message **@BotFather** on Telegram.
2.  Send `/newbot` and follow the instructions.
3.  Copy the **HTTP API Token**.
4.  Get your personal Chat ID by messaging **@userinfobot**.

### Step 3: Configure `.env`

Create a file named `.env` and fill in your details:

```ini
# LISTENER CREDENTIALS (my.telegram.org)
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_SESSION_NAME=sniper_session

# CONTROLLER CREDENTIALS (BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_BOT_CHAT_IDS=123456789

# SIGNAL SOURCE
# Use the included helper script to find Channel IDs (starts with -100)
TELEGRAM_SOURCE_CHANNEL_ID=-100123456789

# METATRADER 5 LOGIN
MT5_ACCOUNT=12345678
MT5_PASSWORD=your_broker_password
MT5_SERVER=Broker-Server
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
```

-----

## 🧠 Signal Detection Logic

The bot uses Python's `re` (Regular Expression) library to parse text. The logic is located in the `parse_signal` function.

### How it Works

1.  **Normalization:** Converts text to `NFKC` form to fix Arabic character encoding.
2.  **Cleaning:** Removes invisible RTL markers (`\u200f`, `\u200e`) that break standard parsing.
3.  **Extraction:** Uses Regex patterns to find keywords.

### Modifying the Logic

If your signal provider changes their format, you must edit the Regex patterns in `main.py`.

#### Example 1: Changing "Entry" Keyword

**Current Code:**

```python
# Looks for "الدخول:" followed by digits
entry_match = re.search(r'الدخول:\s*(\d+\.?\d*)', message)
```

**To change it to "Buy At":**

```python
entry_match = re.search(r'Buy At\s*(\d+\.?\d*)', message, re.IGNORECASE)
```

#### Example 2: Changing TP Format

**Current Code:**

```python
# Looks for bullet point "• TP1:"
tp1_match = re.search(r'•\s*TP1:\s*(\d+\.?\d*)', message)
```

**To change it to "Target 1 -":**

```python
tp1_match = re.search(r'Target 1\s*-\s*(\d+\.?\d*)', message)
```

#### Example 3: Changing Action Keywords

**Current Code:**

```python
# Looks for Arabic Sell/Buy
action_match = re.search(r'(شراء|بيع)', message)
```

**To change it to English:**

```python
# Looks for BUY or SELL (Case Insensitive)
action_match = re.search(r'(BUY|SELL)', message, re.IGNORECASE)
```

-----

## 📱 Telegram Commands

Once the bot is running, send these commands to your Admin Bot:

| Command | Description |
| :--- | :--- |
| `/start` | Activate the bot (starts taking trades). |
| `/stop` | Deactivate the bot (stops listening). |
| `/status` | View current P\&L, balance, and settings. |
| `/baselot 0.1` | Set the starting lot size. |
| `/safety 30` | Set max equity drawdown to 30%. |
| `/smarttargets` | Toggle dynamic TP selection. |
| `/close` | Panic button: Close all open positions. |

-----

## 🚀 Running the Bot

1.  Open the MT5 Terminal manually and login.
2.  Run the script:
    ```bash
    python main.py
    ```
3.  **First Run Only:** You will be prompted in the console to enter your phone number and the Telegram login code to authorize the listener session.

-----

## ⚠️ Disclaimer

Trading Forex/Crypto involves substantial risk. This software is provided "as is" without warranty of any kind. The author is not responsible for any financial losses incurred while using this bot. **Test thoroughly on a Demo account first.**

```

```
