# 🚀 Aria2 Leech Telegram Bot

**A high-performance Telegram bot built with Pyrogram and integrated with Aria2 for fast, direct-link downloading (leeching) and seamless uploading to Telegram chats.**

[![Repo Owner](https://img.shields.io/badge/Developer-Goutham%20Josh-blue.svg?style=for-the-badge&logo=telegram)](https://t.me/im_goutham_josh)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

<br>
<p align="center">
  <img src="https://img.shields.io/badge/Fork%20this%20light-weight%20repo%20⭐-Click%20here-blue?style=for-the-badge&logo=github" alt="Fork Repo">
</p>
<br>

## ✨ Features

- **⚡ Fast Downloading**: Utilizes **Aria2** for high-speed, multi-connection downloads
- **📊 Real-time Progress**: Live updates with speed, ETA, and interactive progress bars (Download → Upload)
- **📋 Consolidated Status** (`/status`): View all active downloads/uploads in a single refreshable message
- **🔄 Concurrent Tasks**: Multiple simultaneous downloads/uploads using threading & asyncio
- **💻 System Stats** (`/stats`): CPU, RAM, Disk usage, and bot activity metrics
- **❌ Cancellation**: Gracefully cancel active download/upload tasks
- **🩺 Health Check**: Web endpoint for cloud deployment monitoring

## ⚙️ Prerequisites

- Telegram API credentials (`API_ID` & `API_HASH`)
- Telegram Bot Token (`BOT_TOKEN`)
- Running **Aria2 RPC** daemon
- Python 3.10+ environment

## 🛠️ Deployment Options

### 🚀 1. Docker (Recommended - Local & Cloud)

**A. Build the Docker Image**
git clone https://github.com/GouthamJosh/aria-tg
cd aria-tg
docker build -t aria2-leech-bot .

text

**B. Run the Container**
<br>
docker run -d<br>
--name aria2-leech<br>
-e API_ID="YOUR_API_ID"<br>
-e API_HASH="YOUR_API_HASH"<br>
-e BOT_TOKEN="YOUR_BOT_TOKEN"<br>
-e OWNER_ID="YOUR_OWNER_ID"<br>
-e ARIA2_HOST="127.0.0.1"<br>
-e ARIA2_PORT="6801"<br>
-e ARIA2_SECRET="gjxdml"<br>
-e PORT="8000"<br>
-p 8000:8000<br><br>


### 📱 2. Termux (Android)

**A. Install Dependencies**<br><br>
pkg update && pkg upgrade<br>
pkg install -y git python aria2
<br>

**B. Clone & Setup**<br>
aria2-leech-bot<br>

**C. Start Aria2 RPC** (in separate Termux session)
aria2c --enable-rpc --rpc-listen-all --rpc-secret=gjxdml --rpc-port=6801 -D<br><br>

**D. Run Bot**
bash start.sh<br><br>


### ☁️ 3. Cloud Platforms (Heroku/Render/Railway)

1. Fork the repository
2. Set environment variables in platform dashboard
3. Deploy with Docker support

## 🔧 Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `API_ID` | Telegram API ID | `12345678` |
| `API_HASH` | Telegram API Hash | `your_api_hash` |
| `BOT_TOKEN` | BotFather token | `123456:ABC-DEF...` |
| `OWNER_ID` | Your Telegram user ID | `123456789` |
| `ARIA2_HOST` | Aria2 RPC host | `127.0.0.1` |
| `ARIA2_PORT` | Aria2 RPC port | `6801` |
| `ARIA2_SECRET` | Aria2 RPC secret | `gjxdml` |
| `PORT` | Web server port | `8000` |

## 📚 Commands

- `/start` - Bot information
- `/status` - Active downloads/uploads
- `/stats` - System statistics
- `/cancel` - Cancel current task

## 🤝 Credits

**Maintained by [Goutham Josh](https://t.me/im_goutham_josh)**  
⭐ **Star this repo if it helps you!**

![Star History](https://star-history.com/#GouthamJosh/aria-tg&Date)
