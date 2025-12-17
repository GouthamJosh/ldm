from pyrogram import Client, filters
from bot.utils.aria2 import api

@Client.on_message(filters.regex(r"^/c_"))
async def cancel(client, message):
    gid = message.text.replace("/c_", "")
    try:
        api.remove(gid, force=True)
        await message.reply(f"Cancelled `{gid}`")
    except:
        await message.reply("Invalid GID")
