import time
import requests
from datetime import datetime
import pytz
import threading
from flask import Flask
import os

# === CONFIGURATION ===
USERNAMES = ["aaditya4chess", "xxhimanshu", "garrymarkus", "newboy97", "aiiyk", "yashkuma7586",
             "iva0912", "anshul_2004", "hitmeharder132", "kav_2004", "atharv741", "Utkarsh3604",
             "kartik689787", "darklyamused", "insaneishi", "priyanshu2564", "omenio",
             "shubhamyadav17", "abhinav_0810", "mkrock"]
CHECK_INTERVAL = 60  # seconds between checks

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "8222471152:AAG21bz7AMTcBqWoD1G4zmkScjoFCIKSEhQ"
TELEGRAM_CHAT_ID = "5643042263"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/115.0.0.0 Safari/537.36"
}

IST = pytz.timezone("Asia/Kolkata")

# === GLOBAL DATA ===
user_uuids = {}
user_last_status = {}
user_last_seen_unix = {}

# === FLASK APP FOR RENDER HEALTH CHECK ===
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running ✅"

# === TELEGRAM NOTIFICATION ===
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        requests.post(url, data=data, timeout=5)
    except Exception as e:
        print(f"[!] Telegram error: {e}")


def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 10, "offset": offset}
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"[!] Error fetching updates: {e}")
    return None


# === TIME HELPERS ===
def convert_unix_to_ist(unix_timestamp):
    if not unix_timestamp:
        return "Unknown"
    try:
        dt_utc = datetime.utcfromtimestamp(unix_timestamp).replace(tzinfo=pytz.utc)
        dt_ist = dt_utc.astimezone(IST)
        return dt_ist.strftime("%Y-%m-%d %H:%M:%S IST")
    except:
        return "Invalid Time"


# === NETWORK HELPERS ===
def get_user_data(username):
    uuid_url = f"https://www.chess.com/callback/user/popup/{username}"
    online_url = f"https://api.chess.com/pub/player/{username}"

    uuid = None
    last_online_unix = None

    try:
        r1 = requests.get(uuid_url, headers=HEADERS, timeout=5)
        if r1.status_code == 200:
            uuid = r1.json().get("uuid")
    except:
        pass

    try:
        r2 = requests.get(online_url, headers=HEADERS, timeout=5)
        if r2.status_code == 200:
            last_online_unix = r2.json().get("last_online")
    except:
        pass

    return {"uuid": uuid, "last_online_unix": last_online_unix}


def get_presence_data(uuid):
    try:
        url = f"https://www.chess.com/service/presence/users?ids={uuid}"
        resp = requests.get(url, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            users = resp.json().get("users", [])
            if users:
                return users[0]
    except:
        pass
    return None


# === BOT COMMAND HANDLER ===
def handle_status_command():
    message_lines = ["♟ **Player Status:**"]
    for username in USERNAMES:
        uuid = user_uuids.get(username)
        presence = get_presence_data(uuid) if uuid else None
        status = presence.get("status") if presence else "unknown"
        last_seen = convert_unix_to_ist(user_last_seen_unix.get(username))
        message_lines.append(f"• {username}: {status.upper()} (Last Online: {last_seen})")
    send_telegram_message("\n".join(message_lines))


def listen_for_commands():
    last_update_id = None
    while True:
        updates = get_updates(last_update_id + 1 if last_update_id else None)
        if updates and "result" in updates:
            for update in updates["result"]:
                last_update_id = update["update_id"]
                message = update.get("message", {})
                text = message.get("text", "").strip()
                chat_id = message.get("chat", {}).get("id")
                if text.lower() == "/status" and str(chat_id) == TELEGRAM_CHAT_ID:
                    handle_status_command()
        time.sleep(2)


# === MAIN LOOP ===
def monitor_loop():
    global user_uuids, user_last_status, user_last_seen_unix

    # Initial fetch of user data
    for username in USERNAMES:
        data = get_user_data(username)
        if data:
            uuid = data.get("uuid")
            last_online_unix = data.get("last_online_unix")
            if uuid:
                user_uuids[username] = uuid
                user_last_seen_unix[username] = last_online_unix
                print(f"[+] {username} UUID: {uuid}, Last Online: {convert_unix_to_ist(last_online_unix)}")
            else:
                print(f"[X] UUID not found for {username}")

    print("\n[~] Monitoring users...\n")

    while True:
        for username in user_uuids:
            uuid = user_uuids[username]
            last_online_unix = user_last_seen_unix.get(username)
            presence = get_presence_data(uuid)

            if presence:
                current_status = presence.get("status")
                last_status = user_last_status.get(username)

                if current_status == "online" and last_status != "online":
                    message = f"♟ {username} is now ONLINE\nLast Online: {convert_unix_to_ist(last_online_unix)}"
                    send_telegram_message(message)

                user_last_status[username] = current_status
            else:
                print(f"[!] No presence data for {username}")

        time.sleep(CHECK_INTERVAL)


# === START EVERYTHING ===
if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    threading.Thread(target=listen_for_commands, daemon=True).start()

    # Start Flask server on the port provided by Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
