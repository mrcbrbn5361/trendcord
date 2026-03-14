import discord
from discord.ext import commands, tasks
import asyncio
import os
import logging
import dotenv
from datetime import datetime
import traceback

from database import Database
from scraper import TrendyolScraper

dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('PREFIX', '!')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 3600))
PROXY_ENABLED = os.getenv('PROXY_ENABLED', 'True').lower() == 'true'
DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/trendyol_tracker.sqlite')

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, case_insensitive=True, help_command=None)

bot.db = Database(db_name=DATABASE_PATH)
bot.scraper = TrendyolScraper(use_proxy=PROXY_ENABLED)

@bot.event
async def on_ready():
    logger.info(f'Bot {bot.user.name} olarak giriş yaptı')
    await load_cogs()
    try:
        await bot.tree.sync()
        logger.info("Slash komutları senkronize edildi.")
    except Exception as e:
        logger.error(f"Slash senkronizasyon hatası: {e}")

    if not check_prices.is_running():
        check_prices.start()

async def load_cogs():
    cogs_dir = os.path.abspath("cogs")
    for filename in os.listdir(cogs_dir):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                logger.info(f"Cog yüklendi: {filename}")
            except Exception as e:
                logger.error(f"Cog yükleme hatası {filename}: {e}")

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_prices():
    logger.info("Fiyat kontrolü başlıyor...")
    products = bot.db.get_all_products()

    for product in products:
        try:
            product_data = bot.scraper.scrape_product(product['url'])
            if not product_data or not product_data.get('success'):
                continue

            old_price = product['current_price']
            new_price = product_data['current_price']

            if new_price is not None and old_price != new_price:
                bot.db.update_product_price(product['product_id'], new_price)

                # Aboneleri bilgilendir
                subscriptions = bot.db.get_subscriptions_for_product(product['product_id'])
                for sub in subscriptions:
                    try:
                        channel_id = sub.get('channel_id')
                        user_id = sub.get('user_id')

                        if channel_id:
                            channel = bot.get_channel(int(channel_id))
                            if channel:
                                embed = discord.Embed(
                                    title="💸 Fiyat Değişimi Bildirimi",
                                    url=product['url'],
                                    color=discord.Color.green() if new_price < old_price else discord.Color.red()
                                )
                                embed.set_author(name=product['name'])
                                if product.get('image_url'):
                                    embed.set_thumbnail(url=product['image_url'])

                                diff = new_price - old_price
                                perc = abs(diff / old_price * 100) if old_price != 0 else 0

                                if diff < 0:
                                    txt = f"🔽 **Fiyat Düştü!**\n{old_price:.2f} TL ➡️ {new_price:.2f} TL\n📉 {abs(diff):.2f} TL düşüş (-%{perc:.1f})"
                                else:
                                    txt = f"🔼 **Fiyat Arttı!**\n{old_price:.2f} TL ➡️ {new_price:.2f} TL\n📈 {diff:.2f} TL artış (+%{perc:.1f})"

                                embed.description = txt
                                await channel.send(content=f"<@{user_id}> takip ettiğin ürünün fiyatı değişti!", embed=embed)
                    except Exception as e:
                        logger.error(f"Bildirim hatası: {e}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Ürün kontrol hatası {product['product_id']}: {e}")

@check_prices.before_loop
async def before_check_prices():
    await bot.wait_until_ready()

if __name__ == "__main__":
    bot.run(TOKEN)
