#!/bin/bash

# --- Check for Aria2 installation ---
if ! command -v aria2c &> /dev/null
then
    echo "❌ ERROR: aria2c command not found. Please install Aria2."
    exit 1
fi
# ------------------------------------

# Kill everything first
echo "🔪 Killing all Aria2 and freeing ports..."
pkill -9 -f aria2c || true
fuser -k 6800/tcp 6801/tcp || true
sleep 3

# Cleanup
rm -rf downloads aria2.log aria2.session
mkdir -p downloads

# Start Aria2 on port 6801 ONLY (foreground for stability)
echo "🚀 Starting Aria2 on port 6801..."
# Use exec to replace the shell process with aria2c, allowing better signal handling.
# However, since you want to run the python script afterward, we keep '&' and put a long sleep.
aria2c \
    --enable-rpc \
    --rpc-listen-all=true \
    --rpc-allow-origin-all=true \
    --rpc-secret="gjxdml" \
    --rpc-listen-port=6801 \
    --disable-ipv6 \
    --dir=downloads \
    --max-connection-per-server=16 \
    --split=16 \
    --min-split-size=1M \
    --file-allocation=trunc \
    --disk-cache=64M \
    --log-level=info \
    --log=aria2.log &

sleep 8  # Increased slightly for stability

# Test connection with proper POST
echo "🔍 Testing Aria2 RPC..."
if curl -s -f -X POST -d '{"jsonrpc":"2.0","id":"test","method":"aria2.getVersion","params":["token:gjxdml"]}' http://localhost:6801/jsonrpc >/dev/null 2>&1; then
    echo "✅ Aria2 READY!"
    python bot.py
else
    echo "❌ Aria2 FAILED. Check logs for details."
    echo "Manual test command: curl -X POST -d '{\"jsonrpc\":\"2.0\",\"method\":\"aria2.getVersion\",\"params\":[\"token:gjxdml\"]}' http://localhost:6801/jsonrpc"
    # Added conditional check for log file existence
    if [ -f "aria2.log" ]; then
        tail -20 aria2.log
    else
        echo "Aria2 log file (aria2.log) was not created."
    fi
    exit 1
fi