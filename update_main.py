import re

file_path = 'main.py'
with open(file_path, 'r') as f:
    content = f.read()

# Add imports
content = content.replace(
    'from scraper import TrendyolScraper',
    'from scraper import TrendyolScraper\nimport uvicorn\nfrom web.app import app as web_app, set_instances'
)

# Set instances
content = content.replace(
    'bot.scraper = TrendyolScraper(use_proxy=PROXY_ENABLED, verify_ssl=VERIFY_SSL)',
    'bot.scraper = TrendyolScraper(use_proxy=PROXY_ENABLED, verify_ssl=VERIFY_SSL)\n\n# Web app instance\'larını set et\nset_instances(bot, bot.db)'
)

# Update main block
old_main = r'''if __name__ == "__main__":
    if not TOKEN:
        logger.error("Discord token bulunamadı! Lütfen .env dosyasına DISCORD_TOKEN ekleyin.")
        exit(1)
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"Bot başlatılırken hata oluştu: {e}")
        traceback.print_exc()'''

new_main = r'''async def run_bot():
    if not TOKEN:
        logger.error("Discord token bulunamadı! Lütfen .env dosyasına DISCORD_TOKEN ekleyin.")
        return

    try:
        async with bot:
            await bot.start(TOKEN)
    except Exception as e:
        logger.error(f"Bot başlatılırken hata oluştu: {e}")
        traceback.print_exc()

async def run_web():
    port = int(os.getenv("PORT", 8000))
    config = uvicorn.Config(web_app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main_all():
    # Bot ve Web sunucusunu aynı anda çalıştır
    await asyncio.gather(
        run_bot(),
        run_web()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main_all())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Sistem başlatılırken hata oluştu: {e}")
        traceback.print_exc()'''

content = content.replace(old_main, new_main)

with open(file_path, 'w') as f:
    f.write(content)
