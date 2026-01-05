# bot.py

import os  # <-- Added missing import for os
import time
import threading
import shutil
import aria2p
from pyrogram import Client

# ================= CONFIG IMPORT =================
import config

# ================= MODULAR IMPORTS =================
from plugins.commands import register_handlers

try:
    from plugins.weblive import start_web_server_thread
except ImportError:
    start_web_server_thread = None
    print("⚠️ Web health server disabled (weblive not found)")

# ================= CLEANUP =================
def cleanup():
    if os.path.exists(config.DOWNLOAD_DIR):
        shutil.rmtree(config.DOWNLOAD_DIR)
    os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)

cleanup()

# ================= ARIA2 =================
aria2 = aria2p.API(
    aria2p.Client(
        host=config.ARIA2_HOST,
        port=config.ARIA2_PORT,
        secret=config.ARIA2_SECRET
    )
)

# ================= GLOBAL STATE =================
GLOBAL_STATE = {
    "ACTIVE": {},
    "DOWNLOAD_COUNT": 0,
    "UPLOAD_COUNT": 0,
    "TOTAL_DOWNLOAD_TIME": 0,
    "TOTAL_UPLOAD_TIME": 0,
    "DOWNLOAD_COUNTER": 1,
    "DOWNLOAD_DIR": config.DOWNLOAD_DIR,
}

def time_tracker():
    while True:
        if GLOBAL_STATE["DOWNLOAD_COUNT"] > 0:
            GLOBAL_STATE["TOTAL_DOWNLOAD_TIME"] += 1
        if GLOBAL_STATE["UPLOAD_COUNT"] > 0:
            GLOBAL_STATE["TOTAL_UPLOAD_TIME"] += 1
        time.sleep(1)

threading.Thread(target=time_tracker, daemon=True).start()

# ================= BOT CLIENT =================
app = Client(
    config.SESSION_NAME,
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    workers=16
)

register_handlers(app, aria2, GLOBAL_STATE)

# ================= MAIN =================
if __name__ == "__main__":
    try:
        aria2.get_stats()
        print("✅ Aria2 connected on port 6801!\n")
    except Exception:
        print("❌ Aria2 not running! Exiting.\n")
        exit(1)

    print("🤖 Bot is starting...\n")
    app.start_time = time.time()

    if start_web_server_thread:
        start_web_server_thread(config.HEALTH_PORT)

    app.run()
