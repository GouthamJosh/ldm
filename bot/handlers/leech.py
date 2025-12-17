import os, time, asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from bot.utils.aria2 import api
from bot.config import DOWNLOAD_DIR
from bot.utils.progress import progress_bar
from bot.utils.timefmt import time_formatter

@Client.on_message(filters.command(["l", "leech"]))
async def leech(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Send URL")

    url = message.command[1]
    start = time.time()

    download = api.add_uris([url], {"dir": DOWNLOAD_DIR})
    gid = download.gid

    msg = await message.reply(f"Starting Download\nGID: `{gid}`")

    while True:
        download.update()
        if download.is_complete:
            break
        if download.is_removed:
            return

        done = download.completed_length
        total = download.total_length
        speed = download.download_speed
        eta = download.eta

        text = (
            f"📂 {download.name}\n"
            f"{progress_bar(done, total)}\n"
            f"{done/1024/1024:.2f}MB / {total/1024/1024:.2f}MB\n"
            f"🚀 {speed/1024:.1f} KB/s | ⏳ {time_formatter(eta)}\n"
            f"🆔 `{gid}`"
        )
        await msg.edit(text)
        await asyncio.sleep(3)

    file_path = download.files[0].path
    upload_start = time.time()

    await client.send_document(
        message.chat.id,
        file_path,
    )

    os.remove(file_path)

    await msg.edit(
        f"Done\n"
        f"Download: {time_formatter(time.time()-start)}\n"
        f"Upload: {time_formatter(time.time()-upload_start)}"
    )
