import os
import asyncio
from aiohttp import web

os.environ.setdefault("DATABASE_URL", os.getenv("DATABASE_URL", ""))
os.environ["WEBAPP_URL"] = "http://localhost:8080"
os.environ["BOT_TOKEN"] = "8039427064:AAEmq3_dummy_token_for_dashboard_only"

import test_bot

async def main():
    app = await test_bot.create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 8080)
    await site.start()
    print("DASHBOARD_READY_PORT_8080")
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
