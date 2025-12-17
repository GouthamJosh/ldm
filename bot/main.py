from pyrogram import Client
from bot.config import API_ID, API_HASH, BOT_TOKEN
from bot.utils.cleanup import clean_all

clean_all()

app = Client(
    "aria2-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

app.run()
