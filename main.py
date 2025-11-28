import asyncio
import re
import hashlib
import time
import unicodedata
from typing import Dict, Optional, Tuple
import MetaTrader5 as mt5
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telethon import TelegramClient, events
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# Configuration - Loaded from env vars
class Config:
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    SOURCE_CHANNEL = os.getenv('TELEGRAM_SOURCE_CHANNEL_ID')  # Should be an integer, e.g., -1002867602729
    BOT_CHAT_IDS = os.getenv('TELEGRAM_BOT_CHAT_IDS').split(',') if os.getenv('TELEGRAM_BOT_CHAT_IDS') else []  # Comma-separated list, e.g., "5939411038,1439474740"
    API_ID = os.getenv('TELEGRAM_API_ID')
    API_HASH = os.getenv('TELEGRAM_API_HASH')
    MT5_ACCOUNT = os.getenv('MT5_ACCOUNT')
    MT5_PASSWORD = os.getenv('MT5_PASSWORD')
    MT5_SERVER = os.getenv('MT5_SERVER')
    MT5_PATH = os.getenv('MT5_PATH')
    SESSION_NAME = os.getenv('TELEGRAM_SESSION_NAME', 'session')  # Default session name

# Check for required env vars
required_vars = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_SOURCE_CHANNEL_ID', 'TELEGRAM_BOT_CHAT_IDS', 'TELEGRAM_API_ID', 'TELEGRAM_API_HASH', 'MT5_ACCOUNT', 'MT5_PASSWORD', 'MT5_SERVER', 'MT5_PATH']
missing = [var for var in required_vars if not os.getenv(var)]
if missing:
    raise ValueError(f"Missing required environment variables: {', '.join(missing)}. Please set them in .env file.")

# Convert types where needed
Config.SOURCE_CHANNEL = int(Config.SOURCE_CHANNEL)
Config.BOT_CHAT_IDS = [int(chat_id.strip()) for chat_id in Config.BOT_CHAT_IDS]
Config.API_ID = int(Config.API_ID)
Config.MT5_ACCOUNT = int(Config.MT5_ACCOUNT)

class SimpleTradingBot:
    def __init__(self):
        # Basic Settings - All adjustable via Telegram
        self.base_lot_size = 0.1
        self.lot_increment = 0.05  # Add 0.05 each consecutive trade
        self.stop_loss_points = 15
        self.use_smart_tp = True  # Auto choose TP1 or TP2

        # Safety Settings - Controllable via chat
        self.max_loss_percent = 35.0  # Stop at 35% equity loss
        self.enable_safety = True
        self.max_spread = 5.0

        # Bot State
        self.is_active = False
        self.initial_equity = None

        # Trade Tracking - Simple
        self.last_action = {}  # symbol -> "buy"/"sell"
        self.consecutive_count = {}  # symbol -> count
        self.processed_signals = set()

        print(f"Simple Trading Bot Ready")
        print(f"Base lot: {self.base_lot_size}")
        print(f"Safety stop: {self.max_loss_percent}%")

    def init_mt5(self) -> bool:
        """Connect to MetaTrader5."""
        try:
            mt5.shutdown()
        except:
            pass

        if not mt5.initialize(
            login=Config.MT5_ACCOUNT,
            password=Config.MT5_PASSWORD,
            server=Config.MT5_SERVER,
            path=Config.MT5_PATH
        ):
            print(f"MT5 connection failed: {mt5.last_error()}")
            return False

        account = mt5.account_info()
        if account:
            self.initial_equity = account.equity
            print(f"Connected! Balance: ${account.balance}")
            return True
        return False


    def parse_signal(self, message):
        """Parse Arabic signals with improved Unicode handling and new format."""
        if not message:
            return None

        # Normalize Unicode to handle Arabic text consistently
        message = unicodedata.normalize('NFKC', message)

        # Debug: Print the first part of the message to see what we're working with
        print(f"🔍 DEBUG - Message preview: {repr(message[:150])}")

        # Clean the message - remove Right-to-Left marks and other invisible characters
        message = re.sub(r'[\u200f\u200e\u202a-\u202e]', '', message)

        # Remove markdown formatting (**text**)
        message = re.sub(r'\*\*(.*?)\*\*', r'\1', message)
        print(f"🔍 DEBUG - After cleaning: {repr(message[:150])}")

        # Extract action and symbol - handle bold formatting
        # Look for شراء/بيع followed by emoji and symbol
        action_match = re.search(r'(شراء|بيع)\s*(?:🟢|🔴)?\s*(?:—|–|-)\s*([A-Z]+(?:[A-Z0-9]*)?)', message, re.UNICODE)

        if not action_match:
            print("❌ Failed to match action and symbol")
            print(f"🔍 DEBUG - Looking for pattern in: {message[:200]}")
            # Let's try a simpler pattern as fallback
            simple_action_match = re.search(r'(شراء|بيع)', message)
            simple_symbol_match = re.search(r'([A-Z]{4,})', message)  # Look for 4+ capital letters (like XAUUSD)

            if simple_action_match and simple_symbol_match:
                action = 'buy' if simple_action_match.group(1) == 'شراء' else 'sell'
                symbol = simple_symbol_match.group(1)
                print(f"✅ Fallback match - action: {action}, symbol: {symbol}")
            else:
                print("❌ Even fallback pattern failed")
                return None
        else:
            action = 'buy' if action_match.group(1) == 'شراء' else 'sell'
            symbol = action_match.group(2)
            print(f"✅ Matched action: {action}, symbol: {symbol}")

        # Extract entry price - handle bold formatting around الدخول:
        entry_match = re.search(r'الدخول:\s*(\d+\.?\d*)', message)
        if not entry_match:
            print("❌ Failed to match entry price")
            print(f"🔍 DEBUG - Searching for 'الدخول:' in message")
            return None

        entry_price = float(entry_match.group(1))
        print(f"✅ Matched entry: {entry_price}")

        # Extract TP1 and TP2 - handle bullet points
        tp1_match = re.search(r'•\s*TP1:\s*(\d+\.?\d*)', message)
        tp2_match = re.search(r'•\s*TP2:\s*(\d+\.?\d*)', message)

        if not tp1_match:
            print("❌ Failed to match TP1")
            print(f"🔍 DEBUG - Searching for 'TP1:' in message")
            # Try to find any number after TP1 as fallback
            tp1_fallback = re.search(r'TP1[:\s]*(\d+\.?\d*)', message)
            if tp1_fallback:
                tp1 = float(tp1_fallback.group(1))
                print(f"✅ Fallback TP1 match: {tp1}")
            else:
                return None
        else:
            tp1 = float(tp1_match.group(1))
            print(f"✅ Matched TP1: {tp1}")

        # TP2 is optional
        if tp2_match:
            tp2 = float(tp2_match.group(1))
            print(f"✅ Matched TP2: {tp2}")
        else:
            tp2_fallback = re.search(r'TP2[:\s]*(\d+\.?\d*)', message)
            tp2 = float(tp2_fallback.group(1)) if tp2_fallback else None
            if tp2:
                print(f"✅ Fallback TP2 match: {tp2}")
            else:
                print("⚠️ No TP2 found")

        signal = {
            "action": action,
            "symbol": symbol,
            "entry": entry_price,
            "tp1": tp1,
            "tp2": tp2
        }

        # Validate signal
        if not all([signal["entry"], signal["tp1"]]):  # TP2 is optional
            print("❌ Missing required fields (entry or TP1)")
            return None

        print(f"✅ Successfully parsed signal: {signal}")
        return signal

    def choose_target(self, signal: Dict) -> float:
        """Smart TP selection based on signal quality."""
        if not self.use_smart_tp or not signal["tp2"]:
            return signal["tp1"]

        entry = signal["entry"]
        tp1_distance = abs(signal["tp1"] - entry)
        tp2_distance = abs(signal["tp2"] - entry)

        # Use TP2 if it's less than 2x TP1 distance (reasonable risk)
        if tp2_distance < (tp1_distance * 2):
            print(f"Using TP2: {signal['tp2']} (distance: {tp2_distance:.2f})")
            return signal["tp2"]
        else:
            print(f"Using TP1: {signal['tp1']} (distance: {tp1_distance:.2f})")
            return signal["tp1"]

    def calculate_lot_size(self, symbol: str, action: str) -> float:
        """Calculate position size with progression."""
        # Check if direction changed
        last_action = self.last_action.get(symbol)
        if last_action != action:
            # Direction changed - reset and close opposite positions
            print(f"Direction changed from {last_action} to {action}")
            self.consecutive_count[symbol] = 1
            closed = self.close_symbol_positions(symbol)
            if closed > 0:
                print(f"Closed {closed} opposite positions")
        else:
            # Same direction - increase count
            count = self.consecutive_count.get(symbol, 0) + 1
            self.consecutive_count[symbol] = count

        # Calculate lot size with progression
        consecutive = self.consecutive_count.get(symbol, 1)
        lot_size = self.base_lot_size + (self.lot_increment * (consecutive - 1))

        # Safety check - don't exceed reasonable limits
        max_lot = self.base_lot_size * 5  # Max 5x base size
        lot_size = min(lot_size, max_lot)

        print(f"Position size: {lot_size} lots (consecutive: {consecutive})")
        return lot_size

    def close_symbol_positions(self, symbol: str) -> int:
        """Close all positions for symbol."""
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return 0

        closed = 0
        for pos in positions:
            opposite_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                continue

            price = tick.bid if pos.type == 0 else tick.ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": pos.volume,
                "type": opposite_type,
                "position": pos.ticket,
                "price": price,
                "deviation": 20,
                "magic": 123456,
                "comment": "Direction change"
            }

            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                closed += 1
                print(f"Closed position {pos.ticket}")

        return closed

    def check_safety_stop(self) -> bool:
        """Check if we should stop trading due to losses."""
        if not self.enable_safety or not self.initial_equity:
            return False

        account = mt5.account_info()
        if not account:
            return False

        equity_loss_percent = ((self.initial_equity - account.equity) / self.initial_equity) * 100

        if equity_loss_percent >= self.max_loss_percent:
            print(f"Safety stop triggered! Loss: {equity_loss_percent:.1f}%")
            return True

        return False

    def execute_trade(self, signal: Dict) -> Tuple[bool, str]:
        """Execute trade - keep it simple."""
        if not self.is_active:
            return False, "Bot is inactive"

        # Safety check
        if self.check_safety_stop():
            self.is_active = False
            return False, f"🚨 SAFETY STOP! Equity loss reached {self.max_loss_percent}%. Bot deactivated."

        symbol = signal["symbol"]
        action = signal["action"]

        print(f"Executing {action} trade for {symbol}")

        # Check spread
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        if not tick or not info:
            return False, "No market data available"

        spread = (tick.ask - tick.bid) / info.point
        print(f"Current spread: {spread:.1f} points")

        if spread > self.max_spread:
            return False, f"Spread too wide: {spread:.1f} points (max: {self.max_spread})"

        # Calculate position size
        lot_size = self.calculate_lot_size(symbol, action)

        # Get prices
        price = tick.ask if action == "buy" else tick.bid

        # Calculate stop loss
        sl = (price - self.stop_loss_points * info.point if action == "buy"
              else price + self.stop_loss_points * info.point)

        # Smart target selection
        tp = self.choose_target(signal)

        print(f"Trade details: Price={price:.2f}, SL={sl:.2f}, TP={tp:.2f}")

        # Build trade request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": mt5.ORDER_TYPE_BUY if action == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 123456,
            "comment": f"Bot-{action}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC
        }

        # Execute
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Trade failed: {result.comment} (Code: {result.retcode})"
            print(error_msg)
            return False, error_msg

        # Update tracking
        self.last_action[symbol] = action

        # Success message
        account = mt5.account_info()
        equity_change = account.equity - self.initial_equity if self.initial_equity else 0

        target_type = "TP2" if tp == signal.get("tp2") else "TP1"

        success_msg = (
            f"✅ Trade Executed\n"
            f"Symbol: {symbol}\n"
            f"Action: {action.upper()}\n"
            f"Size: {lot_size} lots\n"
            f"Price: {price:.2f}\n"
            f"Stop Loss: {sl:.2f}\n"
            f"Target: {tp:.2f} ({target_type})\n"
            f"Spread: {spread:.1f} points\n"
            f"Equity: ${account.equity:.2f} ({equity_change:+.2f})"
        )

        print("✅ Trade executed successfully!")
        return True, success_msg

# Bot instance
bot = SimpleTradingBot()

# Telegram Commands - Simple and clear
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the bot."""
    bot.is_active = True
    await update.message.reply_text(
        f"🟢 Bot Started\n"
        f"Base lot size: {bot.base_lot_size}\n"
        f"Safety stop: {bot.max_loss_percent}%\n"
        f"Spread limit: {bot.max_spread} points\n"
        f"Smart targets: {'On' if bot.use_smart_tp else 'Off'}"
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop the bot."""
    bot.is_active = False
    await update.message.reply_text("🔴 Bot Stopped")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot status."""
    account = mt5.account_info()
    if not account:
        await update.message.reply_text("❌ Cannot connect to MT5")
        return

    equity_change = account.equity - bot.initial_equity if bot.initial_equity else 0
    status_text = "🟢 Active" if bot.is_active else "🔴 Inactive"

    msg = (
        f"📊 Bot Status: {status_text}\n\n"
        f"💰 Account:\n"
        f"Balance: ${account.balance:.2f}\n"
        f"Equity: ${account.equity:.2f}\n"
        f"Profit/Loss: {equity_change:+.2f}\n\n"
        f"⚙️ Settings:\n"
        f"Base lot: {bot.base_lot_size}\n"
        f"Safety stop: {bot.max_loss_percent}%\n"
        f"Stop loss: {bot.stop_loss_points} points\n"
        f"Max spread: {bot.max_spread} points"
    )
    await update.message.reply_text(msg)

async def positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show open positions."""
    positions = mt5.positions_get()
    if not positions:
        await update.message.reply_text("No open positions")
        return

    msg = "📊 Open Positions:\n\n"
    total_profit = 0

    for i, pos in enumerate(positions, 1):
        action = "BUY" if pos.type == 0 else "SELL"
        total_profit += pos.profit
        msg += f"{i}. {action} {pos.volume} lots\n"
        msg += f"   Entry: {pos.price_open:.2f}\n"
        msg += f"   Current: {pos.price_current:.2f}\n"
        msg += f"   P&L: ${pos.profit:.2f}\n\n"

    msg += f"Total P&L: ${total_profit:.2f}"
    await update.message.reply_text(msg)

async def close_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close all positions."""
    positions = mt5.positions_get()
    if not positions:
        await update.message.reply_text("No positions to close")
        return

    closed = 0
    for pos in positions:
        closed += bot.close_symbol_positions(pos.symbol)

    await update.message.reply_text(f"✅ Closed {closed} positions")

async def set_base_lot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change base lot size: /baselot 0.05"""
    if not context.args:
        await update.message.reply_text(f"Current base lot: {bot.base_lot_size}\nUsage: /baselot 0.05")
        return

    try:
        new_lot = float(context.args[0])
        if 0.01 <= new_lot <= 1.0:
            bot.base_lot_size = new_lot
            await update.message.reply_text(f"✅ Base lot changed to {new_lot}")
        else:
            await update.message.reply_text("❌ Lot size must be between 0.01 and 1.0")
    except ValueError:
        await update.message.reply_text("❌ Invalid number")

async def set_safety(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change safety stop: /safety 25"""
    if not context.args:
        await update.message.reply_text(f"Current safety: {bot.max_loss_percent}%\nUsage: /safety 25")
        return

    try:
        new_percent = float(context.args[0])
        if 5 <= new_percent <= 80:
            bot.max_loss_percent = new_percent
            await update.message.reply_text(f"✅ Safety stop set to {new_percent}%")
        else:
            await update.message.reply_text("❌ Safety must be between 5% and 80%")
    except ValueError:
        await update.message.reply_text("❌ Invalid number")

async def set_stoploss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change stop loss: /stoploss 20"""
    if not context.args:
        await update.message.reply_text(f"Current stop loss: {bot.stop_loss_points} points\nUsage: /stoploss 20")
        return

    try:
        new_sl = float(context.args[0])
        if 5 <= new_sl <= 100:
            bot.stop_loss_points = new_sl
            await update.message.reply_text(f"✅ Stop loss set to {new_sl} points")
        else:
            await update.message.reply_text("❌ Stop loss must be between 5 and 100 points")
    except ValueError:
        await update.message.reply_text("❌ Invalid number")

async def set_spread(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change max spread: /spread 10"""
    if not context.args:
        await update.message.reply_text(f"Current max spread: {bot.max_spread} points\nUsage: /spread 10")
        return

    try:
        new_spread = float(context.args[0])
        if 1 <= new_spread <= 50:
            bot.max_spread = new_spread
            await update.message.reply_text(f"✅ Max spread set to {new_spread} points")
        else:
            await update.message.reply_text("❌ Spread must be between 1 and 50 points")
    except ValueError:
        await update.message.reply_text("❌ Invalid number")

async def toggle_smart_targets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle smart TP selection."""
    bot.use_smart_tp = not bot.use_smart_tp
    status = "enabled" if bot.use_smart_tp else "disabled"
    await update.message.reply_text(f"🎯 Smart targets {status}")

async def toggle_safety(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle safety features."""
    bot.enable_safety = not bot.enable_safety
    status = "enabled" if bot.enable_safety else "disabled"
    await update.message.reply_text(f"🛡️ Safety features {status}")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help."""
    help_text = (
        "🤖 Trading Bot Commands:\n\n"
        "Basic:\n"
        "/start - Start bot\n"
        "/stop - Stop bot\n"
        "/status - Show status\n"
        "/positions - Show trades\n"
        "/close - Close all positions\n\n"
        "Settings:\n"
        "/baselot 0.1 - Set base lot size\n"
        "/safety 35 - Set safety stop %\n"
        "/stoploss 15 - Set stop loss points\n"
        "/spread 5 - Set max spread points\n"
        "/smarttargets - Toggle smart TP\n"
        "/safetyoff - Toggle safety features\n\n"
        "Debug:\n"
        "/help - This message"
    )
    await update.message.reply_text(help_text)

# Signal Processing
async def signal_listener(msg_queue: asyncio.Queue):
    """Listen for signals."""
    client = TelegramClient("session", Config.API_ID, Config.API_HASH)
    await client.start()
    print("✅ Listening for signals...")

    @client.on(events.NewMessage(chats=Config.SOURCE_CHANNEL))
    async def handle_signal(event):
        message = event.text
        print(f"📥 RAW MESSAGE RECEIVED: {message[:100]}...")

        # Prevent duplicates
        msg_hash = hashlib.sha256(message.encode()).hexdigest()
        if msg_hash in bot.processed_signals:
            print("⚠️ Duplicate signal ignored")
            return
        bot.processed_signals.add(msg_hash)

        # Parse and execute
        signal = bot.parse_signal(message)
        if signal:
            print(f"✅ Signal parsed: {signal['action']} {signal['symbol']}")
            success, response = bot.execute_trade(signal)
            await msg_queue.put(response)
        else:
            error_msg = f"❌ Could not parse signal from message \nMessage preview:\n{message[:500]}"
            print(error_msg)
            await msg_queue.put(error_msg)

    await client.run_until_disconnected()

async def message_sender(app_bot, msg_queue: asyncio.Queue):
    """Send messages to multiple Telegram chats."""
    while True:
        try:
            message = await msg_queue.get()
            # Send to all chat IDs
            for chat_id in Config.BOT_CHAT_IDS:
                try:
                    await app_bot.send_message(chat_id, message)
                except Exception as e:
                    print(f"Failed to send to {chat_id}: {e}")
        except Exception as e:
            print(f"Message sender error: {e}")
            await asyncio.sleep(1)

# Main Application
async def main():
    print("🚀 Starting Simple Trading Bot...")

    if not bot.init_mt5():
        print("❌ MT5 connection failed")
        return

    # Setup Telegram bot
    app = ApplicationBuilder().token(Config.BOT_TOKEN).build()

    # Add commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("positions", positions))
    app.add_handler(CommandHandler("close", close_all))
    app.add_handler(CommandHandler("baselot", set_base_lot))
    app.add_handler(CommandHandler("safety", set_safety))
    app.add_handler(CommandHandler("stoploss", set_stoploss))
    app.add_handler(CommandHandler("spread", set_spread))
    app.add_handler(CommandHandler("smarttargets", toggle_smart_targets))
    app.add_handler(CommandHandler("safetyoff", toggle_safety))
    app.add_handler(CommandHandler("help", help_cmd))

    await app.initialize()
    await app.start()

    # Start background tasks
    msg_queue = asyncio.Queue()
    tasks = [
        asyncio.create_task(signal_listener(msg_queue)),
        asyncio.create_task(message_sender(app.bot, msg_queue))
    ]

    # Send startup message to all chat IDs
    startup_msg = (
        f"🤖 Simple Trading Bot Online\n\n"
        f"Settings:\n"
        f"• Base lot: {bot.base_lot_size}\n"
        f"• Safety stop: {bot.max_loss_percent}%\n"
        f"• Stop loss: {bot.stop_loss_points} points\n"
        f"• Max spread: {bot.max_spread} points\n"
        f"• Smart targets: On\n\n"
        f"Use /help for commands\n"
        f"Use /start to begin trading\n\n"
        f"⚠️ Bot starts INACTIVE"
    )

    # Send to all chat IDs
    for chat_id in Config.BOT_CHAT_IDS:
        await app.bot.send_message(chat_id, startup_msg)

    await app.updater.start_polling()

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        for task in tasks:
            task.cancel()
        mt5.shutdown()
        await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error: {e}")
