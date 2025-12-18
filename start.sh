#!/bin/bash

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
    echo "❌ Aria2 FAILED. Manual test:"
    echo "curl -X POST -d '{\"jsonrpc\":\"2.0\",\"method\":\"aria2.getVersion\",\"params\":[\"token:gjxdml\"]}' http://localhost:6801/jsonrpc"
    tail -20 aria2.log
    exit 1
fi