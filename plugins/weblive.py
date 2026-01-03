# plugins/weblive.py

import threading
import asyncio
from aiohttp import web

# --- Configuration ---
DEFAULT_HEALTH_PORT = 8000


# =========================================================
# AIOHTTP HEALTH SERVER
# =========================================================

async def health_handler(request):
    """Simple health check endpoint."""
    return web.Response(text="OK")


async def aiohttp_server(port):
    app = web.Application()
    app.router.add_get("/health", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"🌐 Health check running on port {port} (aiohttp)")

    # Keep server alive forever
    while True:
        await asyncio.sleep(3600)


# =========================================================
# THREAD STARTER
# =========================================================

def start_web_server_thread(port=DEFAULT_HEALTH_PORT):
    """Start aiohttp server in a daemon thread."""

    def _run():
        asyncio.run(aiohttp_server(port))

    web_thread = threading.Thread(target=_run, daemon=True)
    web_thread.start()

    return web_thread
