# plugins/commands.py

import os
import time
import asyncio
import subprocess
from datetime import timedelta

# NOTE: We need InlineKeyboardMarkup and InlineKeyboardButton for /status
from pyrogram import Client, filters, enums
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

# ================= Global State and Helpers (Placeholders to be set by bot.py) =================
GLOBAL_STATE = {}
ARIA2_API = None
MAX_CONCURRENT_UPLOADS = 3 # <-- NEW: Maximum number of files to upload at the same time

# --- Helper Functions ---

def progress_bar(done, total, size=12):
    FILLED = "⬢" 
    EMPTY = "⬡"
    if total == 0:
        return f"[{EMPTY * size}] 0.00%"
    percent = min(100.0, (done / total) * 100)
    filled_count = int(percent / 100 * size)
    if percent > 0 and filled_count == 0 and size > 0: filled_count = 1
    if filled_count > size: filled_count = size
    empty_count = size - filled_count
    bar = FILLED * filled_count + EMPTY * empty_count
    return f"[{bar}] {percent:.2f}%"

def time_fmt(sec):
    if not isinstance(sec, (int, float)): sec = 0
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h > 0: return f"{h}h{m}m{s}s"
    elif m > 0: return f"{m}m{s}s"
    else: return f"{s}s"

def format_speed(bps):
    if bps == 0: return "0B/s"
    units = ['B/s', 'KB/s', 'MB/s', 'GB/s', 'TB/s', 'PB/s']
    unit = 0
    while bps >= 1024 and unit < len(units) - 1:
        bps /= 1024
        unit += 1
    return f"{bps:.1f}{units[unit]}"

def format_size(b): 
    if b == 0: return "0B"
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit = 0
    while b >= 1024 and unit < len(units) - 1:
        b /= 1024
        unit += 1
    return f"{b:.2f}{units[unit]}"

# --- Async Helper Functions ---

async def edit_message_async(msg, content, parse_mode, max_retries=3, reply_markup=None):
    # Added reply_markup argument for status handler
    if msg.text == content and not reply_markup: return None
    retries = 0
    while retries < max_retries:
        try:
            return await msg.edit(content, parse_mode=parse_mode, reply_markup=reply_markup)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            retries += 1
        except Exception:
            return None
    return None

async def reply_message_async(m, text, parse_mode=None, max_retries=3, reply_markup=None):
    # Added reply_markup argument for status handler
    retries = 0
    while retries < max_retries:
        try:
            return await m.reply(text, parse_mode=parse_mode, reply_markup=reply_markup)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            retries += 1
        except Exception:
            return None
    return None

# --- Upload Progress Function (Runs in a separate thread) ---

def upload_progress(current, total, gid, start_time, name, parse_mode, loop, download_index, user_first, user_id):
    # Note: This progress function is only called when the file is actively uploading (inside the semaphore block)
    if total == 0: return
    
    if GLOBAL_STATE["ACTIVE"].get(gid, {}).get("cancel", False):
        raise Exception("Upload manually cancelled by user.")
    
    current_time = time.time()
    if current_time - GLOBAL_STATE["ACTIVE"].get(gid, {}).get("last_edit", 0) < 3:
        return
    
    elapsed = time.time() - start_time
    speed = current / elapsed if elapsed > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0
    eta_str = time_fmt(eta)
    elapsed_str = time_fmt(elapsed)
    progress_bar_output = progress_bar(current, total)
    
    new_content = (
        f"{download_index}. {name}\n"
        f"┃ {progress_bar_output}\n"
        f"┠ Processed: {format_size(current)} of {format_size(total)}\n"
        f"┠ Status: Upload | ETA: {eta_str}\n"
        f"┠ Speed: {format_speed(speed)} | Elapsed: {elapsed_str}\n"
        f"┠ Engine: Pyrogram v2\n"
        f"┠ Mode: #Leech | #qBit\n"
        f"┠ User: {user_first} | ID: {user_id}\n"
        f"┖ /cancel{download_index}_{gid}"
    )
    
    msg = GLOBAL_STATE["ACTIVE"][gid]["msg"]
    try:
        coro = edit_message_async(msg, new_content, parse_mode)
        asyncio.run_coroutine_threadsafe(coro, loop)
        GLOBAL_STATE["ACTIVE"][gid]["last_edit"] = current_time
    except:
        pass

# --- Upload Handler (Runs in the main event loop) ---

async def upload_file(app, msg, file_path, name, file_size, loop, gid, download_index, user_first, user_id):
    GLOBAL_STATE["ACTIVE"][gid]["status"] = "QUEUED" # <-- NEW: Set initial status as Queued

    # Use the semaphore to limit concurrent uploads (this line waits if MAX_CONCURRENT_UPLOADS is reached)
    async with GLOBAL_STATE["UPLOAD_SEMAPHORE"]:
        
        # Once semaphore is acquired, update status and counters
        GLOBAL_STATE["ACTIVE"][gid]["status"] = "UPLOADING" # <-- NEW: Set status to Uploading
        GLOBAL_STATE["UPLOAD_COUNT"] += 1
        try:
            await app.send_document(
                msg.chat.id, 
                file_path,
                caption=f"✅ **{name}**\nSize: {format_size(file_size)}",
                progress=upload_progress, 
                progress_args=(gid, time.time(), name, enums.ParseMode.MARKDOWN, loop, download_index, user_first, user_id)
            )
            await edit_message_async(msg, f"✅ Upload complete for **{name}**!", parse_mode=enums.ParseMode.MARKDOWN)
        
        except Exception as e:
            cancellation_message = "Upload manually cancelled by user."
            
            if cancellation_message in str(e):
                print(f"Upload GID {gid} was gracefully cancelled.")
            
            elif not GLOBAL_STATE["ACTIVE"].get(gid, {}).get("cancel", False):
                print(f"❌ Upload GID {gid} failed unexpectedly: {e}")
                await edit_message_async(msg, f"❌ Upload failed: {str(e)}", parse_mode=None)
    
    finally:
        GLOBAL_STATE["UPLOAD_COUNT"] -= 1
        GLOBAL_STATE["ACTIVE"].pop(gid, None) 
        if os.path.exists(file_path):
            await asyncio.to_thread(os.remove, file_path)

# ================= STATUS FUNCTIONS =================

def get_status_keyboard():
    """Returns an inline keyboard with a Refresh button."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh Status", callback_data="status_refresh")
        ]
    ])

def get_all_active_status(app):
    status_lines = []
    
    # Calculate Total Uptime
    uptime_sec = time.time() - app.start_time
    uptime_str = time_fmt(uptime_sec)
    
    # Summary Header
    status_lines.append("🚀 **Active Transfer Status**")
    status_lines.append("----------------------------")
    
    # System & Bot Stats
    active_download = GLOBAL_STATE.get("DOWNLOAD_COUNT", 0)
    active_upload = GLOBAL_STATE.get("UPLOAD_COUNT", 0)
    
    status_lines.append(f"🟢 **Bot Uptime**: {uptime_str}")
    status_lines.append(f"⬇️ **Active DLs**: {active_download} | ⬆️ **Active ULs**: {active_upload}")
    status_lines.append("----------------------------")

    if not GLOBAL_STATE["ACTIVE"]:
        status_lines.append("✅ No active downloads or uploads at this time.")
        return "\n".join(status_lines)

    # Detailed Task List
    for gid, task_info in GLOBAL_STATE["ACTIVE"].items():
        is_upload = "file_path" in task_info
        
        if is_upload:
            name = task_info.get("name", "Unknown Upload")
            current_status = task_info.get("status", "UPLOADING") # <-- NEW: Get current state
            
            status_emoji = "⬆️" if current_status == "UPLOADING" else "⏳"
            
            status_lines.append(f"{status_emoji} **{current_status}** - **{name}**")
            status_lines.append(f"  Status: {current_status} | /cancel_{gid}")
            
        else:
            try:
                # Aria2 Download (Fetch fresh data)
                dl = ARIA2_API.get_download(gid)
                
                if dl.is_complete or dl.is_removed or dl.has_failed:
                    continue 

                done = dl.completed_length
                total = dl.total_length
                speed = dl.download_speed
                
                progress_output = progress_bar(done, total, size=15)
                
                status_lines.append(f"⬇️ **DL** - **{dl.name}**")
                status_lines.append(f"  {progress_output} {format_size(done)}/{format_size(total)}")
                status_lines.append(f"  Speed: {format_speed(speed)} | /cancel_{gid}")
                
            except Exception:
                status_lines.append(f"⚠️ **DL** - GID `{gid}` (Status Update Failed)")
    
    return "\n".join(status_lines)


# ================= COMMAND HANDLERS =================

async def start_handler(_, m):
    PARSE_MODE = enums.ParseMode.MARKDOWN
    user_name = m.from_user.first_name
    start_message = (
        f"👋 Hello, **{user_name}**!\n"
        "I am a fast Aria2 Leech Bot designed to download files directly from URLs and upload them to Telegram.\n\n"
        "**📚 How to Use Me:**\n"
        "┠ To start a download: `/l <Direct_URL>`\n"
        "┠ To check active transfers: `/status`\n" # Updated instructions
        "┠ To view system stats: `/stats`\n"
        "┖ To cancel an active task (DL or UL): `/cancel<index>_<gid>`\n\n"
        "**ℹ️ Supported URLs:**\n"
        "┖ Direct file links (HTTP/HTTPS) and Torrent files.\n\n"
        "🚀 Happy Leeching!"
    )
    await reply_message_async(m, start_message, parse_mode=PARSE_MODE)

async def leech_handler(app, m: Message):
    if len(m.command) < 2:
        return await reply_message_async(m, "Usage:\n/l <direct_url>", parse_mode=None)

    url = m.command[1]
    
    try:
        options = {
            "dir": GLOBAL_STATE["DOWNLOAD_DIR"],
            "max-connection-per-server": "4",
            "min-split-size": "1M",
            "split": "4",
            "max-concurrent-downloads": "10"
        }
        dl = await asyncio.to_thread(ARIA2_API.add_uris, [url], options)
        gid = dl.gid
    except Exception as e:
        return await reply_message_async(m, f"Failed to start download: {e}", parse_mode=None)

    download_index = GLOBAL_STATE["DOWNLOAD_COUNTER"]
    GLOBAL_STATE["DOWNLOAD_COUNTER"] += 1

    start_time = time.time()
    msg = await reply_message_async(m, f"🚀 Starting download {download_index}\nGID: `{gid}`", parse_mode=enums.ParseMode.MARKDOWN)
    
    GLOBAL_STATE["ACTIVE"][gid] = {"cancel": False, "start_time": start_time}
    GLOBAL_STATE["DOWNLOAD_COUNT"] += 1
    
    while not dl.is_complete:
        if GLOBAL_STATE["ACTIVE"][gid]["cancel"] or dl.is_removed or dl.has_failed:
            await edit_message_async(msg, f"Download {gid} finished, removed, or failed.", parse_mode=None)
            break
            
        await asyncio.to_thread(dl.update) 
        
        done = dl.completed_length
        total = dl.total_length
        speed = dl.download_speed
        eta_sec = dl.eta.total_seconds() if isinstance(dl.eta, timedelta) else dl.eta
        
        eta_str = time_fmt(eta_sec)
        elapsed = int(time.time() - start_time)
        elapsed_str = time_fmt(elapsed)

        if not (dl.is_removed or dl.has_failed):
            try:
                await edit_message_async(
                    msg,
                    f"{download_index}. {dl.name}\n"
                    f"┃ {progress_bar(done, total)}\n" 
                    f"┠ Processed: {format_size(done)} of {format_size(total)}\n"
                    f"┠ Status: Download | ETA: {eta_str}\n"
                    f"┠ Speed: {format_speed(speed)} | Elapsed: {elapsed_str}\n"
                    f"┠ Engine: Aria2 v1.36.0\n"
                    f"┠ Mode: #Leech | #Aria2\n"
                    f"┠ Seeders: N/A | Leechers: N/A\n"
                    f"┠ User: {m.from_user.first_name} | ID: {m.from_user.id}\n"
                    f"┖ /cancel{download_index}_{gid}", 
                    parse_mode=None
                )
            except Exception: pass

        await asyncio.sleep(3)

    GLOBAL_STATE["DOWNLOAD_COUNT"] -= 1
    GLOBAL_STATE["ACTIVE"].pop(gid, None) 

    if dl.is_complete and dl.files and dl.files[0]:
        file_path = dl.files[0].path
        if not file_path or not os.path.exists(file_path):
            return await edit_message_async(msg, "❌ Download complete but file missing.", parse_mode=None)
        
        try:
            file_size = os.path.getsize(file_path)
            if file_size == 0: raise ValueError("File empty")
        except:
            return await edit_message_async(msg, "❌ File corrupted or empty.", parse_mode=None)
        
        await edit_message_async(msg, 
                                    f"✅ Download complete! Starting upload of **{dl.name}**\n"
                                    f"To cancel upload, use `/cancel{download_index}_{gid}`", 
                                    parse_mode=enums.ParseMode.MARKDOWN)
        
        # Prepare state for the upload task
        GLOBAL_STATE["ACTIVE"][gid] = {
            "cancel": False, 
            "file_path": file_path, 
            "name": dl.name, 
            "last_edit": 0, 
            "msg": msg,
            "status": "QUEUED" # <-- NEW: Set initial status as Queued
        } 
        
        loop = asyncio.get_running_loop()
        user_first = m.from_user.first_name
        user_id = m.from_user.id
        asyncio.create_task(upload_file(app, msg, file_path, dl.name, file_size, loop, gid, download_index, user_first, user_id))
    
    elif dl.has_failed:
        await edit_message_async(msg, f"❌ Download **{dl.name}** failed.\nReason: {dl.error_message}", parse_mode=enums.ParseMode.MARKDOWN)

async def cancel_handler(_, m: Message):
    text = m.text
    task_id = text.split("_", 1)[1] if "_" in text else text.replace("/cancel", "")

    if not task_id:
        return await reply_message_async(m, "Invalid cancel command.", parse_mode=None)

    if task_id in GLOBAL_STATE["ACTIVE"]:
        task_info = GLOBAL_STATE["ACTIVE"][task_id]
        task_info["cancel"] = True
        
        if "file_path" in task_info:
            # --- UPLOAD CANCELLATION ---
            file_path = task_info.get("file_path")
            if file_path and os.path.exists(file_path):
                await asyncio.to_thread(os.remove, file_path)
            await reply_message_async(m, f"🛑 Cancelled Upload **{task_info['name']}**.\nFile deleted.", parse_mode=enums.ParseMode.MARKDOWN)
        
        else:
            # --- DOWNLOAD CANCELLATION (Enhanced cleanup logic) ---
            file_path_to_delete = None
            try:
                dl = await asyncio.to_thread(ARIA2_API.get_download, task_id)
                
                if dl and dl.files and dl.files[0] and dl.files[0].path:
                    file_path_to_delete = dl.files[0].path

                await asyncio.to_thread(ARIA2_API.remove, [dl], force=True)
                
            except Exception as e:
                print(f"Aria2 remove failed for GID {task_id}: {e}")
            
            if file_path_to_delete:
                main_file_path = str(file_path_to_delete)
                temp_file_path = main_file_path + '.aria2'
                
                if os.path.exists(main_file_path):
                    await asyncio.to_thread(os.remove, main_file_path)
                    print(f"Manually deleted main file: {main_file_path}")
                
                if os.path.exists(temp_file_path):
                    await asyncio.to_thread(os.remove, temp_file_path)
                    print(f"Manually deleted temp file: {temp_file_path}")
            
            await reply_message_async(m, f"🛑 Cancelled Download GID: **{task_id}**", parse_mode=enums.ParseMode.MARKDOWN)
            
    else:
        await reply_message_async(m, f"Task ID **{task_id}** not found or already complete.", parse_mode=enums.ParseMode.MARKDOWN)


async def status_handler(app, m: Message):
    """Handles the /status command, showing all active tasks."""
    status_text = await asyncio.to_thread(get_all_active_status, app)
    keyboard = get_status_keyboard()
    await reply_message_async(m, status_text, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=keyboard)


async def status_callback_handler(app, cq: CallbackQuery):
    """Handles the callback query from the Refresh button."""
    if cq.data == "status_refresh":
        new_status_text = await asyncio.to_thread(get_all_active_status, app)
        keyboard = get_status_keyboard()
        
        try:
            # Use edit_message_text for callback query to update the existing message
            await cq.edit_message_text(new_status_text, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=keyboard)
            await cq.answer("Status refreshed successfully!")
        except FloodWait as e:
            await cq.answer(f"Flood control: Try again in {e.value}s.", show_alert=True)
        except Exception:
            # This handles cases where the message is too old or the text hasn't changed.
            await cq.answer("Status message could not be refreshed (too old or unchanged).", show_alert=False)


async def stats_handler(app, m: Message):
    # ================= 1. System Stats (Subprocess) =================
    
    cpu_percent = "N/A"
    ram_usage = "N/A"
    disk_info = "Disk info unavailable"
    
    # Get CPU Load
    try:
        cpu_result = subprocess.run(["sh", "-c", "top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'"], capture_output=True, text=True, timeout=5, check=True)
        if cpu_result.returncode == 0:
            cpu_percent = f"{float(cpu_result.stdout.strip()):.1f}%"
    except Exception: pass

    # Get RAM Usage
    try:
        ram_result = subprocess.run(["sh", "-c", "free -m | awk 'NR==2{printf \"%.1f%%\", $3*100/$2 }'"], capture_output=True, text=True, timeout=5, check=True)
        if ram_result.returncode == 0:
            ram_usage = ram_result.stdout.strip()
    except Exception: pass

    # Get Disk Usage
    try:
        df_result = subprocess.run(["df", "-h", "--output=size,avail,pcent", GLOBAL_STATE["DOWNLOAD_DIR"]], capture_output=True, text=True, timeout=5, check=True)
        if df_result.returncode == 0:
            df_output_lines = df_result.stdout.strip().split('\n')
            if len(df_output_lines) > 1:
                df_data = df_output_lines[1].split() 
                if len(df_data) >= 3:
                    total_disk, free_disk, disk_percent = df_data[0], df_data[1], df_data[2]
                    disk_info = f"F: {free_disk} | T: {total_disk} [{disk_percent}]"
    except Exception: pass

    # ================= 2. Bot State and Time =================

    uptime_sec = time.time() - app.start_time
    uptime_str = time_fmt(uptime_sec)
    
    total_dl_str = GLOBAL_STATE.get("TOTAL_DOWNLOAD_TIME", "0s")
    total_ul_str = GLOBAL_STATE.get("TOTAL_UPLOAD_TIME", "0s")

    active_download = GLOBAL_STATE.get("DOWNLOAD_COUNT", 0)
    active_upload = GLOBAL_STATE.get("UPLOAD_COUNT", 0)
    
    # ================= 3. Build Message =================

    stats_text = (
        "🤖 **Bot Status Report**\n"
        "--- System Metrics ---\n"
        f"┠ CPU Load: **{cpu_percent}**\n"
        f"┠ RAM Usage: **{ram_usage}**\n"
        f"┖ Disk: **{disk_info}**\n"
        "\n"
        "--- Transfer Activity ---\n"
        f"┠ Active DLs: **{active_download}**\n"
        f"┖ Active ULs: **{active_upload}**\n"
        "\n"
        "--- Cumulative Stats ---\n"
        f"┠ Total DL Time: **{total_dl_str}**\n"
        f"┠ Total UL Time: **{total_ul_str}**\n"
        f"┖ Bot Uptime: **{uptime_str}**"
    )
    
    await reply_message_async(m, stats_text, parse_mode=enums.ParseMode.MARKDOWN)

# ================= REGISTRATION FUNCTION =================

def register_handlers(app, aria2_api, state_vars):
    """
    Registers all command handlers to the Pyrogram client instance and sets 
    the necessary global variables in this module.
    """
    global ARIA2_API, GLOBAL_STATE

    ARIA2_API = aria2_api
    GLOBAL_STATE = state_vars
    
    # <-- NEW: Initialize the upload semaphore to limit concurrent uploads
    GLOBAL_STATE["UPLOAD_SEMAPHORE"] = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)
    
    # --- Handlers that only need the default args (client, message/callback) ---
    app.on_message(filters.command("start"))(start_handler)
    app.on_message(filters.regex(r"^/cancel"))(cancel_handler)
    app.on_callback_query()(status_callback_handler) # Register the callback handler
    
    # --- Handlers that are defined to take (app, message) args (using wrappers) ---
    
    @app.on_message(filters.command(["l", "leech"]))
    async def leech_wrapper(client, message):
        await leech_handler(client, message)

    @app.on_message(filters.command("status")) # Add /status command
    async def status_wrapper(client, message):
        await status_handler(client, message)

    @app.on_message(filters.command("stats"))
    async def stats_wrapper(client, message):
        await stats_handler(client, message)
