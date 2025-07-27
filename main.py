import os
import time
import json
import logging
import threading
from datetime import datetime

import pytz
import requests
from requests.adapters import HTTPAdapter, Retry

# ------------------ CONFIG ------------------

# Read from environment (Render → Environment tab)
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID", "").strip()

USERNAMES = os.getenv("USERNAMES", "").split(",") if os.getenv("USERNAMES") else [
    "aaditya4chess", "xxhimanshu", "garrymarkus", "newboy97", "aiiyk",
    "yashkuma7586", "iva0912", "anshul_2004", "hitmeharder132", "kav_2004",
    "atharv741", "Utkarsh3604", "kartik689787", "darklyamused", "insaneishi",
    "priyanshu2564", "omenio", "shubhamyadav17", "abhinav_0810", "mkrock"
]

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))  # seconds

IST = pytz.timezone("Asia/Kolkata")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}

# ------------------ LOGGING ------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("chess-monitor")

# ------------------ GLOBAL STATE ------------------

user_uuids = {}
user_last_status = {}
user_last_seen_unix = {}

# Single shared session with retries
session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"]
)
adapter = HTTPAdapter(max_retries=retries)
session.mount("https://", adapter)
session.mount("http://", adapter)


# ------------------ HELPERS ------------------

def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.error("BOT_TOKEN or CHAT_ID not set — cannot send Telegram messages.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        session.post(url, data=data, timeout=10)
    except Exception as e:
        log.error(f"Telegram send error: {e}")


def get_updates(offset=None):
    """Long-poll Telegram for commands."""
    if not TELEGRAM_BOT_TOKEN:
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset is not None:
        params["offset"] = offset
    try:
        r = session.get(url, params=params, timeout=35)
        if r.status_code == 200:
            return r.json()
        else:
            log.warning(f"getUpdates non-200: {r.status_code} -> {r.text}")
    except Exception as e:
        log.error(f"Error fetching updates: {e}")
    return None


def convert_unix_to_ist(unix_timestamp):
    if not unix_timestamp:
        return "Unknown"
    try:
        dt_utc = datetime.utcfromtimestamp(unix_timestamp).replace(tzinfo=pytz.utc)
        dt_ist = dt_utc.astimezone(IST)
        return dt_ist.strftime("%Y-%m-%d %H:%M:%S IST")
    except Exception:
        return "Invalid Time"


def get_user_data(username):
    """Returns uuid + last_online_unix using the same endpoints you used."""
    uuid_url = f"https://www.chess.com/callback/user/popup/{username}"
    online_url = f"https://api.chess.com/pub/player/{username}"

    uuid = None
    last_online_unix = None

    try:
        r1 = session.get(uuid_url, headers=HEADERS, timeout=10)
        if r1.status_code == 200:
            uuid = r1.json().get("uuid")
        else:
            log.debug(f"popup {username} -> {r1.status_code}")
    except Exception as e:
        log.warning(f"UUID error for {username}: {e}")

    try:
        r2 = session.get(online_url, headers=HEADERS, timeout=10)
        if r2.status_code == 200:
            last_online_unix = r2.json().get("last_online")
        else:
            log.debug(f"player {username} -> {r2.status_code}")
    except Exception as e:
        log.warning(f"last_online error for {username}: {e}")

    return {"uuid": uuid, "last_online_unix": last_online_unix}


def get_presence_data(uuid):
    if not uuid:
        return None
    try:
        url = f"https://www.chess.com/service/presence/users?ids={uuid}"
        resp = session.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            users = resp.json().get("users", [])
            if users:
                return users[0]
        else:
            log.debug(f"presence {uuid} -> {resp.status_code}")
    except Exception as e:
        log.warning(f"Presence error for {uuid}: {e}")
    return None


# ------------------ COMMANDS ------------------

def handle_status_command():
    lines = ["♟ Player Status:"]
    for username in USERNAMES:
        uuid = user_uuids.get(username)
        presence = get_presence_data(uuid) if uuid else None
        status = presence.get("status") if presence else "unknown"
        last_seen = convert_unix_to_ist(user_last_seen_unix.get(username))
        lines.append(f"• {username}: {status.upper()} (Last Online: {last_seen})")
    send_telegram_message("\n".join(lines))


def listen_for_commands():
    last_update_id = None
    while True:
        try:
            updates = get_updates(last_update_id + 1 if last_update_id else None)
            if updates and "result" in updates:
                for update in updates["result"]:
                    last_update_id = update["update_id"]
                    message = update.get("message", {})
                    if not message:
                        continue
                    text = message.get("text", "").strip()
                    chat_id = str(message.get("chat", {}).get("id"))

                    # If you want to restrict to your chat only:
                    if TELEGRAM_CHAT_ID and chat_id != TELEGRAM_CHAT_ID:
                        continue

                    if text.lower() == "/status":
                        handle_status_command()
        except Exception as e:
            log.error(f"listen_for_commands loop error: {e}")

        time.sleep(2)


# ------------------ MONITOR LOOP ------------------

def monitor_loop():
    # Initial fetch
    for username in USERNAMES:
        data = get_user_data(username)
        if not data:
            log.error(f"[X] Could not fetch data for {username}")
            continue

        uuid = data.get("uuid")
        last_online_unix = data.get("last_online_unix")
        if uuid:
            user_uuids[username] = uuid
            user_last_seen_unix[username] = last_online_unix
            log.info(f"[+] {username} UUID: {uuid}, Last Online: {convert_unix_to_ist(last_online_unix)}")
        else:
            log.warning(f"[X] UUID not found for {username}")

    log.info("[~] Monitoring users...")

    while True:
        try:
            for username in user_uuids:
                uuid = user_uuids[username]
                last_online_unix = user_last_seen_unix.get(username)
                presence = get_presence_data(uuid)

                if presence:
                    current_status = presence.get("status")
                    last_status = user_last_status.get(username)

                    # notify on offline -> online
                    if current_status == "online" and last_status != "online":
                        msg = f"♟ {username} is now ONLINE\nLast Online: {convert_unix_to_ist(last_online_unix)}"
                        send_telegram_message(msg)

                    user_last_status[username] = current_status
                else:
                    log.debug(f"No presence data for {username}")

            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            log.error(f"monitor_loop error: {e}")
            time.sleep(5)


# ------------------ MAIN ------------------

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("BOT_TOKEN/CHAT_ID not set. You won't receive Telegram messages.")

    # Start the monitor & command listener
    threading.Thread(target=monitor_loop, daemon=True).start()
    listen_for_commands()
