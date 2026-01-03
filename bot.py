# bot.py

import os
import time
import threading
import shutil
import aria2p
from pyrogram import Client

# --- Modular Imports ---
from plugins.commands import register_handlers

try:
    from plugins.weblive import start_web_server_thread
except ImportError:
    start_web_server_thread = None
    print("⚠️ Web health server disabled (weblive not found)")

# ================= CONFIG =================
API_ID = int(os.getenv("API_ID", "18979569"))
API_HASH = os.getenv("API_HASH", "45db354387b8122bdf6c1b0beef93743")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8559651884:AAEUeSpqxunq9BE6I7cvw8ced7J0Oh3jk34")

PORT = int(os.environ.get("PORT", 8000))

DOWNLOAD_DIR = os.path.abspath("downloads")
ARIA2_PORT = 6801
ARIA2_SECRET = "gjxdml"

# ================= CLEANUP =================
def cleanup():
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

cleanup()

# ================= ARIA2 =================
aria2 = aria2p.API(
    aria2p.Client(
        host="http://localhost",
        port=ARIA2_PORT,
        secret=ARIA2_SECRET
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
    "DOWNLOAD_DIR": DOWNLOAD_DIR,
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
    "aria2-leech-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
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
        start_web_server_thread(PORT)

    app.run()
