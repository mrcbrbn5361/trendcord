import discord
import asyncio
import logging
from discord.ext import commands, tasks
from config import config
from database import Database
from scraper import TrendyolScraper

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("Trendcord")


class TrendcordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(
            command_prefix=config.COMMAND_PREFIX,
            intents=intents,
            help_command=None
        )
        self.db = Database(config.DATABASE_URL)
        self.scraper = TrendyolScraper()

    async def setup_hook(self):
        # Load cogs
        await self.load_extension("cogs.product_commands")
        await self.load_extension("cogs.maintenance")
        logger.info("Cog'lar yüklendi")

    async def on_ready(self):
        logger.info(f"Sistem Hazır: {self.user.name} | ID: {self.user.id}")
        if not check_prices.is_running():
            check_prices.start()


bot = TrendcordBot()


@tasks.loop(minutes=config.SCRAPE_INTERVAL_MINUTES)
async def check_prices():
    """Background price checking task."""
    products = await bot.db.get_all_products()
    if not products:
        return

    for p in products:
        try:
            data = await asyncio.get_event_loop().run_in_executor(
                None, bot.scraper.scrape_product, p["url"]
            )
            
            if data and data.get("success"):
                old_price = p["current_price"]
                new_price = data.get("current_price", 0)
                
                if abs(new_price - old_price) > 0.01 and new_price > 0 and old_price > 0:
                    await bot.db.update_product_price(p["product_id"], new_price)
                    
                    channel = bot.get_channel(int(p.get("channel_id", 0)))
                    if channel:
                        color = 0x10B981 if new_price < old_price else 0xEF4444
                        embed = discord.Embed(
                            title="📊 Fiyat Güncellemesi",
                            url=p["url"],
                            color=color
                        )
                        embed.add_field(name="Ürün", value=p["name"][:100], inline=False)
                        embed.add_field(name="Eski Fiyat", value=f"~~{old_price:.2f} TL~~", inline=True)
                        embed.add_field(name="Yeni Fiyat", value=f"**{new_price:.2f} TL**", inline=True)
                        
                        await channel.send(content=f"<@{p['user_id']}>", embed=embed)
                        await asyncio.sleep(0.5)
            
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Hata ({p.get('product_id', 'Bilinmiyor')}): {e}")


async def main():
    if not config.DISCORD_TOKEN:
        logger.critical("DISCORD_TOKEN bulunamadı!")
        return

    try:
        await bot.start(config.DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Bot hatası: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot kapatıldı")
