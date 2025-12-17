#!/bin/bash
aria2c --enable-rpc --rpc-listen-all --rpc-allow-origin-all --rpc-listen-port=6800 --continue=true --auto-file-renaming=false --file-allocation=trunc &

python -m bot.main
