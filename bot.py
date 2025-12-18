import os
import time
import asyncio
import threading
import shutil
import subprocess
from datetime import timedelta

from pyrogram import Client, filters, enums
from pyrogram.types import Message
from pyrogram.errors import FloodWait

import aria2p
from aiohttp import web

# ================= CONFIG =================
API_ID = int(os.getenv("API_ID", "18979569"))
API_HASH = os.getenv("API_HASH", "45db354387b8122bdf6c1b0beef93743")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8559651884:AAEUeSpqxunq9BE6I7cvw8ced7J0Oh3jk34")

DOWNLOAD_DIR = os.path.abspath("downloads")
ARIA2_PORT = 6801
HEALTH_PORT = int(os.getenv("PORT", 8000))
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
ACTIVE = {} # Tracks GID (download) or msg.id (upload)
DOWNLOAD_IN_PROGRESS = False
UPLOAD_IN_PROGRESS = False
TOTAL_DOWNLOAD_TIME = 0
TOTAL_UPLOAD_TIME = 0

def time_tracker():
    """Increments total time spent downloading or uploading."""
    global TOTAL_DOWNLOAD_TIME, TOTAL_UPLOAD_TIME
    while True:
        if DOWNLOAD_IN_PROGRESS:
            TOTAL_DOWNLOAD_TIME += 1
        if UPLOAD_IN_PROGRESS:
            TOTAL_UPLOAD_TIME += 1
        time.sleep(1)

# Start the time tracking thread
threading.Thread(target=time_tracker, daemon=True).start()


# ================= HELPERS =================
def progress_bar(done, total, size=12):
    """Generates a 12-segment hexagonal progress bar string."""
    FILLED = "⬢" # Filled hexagon
    EMPTY = "⬡"  # Empty hexagon
    
    if total == 0:
        return f"[{EMPTY * size}] 0.00%"
        
    percent = min(100.0, (done / total) * 100)
    filled_count = int(percent / 100 * size)
    
    if percent > 0 and filled_count == 0 and size > 0:
        filled_count = 1
        
    if filled_count > size:
        filled_count = size
        
    empty_count = size - filled_count
    bar = FILLED * filled_count + EMPTY * empty_count
    
    return f"[{bar}] {percent:.2f}%"

def time_fmt(sec):
    # This helper is used for ETA and total time display
    if not isinstance(sec, (int, float)):
        sec = 0
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    
    # Format h/m/s for total time: Hh Mm Ss
    if h > 0:
        return f"{h}h{m}m{s}s"
    elif m > 0:
        return f"{m}m{s}s"
    else:
        return f"{s}s"

def format_speed(bps):
    if bps == 0:
        return "0 B/s"
    units = ['B/s', 'KB/s', 'MB/s', 'GB/s', 'TB/s', 'PB/s']
    unit = 0
    while bps >= 1024 and unit < len(units) - 1:
        bps /= 1024
        unit += 1
    return f"{bps:.1f} {units[unit]}"

def format_size(b): 
    if b == 0:
        return "0 B"
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit = 0
    while b >= 1024 and unit < len(units) - 1:
        b /= 1024
        unit += 1
    return f"{b:.2f} {units[unit]}"

# ================= BOT =================
app = Client(
    "aria2-leech-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=8
)

async def edit_message_async(msg, content, parse_mode):
    try:
        return await msg.edit(content, parse_mode=parse_mode)
    except FloodWait as e:
        print(f"Hit FloodWait in edit_message_async: Waiting for {e.value} seconds...")
        await asyncio.sleep(e.value)
        return await msg.edit(content, parse_mode=parse_mode)
    except Exception as edit_error:
        print(f"Error editing message: {edit_error}")
        return None


@app.on_message(filters.command(["l", "leech"]))
async def leech(_, m: Message):
    global DOWNLOAD_IN_PROGRESS, UPLOAD_IN_PROGRESS
    PARSE_MODE = enums.ParseMode.MARKDOWN

    if len(m.command) < 2:
        return await m.reply("Usage:\n/l <direct_url>", parse_mode=None)

    url = m.command[1]
    
    try:
        options = {
            "dir": DOWNLOAD_DIR,
            "max-connection-per-server": "4",
            "min-split-size": "1M",
            "split": "4",
            "max-concurrent-downloads": "10"
        }
        dl = await asyncio.to_thread(aria2.add_uris, [url], options)
        gid = dl.gid
    except Exception as e:
        print(f"Aria2 Add URI Failed: {e}")
        return await m.reply(f"Failed to start download: {e}", parse_mode=None)

    msg = await m.reply(f"🚀 Starting download\nGID: `{gid}`", parse_mode=PARSE_MODE)
    # Store GID and cancel flag for download phase
    ACTIVE[gid] = {"cancel": False}
    
    DOWNLOAD_IN_PROGRESS = True # Set download flag

    while not dl.is_complete:
        if ACTIVE[gid]["cancel"] or dl.is_removed or dl.has_failed:
            await edit_message_async(msg, f"Download {gid} finished, removed, or failed.", parse_mode=None)
            break
            
        await asyncio.to_thread(dl.update) 
        
        done = dl.completed_length
        total = dl.total_length
        speed = dl.download_speed
        eta = dl.eta

        if isinstance(eta, timedelta):
            eta_seconds = eta.total_seconds()
        else:
            eta_seconds = eta
        
        eta_str = time_fmt(eta_seconds)

        if not (dl.is_removed or dl.has_failed):
            try:
                # --- DOWNLOAD MESSAGE TEMPLATE (USING GID FOR CANCEL) ---
                await edit_message_async(
                    msg,
                    f"**📥 DOWNLOADING: {dl.name}**\n"
                    f"┟ `{progress_bar(done, total)}`\n" 
                    f"┠ Processed → {format_size(done)} of {format_size(total)}\n"
                    f"┠ Speed → **{format_speed(speed)}**\n"
                    f"┠ ETA → **{eta_str}**\n"
                    f"┟ GID → `{gid}`\n"
                    f"┖ /c_{gid} to cancel", 
                    parse_mode=PARSE_MODE
                )
                # --- END DOWNLOAD MESSAGE TEMPLATE ---
            except Exception as edit_error:
                print(f"Error editing message: {edit_error}")

        await asyncio.sleep(3) # Throttle edits to avoid FloodWait

    # Download finished, reset flag
    DOWNLOAD_IN_PROGRESS = False 
    
    # Remove GID from active tasks after download is done/failed
    ACTIVE.pop(gid, None) 

    if dl.is_complete and dl.files and dl.files[0]:
        file_path = dl.files[0].path
        
        if not file_path or not os.path.exists(file_path):
            await edit_message_async(msg, "❌ Download complete but file missing.", parse_mode=None)
        else:
            try:
                file_size = os.path.getsize(file_path)
                if file_size == 0:
                    raise ValueError("File empty")
            except:
                await edit_message_async(msg, "❌ File corrupted or empty.", parse_mode=None)
            else:
                try:
                    loop = asyncio.get_running_loop()
                    start_time = time.time()
                    
                    # --- TRANSITION MESSAGE ---
                    await edit_message_async(msg, 
                                             f"✅ Download complete! Starting upload of **{dl.name}**\n"
                                             f"To cancel upload, use `/c_{msg.id}`", 
                                             parse_mode=PARSE_MODE)
                    # --- END TRANSITION MESSAGE ---
                    
                    # Store message ID, file path, and cancel flag for upload phase tracking
                    ACTIVE[msg.id] = {"cancel": False, "file_path": file_path, "name": dl.name}
                    
                    UPLOAD_IN_PROGRESS = True # Set upload flag
                    
                    await app.send_document(
                        m.chat.id, 
                        file_path,
                        caption=f"✅ **{dl.name}**\nSize: {format_size(file_size)}",
                        progress=upload_progress, 
                        progress_args=(msg, start_time, dl.name, PARSE_MODE, loop)
                    )
                    
                    # If upload completes successfully
                    await edit_message_async(msg, f"✅ Upload complete for **{dl.name}**!", parse_mode=PARSE_MODE)
                
                except Exception as e:
                    print(f"Upload failed: {e}")
                    
                    # --- FIX: Skip final error message if manual cancel occurred ---
                    if not ACTIVE.get(msg.id, {}).get("cancel", False):
                        await edit_message_async(msg, f"❌ Upload failed: {str(e)}", parse_mode=None)
            
                finally:
                    UPLOAD_IN_PROGRESS = False # Reset upload flag
                    # Clean up the entry from ACTIVE
                    ACTIVE.pop(msg.id, None) 
            
            if os.path.exists(file_path):
                await asyncio.to_thread(os.remove, file_path)
    
    elif dl.has_failed:
        await edit_message_async(msg, f"❌ Download **{dl.name}** failed.\nReason: {dl.error_message}", parse_mode=PARSE_MODE)


@app.on_message(filters.regex(r"^/c_"))
async def cancel(_, m: Message):
    global UPLOAD_IN_PROGRESS
    task_id = m.text.replace("/c_", "")

    # Check if task_id is a GID (typically 6-character hex) AND is currently an active download
    if len(task_id) == 6 and task_id in ACTIVE and "file_path" not in ACTIVE.get(task_id, {}): 
        
        # --- ARIA2 DOWNLOAD CANCELLATION (using GID) ---
        ACTIVE[task_id]["cancel"] = True
        try:
            dl = await asyncio.to_thread(aria2.get_download, task_id)
            await asyncio.to_thread(aria2.remove, [dl], force=True)
            await m.reply(f"🛑 Cancelled Download GID: **{task_id}**", parse_mode=enums.ParseMode.MARKDOWN)
        except Exception as e:
             await m.reply(f"🛑 Could not cancel GID **{task_id}**: {e}", parse_mode=enums.ParseMode.MARKDOWN)
    
    # Check if task_id is a Message ID (purely numeric) AND is currently an active upload
    elif task_id.isdigit() and int(task_id) in ACTIVE and "file_path" in ACTIVE.get(int(task_id), {}):
        
        # --- PYROGRAM UPLOAD CANCELLATION (using msg.id) ---
        msg_id = int(task_id)
        task_info = ACTIVE[msg_id]
        
        # 1. Set the cancel flag
        task_info["cancel"] = True
        
        # 2. Delete the file immediately
        file_path = task_info.get("file_path")
        if file_path and os.path.exists(file_path):
            await asyncio.to_thread(os.remove, file_path)
            
        # 3. Inform the user and reset upload flag
        UPLOAD_IN_PROGRESS = False
        await m.reply(f"🛑 Cancelled Upload **{task_info['name']}**.\nFile deleted.", parse_mode=enums.ParseMode.MARKDOWN)
        
    else:
        await m.reply(f"Task ID **{task_id}** not found or already complete.", parse_mode=enums.ParseMode.MARKDOWN)

def upload_progress(current, total, msg, start_time, name, parse_mode, loop):
    if total == 0:
        return
    
    # --- CANCELLATION CHECK (must raise an exception to stop pyrogram's upload) ---
    if ACTIVE.get(msg.id, {}).get("cancel", False):
        # This exception stops the Pyrogram thread immediately.
        raise Exception("Upload manually cancelled by user.")
    # --- END CANCELLATION CHECK ---

    elapsed = time.time() - start_time
    speed = current / elapsed if elapsed > 0 else 0
    progress_bar_output = progress_bar(current, total)
    
    # --- UPLOAD MESSAGE TEMPLATE ---
    new_content = (
        f"**📤 UPLOADING: {name}**\n"
        f"┟ `{progress_bar_output}`\n"
        f"┠ Processed → {format_size(current)} of {format_size(total)}\n"
        f"┖ Speed → **{format_speed(speed)}**"
    )
    # --- END UPLOAD MESSAGE TEMPLATE ---
    
    try:
        coro = edit_message_async(msg, new_content, parse_mode)
        asyncio.run_coroutine_threadsafe(coro, loop)
        time.sleep(3) # Throttle edits to avoid FloodWait
    except:
        pass

@app.on_message(filters.command("stats"))
async def bot_stats(_, m: Message):
    # This command uses os.popen to run system commands, which is environment dependent.
    # It attempts to get CPU, RAM, and Uptime from standard Linux commands.
    
    # Get system stats
    cpu_percent = os.popen("top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'").read().strip()
    ram_usage = os.popen("free -m | awk 'NR==2{printf \"%.1f%%\", $3*100/$2 }'").read().strip()
    
    # Get total free space on the current filesystem
    try:
        df_output = os.popen(f"df -h --output=size,avail,pcent {DOWNLOAD_DIR} | tail -n 1").read().strip().split()
        if len(df_output) == 3:
            total_disk = df_output[0]
            free_disk = df_output[1]
            disk_percent = df_output[2]
            disk_info = f"F → {free_disk} of {total_disk} [{disk_percent}]"
        else:
            disk_info = "Disk info unavailable"
    except Exception as e:
        print(f"Disk check failed: {e}")
        disk_info = "Disk info unavailable"

    # Get uptime
    uptime_sec = time.time() - app.start_time
    uptime_str = time_fmt(uptime_sec)
    
    # Format total cumulative times
    total_dl_str = time_fmt(TOTAL_DOWNLOAD_TIME)
    total_ul_str = time_fmt(TOTAL_UPLOAD_TIME)

    stats_text = (
        "⌬ **Bot Stats**\n"
        f"┠ CPU → **{cpu_percent}%** | {disk_info}\n"
        f"┖ RAM → **{ram_usage}** | UP → **{uptime_str}**\n"
        "--- Transfer Times ---\n"
        f"┠ DL Time → **{total_dl_str}**\n"
        f"┖ UL Time → **{total_ul_str}**"
    )
    
    await m.reply_text(stats_text, parse_mode=enums.ParseMode.MARKDOWN)


async def health(request):
    return web.Response(text="OK")

async def start_health():
    apph = web.Application()
    apph.router.add_get("/health", health)
    runner = web.AppRunner(apph)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HEALTH_PORT)
    await site.start()

def run_health():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_health())
    loop.run_forever()

if __name__ == "__main__":
    try:
        aria2.get_stats()
        print("✅ Aria2 connected on port 6801!\n")
    except:
        print("❌ Aria2 not running!\n")
        exit(1)
    
    print("🤖 Bot is starting...\n")
    print("🚀 Starting health check server...\n")
    print(f"🌐 Health check available at http://localhost:{HEALTH_PORT}/\n")
    print("📥 Download directory:\n", DOWNLOAD_DIR)
    print("-----------------------------------")
    print("Bot is now running!\n")
    print("-----------------------------------\n")
    print("Developed by Goutham Josh : )\n")
    print("-----------------------------------\n")
    # Store bot start time for uptime calculation
    app.start_time = time.time()
    
    threading.Thread(target=run_health, daemon=True).start()
    app.run()
