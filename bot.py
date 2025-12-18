import os
import time
import asyncio
import threading
import shutil
import subprocess
from datetime import timedelta

from pyrogram import Client, filters, enums
from pyrogram.types import Message

import aria2p
from aiohttp import web

# ================= CONFIG =================
API_ID = int(os.getenv("API_ID", "18979569"))
API_HASH = os.getenv("API_HASH", "45db354387b8122bdf6c1b0beef93743")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8559651884:AAEUeSpqxunq9BE6I7cvw8ced7J0Oh3jk34")

DOWNLOAD_DIR = os.path.abspath("downloads")
ARIA2_PORT = 6801  # FIXED: Changed to 6801
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

# ================= HELPERS =================
def progress_bar(done, total, size=20):
    if total == 0:
        return "░" * size
    filled = int(done / total * size)
    return "█" * filled + "░" * (size - filled)

def time_fmt(sec):
    if not isinstance(sec, (int, float)):
        sec = 0
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s"

def format_speed(bps):
    if bps == 0:
        return "0 B/s"
    units = ['B/s', 'KB/s', 'MB/s', 'GB/s', 'TB/s', 'PB/s']
    unit = 0
    while bps >= 1024 and unit < len(units) - 1:
        bps /= 1024
        unit += 1
    return f"{bps:.1f} {units[unit]}"

# ================= BOT =================
app = Client(
    "aria2-leech-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=8
)

ACTIVE = {}

async def edit_message_async(msg, content, parse_mode):
    return await msg.edit(content, parse_mode=parse_mode)

@app.on_message(filters.command(["l", "leech"]))
async def leech(_, m: Message):
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
    ACTIVE[gid] = {"cancel": False}

    while not dl.is_complete:
        if ACTIVE[gid]["cancel"] or dl.is_removed or dl.has_failed:
            await msg.edit(f"Download {gid} finished, removed, or failed.")
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
                await msg.edit(
                    f"**📥 {dl.name}**\n"
                    f"`{progress_bar(done, total)}`\n"
                    f"{done/1024/1024:.2f}MB / {total/1024/1024:.2f}MB\n"
                    f"⬇️ Speed: {format_speed(speed)}\n"
                    f"⏱️ ETA: {eta_str}\n"
                    f"GID: `{gid}`\n"
                    f"/c_{gid} to cancel",
                    parse_mode=PARSE_MODE 
                )
            except Exception as edit_error:
                print(f"Error editing message: {edit_error}")

        await asyncio.sleep(2)

    if dl.is_complete and dl.files and dl.files[0]:
        file_path = dl.files[0].path
        
        if not file_path or not os.path.exists(file_path):
            await msg.edit("❌ Download complete but file missing.", parse_mode=None)
        else:
            try:
                file_size = os.path.getsize(file_path)
                if file_size == 0:
                    raise ValueError("File empty")
            except:
                await msg.edit("❌ File corrupted or empty.", parse_mode=None)
            else:
                try:
                    loop = asyncio.get_running_loop()
                    start_time = time.time()
                    await msg.edit("🚀 Starting upload...", parse_mode=PARSE_MODE)
                    
                    await app.send_document(
                        m.chat.id, 
                        file_path,
                        caption=f"✅ **{dl.name}**\nSize: {file_size/1024/1024:.1f}MB",
                        progress=upload_progress, 
                        progress_args=(msg, start_time, dl.name, PARSE_MODE, loop)
                    )
                    await msg.edit(f"✅ Upload complete for **{dl.name}**!", parse_mode=PARSE_MODE)
                except Exception as e:
                    print(f"Upload failed: {e}")
                    await msg.edit(f"❌ Upload failed: {str(e)}", parse_mode=None)
            
            if os.path.exists(file_path):
                await asyncio.to_thread(os.remove, file_path)
    
    elif dl.has_failed:
        await msg.edit(f"❌ Download **{dl.name}** failed.\nReason: {dl.error_message}", parse_mode=PARSE_MODE)

    ACTIVE.pop(gid, None)

@app.on_message(filters.regex(r"^/c_"))
async def cancel(_, m: Message):
    gid = m.text.replace("/c_", "")
    if gid in ACTIVE:
        ACTIVE[gid]["cancel"] = True
        try:
            dl = await asyncio.to_thread(aria2.get_download, gid)
            await asyncio.to_thread(aria2.remove, [dl], force=True)
        except:
            pass
        await m.reply(f"🛑 Cancelled GID: **{gid}**", parse_mode=enums.ParseMode.MARKDOWN)

def upload_progress(current, total, msg, start_time, name, parse_mode, loop):
    if total == 0:
        return
    elapsed = time.time() - start_time
    speed = current / elapsed if elapsed > 0 else 0
    progress_str = progress_bar(current, total)
    
    new_content = (
        f"📤 Uploading **{name}**\n"
        f"`{progress_str}`\n"
        f"{current/1024/1024:.1f}/{total/1024/1024:.1f}MB\n"
        f"⚡ {format_speed(speed)}"
    )
    
    try:
        coro = edit_message_async(msg, new_content, parse_mode)
        asyncio.run_coroutine_threadsafe(coro, loop)
        time.sleep(0.5)
    except:
        pass

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
        print("✅ Aria2 connected on port 6801!")
    except:
        print("❌ Aria2 not running!")
        exit(1)
    
    threading.Thread(target=run_health, daemon=True).start()
    app.run()
