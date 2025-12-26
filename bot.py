# bot.py

import os
import time
import threading
import shutil
import aria2p
from pyrogram import Client

# --- Modular Imports ---
# 1. IMPORT CONFIGURATION FILE
import config 
from plugins.commands import register_handlers

try:
    # We assume 'plugins.weblive' handles its own imports (like uvicorn/starlette)
    from plugins.weblive import start_web_server_thread
    UVICORN_AVAILABLE = True
except ImportError:
    print("WARNING: Could not import web server module 'plugins.weblive'. Health check will not run.")
    UVICORN_AVAILABLE = False
# -----------------------

# ================= CONFIGURATION & SETUP =================

# Use the imported configuration variables
DOWNLOAD_DIR = config.DOWNLOAD_DIR
ARIA2_PORT = config.ARIA2_PORT
ARIA2_SECRET = config.ARIA2_SECRET
HEALTH_PORT = config.HEALTH_PORT # Assuming you added HEALTH_PORT to config.py

def cleanup():
    """Removes and recreates the download directory on startup."""
    if os.path.exists(DOWNLOAD_DIR):
        print(f"Cleaning up old downloads directory: {DOWNLOAD_DIR}")
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

cleanup()

# ================= ARIA2 CLIENT =================
print("Setting up Aria2 RPC client...")
aria2 = aria2p.API(
    aria2p.Client(
        host=config.ARIA2_HOST, # Use host from config
        port=ARIA2_PORT,
        secret=ARIA2_SECRET
    )
)

# ================= GLOBAL STATE (Centralized) =================
# This dictionary will be passed to the command handlers module
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
    """Increments total time spent downloading or uploading."""
    while True:
        if GLOBAL_STATE["DOWNLOAD_COUNT"] > 0:
            GLOBAL_STATE["TOTAL_DOWNLOAD_TIME"] += 1
        if GLOBAL_STATE["UPLOAD_COUNT"] > 0:
            GLOBAL_STATE["TOTAL_UPLOAD_TIME"] += 1
        time.sleep(1)

# Start the time tracking thread
threading.Thread(target=time_tracker, daemon=True).start()

# ================= PYROGRAM BOT CLIENT =================
app = Client(
    config.SESSION_NAME, # Use SESSION_NAME from config
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    workers=16
)

# Register handlers from the external module
register_handlers(app, aria2, GLOBAL_STATE)

# ================= MAIN EXECUTION =================

if __name__ == "__main__":
    # --- Check Aria2 Connection ---
    try:
        aria2.get_stats()
        print(f"✅ Aria2 connected on {config.ARIA2_HOST}:{ARIA2_PORT}!\n")
    except Exception as e:
        print(f"❌ Aria2 not running or configuration failed! Error: {e}")
        print("Please ensure your Aria2 RPC service is running and accessible.")
        exit(1)
        
    print("🤖 Bot is starting...\n")

    # Store bot start time for uptime calculation
    app.start_time = time.time()
    
    # Start the Uvicorn/Starlette health check in a separate thread
    if UVICORN_AVAILABLE:
        print(f"🌐 Starting web server for health check on port {HEALTH_PORT}...")
        start_web_server_thread(HEALTH_PORT)
    
    # Start the bot
    app.run()
