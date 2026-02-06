# main.py (ilgili kısımlar)

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
import uvicorn
from web.app import app as web_app, set_instances

dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('PREFIX', '!')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 3600))
PROXY_ENABLED = os.getenv('PROXY_ENABLED', 'True').lower() == 'true'
VERIFY_SSL = os.getenv('VERIFY_SSL', 'True').lower() == 'true'
DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/trendyol_tracker.sqlite')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, case_insensitive=True, help_command=None)

# Database ve Scraper instance'larını bot objesine ata
bot.db = Database(db_name=DATABASE_PATH)
bot.scraper = TrendyolScraper(use_proxy=PROXY_ENABLED, verify_ssl=VERIFY_SSL)

# Web app instance'larını set et
set_instances(bot, bot.db)

@bot.event
async def on_ready():
    logger.info(f'Bot {bot.user.name} olarak giriş yaptı')
    logger.info(f'Bot ID: {bot.user.id}')

    await load_cogs()

    try:
        # Global senkronizasyon
        synced = await bot.tree.sync()
        logger.info(f"{len(synced)} slash komutu global olarak senkronize edildi.")
        # Test için belirli bir sunucuya senkronize etmek isterseniz:
        # GUILD_ID = YOUR_TEST_GUILD_ID # Buraya test sunucunuzun ID'sini yazın
        # guild = discord.Object(id=GUILD_ID)
        # await bot.tree.sync(guild=guild)
        # logger.info(f"Slash komutları {GUILD_ID} sunucusuna senkronize edildi.")
    except Exception as e:
        logger.error(f"Slash komutları senkronize edilirken hata: {e}")
        traceback.print_exc()

    if not check_prices.is_running():
        check_prices.start()
        logger.info(f"Fiyat kontrolü başlatıldı. Kontrol aralığı: {CHECK_INTERVAL} saniye")

async def load_cogs():
    cogs_dir = os.path.abspath("cogs")
    if not os.path.exists(cogs_dir):
        os.makedirs(cogs_dir)
        logger.info(f"Cogs klasörü oluşturuldu: {cogs_dir}")

    for filename in os.listdir(cogs_dir):
        if filename.endswith(".py"):
            cog_name = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(cog_name)
                logger.info(f"Cog yüklendi: {cog_name}")
            except Exception as e:
                logger.error(f"Cog yüklenirken hata: {cog_name}\nHata: {e}")
                traceback.print_exc()

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_prices():
    logger.info("Fiyat kontrolü başlıyor...")
    # bot.db üzerinden erişim
    products = bot.db.get_all_products()

    if not products:
        logger.info("Takip edilen ürün bulunamadı.")
        return

    logger.info(f"Toplam {len(products)} ürün kontrol edilecek.")

    for product in products:
        try:
            # bot.scraper üzerinden erişim
            product_data = bot.scraper.scrape_product(product['url'])

            if not product_data or not product_data.get('success', False):
                logger.warning(f"Ürün bilgileri alınamadı: {product.get('product_id','Bilinmeyen ID')} - {product.get('name','Bilinmeyen Ürün')}")
                continue

            old_price = product['current_price']
            new_price = product_data['current_price']

            if new_price is None: # Scraper None dönebilir
                logger.warning(f"Yeni fiyat bilgisi None geldi: {product.get('product_id','Bilinmeyen ID')}")
                continue

            bot.db.update_product_price(product['product_id'], new_price)

            if old_price != new_price:
                try:
                    channel_id_str = product.get('channel_id')
                    user_id_str = product.get('user_id')

                    if not channel_id_str or not user_id_str:
                        logger.warning(f"Ürün için channel_id veya user_id eksik: {product['product_id']}")
                        continue
                    
                    channel = bot.get_channel(int(channel_id_str))
                    if channel:
                        embed = discord.Embed(
                            title="💸 Fiyat Değişimi Bildirimi",
                            url=product['url'],
                            color=discord.Color.green() if new_price < old_price else discord.Color.red()
                        )
                        embed.set_author(name=product['name'])
                        if product.get('image_url'):
                            embed.set_thumbnail(url=product['image_url'])

                        price_diff = new_price - old_price
                        percentage = abs(price_diff / old_price * 100) if old_price != 0 else 0

                        if price_diff < 0:
                            change_text = f"🔽 **Fiyat Düştü!**\n{old_price:.2f} TL ➡️ {new_price:.2f} TL\n📉 {abs(price_diff):.2f} TL düşüş (-%{percentage:.1f})"
                        else:
                            change_text = f"🔼 **Fiyat Arttı!**\n{old_price:.2f} TL ➡️ {new_price:.2f} TL\n📈 {price_diff:.2f} TL artış (+%{percentage:.1f})"
                        embed.description = change_text

                        user_mention = f"<@{user_id_str}>"
                        await channel.send(content=f"{user_mention} takip ettiğin ürünün fiyatı değişti!", embed=embed)
                        logger.info(f"Fiyat değişimi bildirimi gönderildi: {product['name']}")
                    else:
                        logger.warning(f"Bildirim kanalı bulunamadı: {channel_id_str}")
                except Exception as e:
                    logger.error(f"Bildirim gönderilirken hata: {e} (Ürün: {product['product_id']})")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Ürün kontrolünde hata: {product.get('product_id','Bilinmeyen ID')} - {e}")
            traceback.print_exc()
            continue
    logger.info("Fiyat kontrolü tamamlandı.")

@check_prices.before_loop
async def before_check_prices():
    await bot.wait_until_ready()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Eksik argüman: `{error.param.name}`. Doğru kullanım için `{PREFIX}yardım {ctx.command.name}` komutunu deneyin.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Geçersiz argüman tipi: {error}")
    elif isinstance(error, commands.CommandInvokeError):
        logger.error(f"Komut hatası ({ctx.command.name}): {error.original}")
        traceback.print_exc()
        await ctx.send(f"❌ Komut çalıştırılırken bir hata oluştu. Detaylar loglandı.")
    else:
        logger.error(f"Bilinmeyen prefix komut hatası: {error}")
        await ctx.send(f"❌ Bir hata oluştu: {error}")
        traceback.print_exc()

@bot.command(name="yardım", aliases=["yardim", "help"])
async def custom_prefix_help(ctx: commands.Context, *, command_name: str = None):
    """Bot komutları hakkında yardım bilgisi verir (Prefix)."""
    if command_name:
        command = bot.get_command(command_name)
        if command:
            # Detaylı yardım için bir yapı oluşturulabilir (örn: command.help, command.signature)
            embed = discord.Embed(title=f"{PREFIX}{command.name} Komutu", description=command.help or "Açıklama yok.", color=discord.Color.blue())
            embed.add_field(name="Kullanım", value=f"`{PREFIX}{command.name} {command.signature}`", inline=False)
            if command.aliases:
                embed.add_field(name="Alternatifler", value=", ".join([f"`{PREFIX}{a}`" for a in command.aliases]), inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❓ `{command_name}` adında bir komut bulunamadı.")
        return

    embed = discord.Embed(
        title="📚 Trendyol Takip Botu - Yardım (Prefix Komutları)",
        description=f"Aşağıda `{PREFIX}` ön eki ile kullanabileceğiniz komutların listesi bulunmaktadır. "
                    f"Belirli bir komut hakkında detaylı bilgi için `{PREFIX}yardım <komut_adı>` yazın.\n"
                    f"Ayrıca slash komutları (`/`) da mevcuttur. Onlar için `/yardim` kullanın.",
        color=discord.Color.blue()
    )
    for cog_name in bot.cogs:
        cog = bot.cogs[cog_name]
        cog_commands = [cmd for cmd in cog.get_commands() if not cmd.hidden and isinstance(cmd, commands.Command)]
        if cog_commands:
            command_list = []
            for cmd in cog_commands:
                command_list.append(f"`{PREFIX}{cmd.name}`: {cmd.short_doc or 'Açıklama yok.'}")
            embed.add_field(name=f"**{cog_name}**", value="\n".join(command_list), inline=False)
    
    # Cog dışı komutlar (örn: bu yardım komutu)
    other_commands = [cmd for cmd in bot.commands if not cmd.cog and not cmd.hidden and isinstance(cmd, commands.Command)]
    if other_commands:
        command_list = []
        for cmd in other_commands:
            command_list.append(f"`{PREFIX}{cmd.name}`: {cmd.short_doc or 'Açıklama yok.'}")
        embed.add_field(name="**Diğer Komutlar**", value="\n".join(command_list), inline=False)

    embed.set_footer(text=f"Trendyol Takip Botu • Fiyat kontrol aralığı: {CHECK_INTERVAL//60} dakika")
    await ctx.send(embed=embed)

async def run_bot():
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
        traceback.print_exc()
