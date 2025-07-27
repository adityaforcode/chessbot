import time
import requests
import logging
from datetime import datetime
import pytz
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os

# === CONFIGURATION ===
USERNAMES = ["aaditya4chess", "xxhimanshu", "garrymarkus","newboy97","aiiyk","yashkuma7586","iva0912","anshul_2004","hitmeharder132","kav_2004","atharv741","Utkarsh3604","kartik689787","darklyamused","insaneishi","priyanshu2564","omenio","shubhamyadav17","abhinav_0810","mkrock"]
CHECK_INTERVAL = 60  # seconds between checks
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # <-- Replace with your chat ID (to receive notifications)
IST = pytz.timezone("Asia/Kolkata")

# === GLOBALS ===
user_status = {u: "offline" for u in USERNAMES}  # Track online/offline
user_last_online = {u: None for u in USERNAMES}

# === LOGGING ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# === HELPER FUNCTIONS ===
def convert_unix_to_ist(unix_timestamp):
    if not unix_timestamp:
        return "Unknown"
    try:
        dt_utc = datetime.utcfromtimestamp(unix_timestamp)
        dt_utc = dt_utc.replace(tzinfo=pytz.utc)
        dt_ist = dt_utc.astimezone(IST)
        return dt_ist.strftime("%Y-%m-%d %H:%M:%S IST")
    except Exception:
        return "Invalid Time"

def get_player_status(username):
    """Fetch online status using Chess.com public API."""
    try:
        url = f"https://api.chess.com/pub/player/{username}"
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            last_online = data.get("last_online")
            user_last_online[username] = last_online
            # User is online if last_online within 5 min
            now_unix = int(time.time())
            if now_unix - last_online < 300:
                return "online"
            else:
                return "offline"
        else:
            return "unknown"
    except Exception as e:
        logging.error(f"Error fetching {username}: {e}")
        return "unknown"

async def send_notification(bot: Bot, message: str):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message)
    except Exception as e:
        logging.error(f"Error sending Telegram message: {e}")

async def monitor_players(bot: Bot):
    """Background loop to monitor players."""
    while True:
        for username in USERNAMES:
            current_status = get_player_status(username)
            if current_status != user_status[username]:
                user_status[username] = current_status
                last_seen = convert_unix_to_ist(user_last_online[username])
                await send_notification(bot, f"{username} is now {current_status.upper()}.\nLast seen: {last_seen}")
        await asyncio.sleep(CHECK_INTERVAL)

# === TELEGRAM COMMANDS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Chess.com presence bot is running!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the status of all tracked players."""
    msg_lines = []
    for username in USERNAMES:
        last_seen = convert_unix_to_ist(user_last_online[username])
        msg_lines.append(f"{username}: {user_status[username].upper()} (Last seen: {last_seen})")
    await update.message.reply_text("\n".join(msg_lines))

# === MAIN ENTRY ===
import asyncio

async def main():
    bot = Bot(token=BOT_TOKEN)
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    # Start background monitoring
   def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    ...
    app.run_polling()

if __name__ == "__main__":
    main()
