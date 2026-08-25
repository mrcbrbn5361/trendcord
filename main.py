import discord
import asyncio
import os
import sys
import signal
import logging
import logging.handlers
import dotenv
import functools
import threading
import uvicorn
from discord.ext import commands, tasks

from database import Database
from scraper import TrendyolScraper
from web.app import app as web_app, set_instances

# .env yükle
dotenv.load_dotenv()

# Log rotation ayarları (5MB max, 3 yedek dosya)
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOG_DIR, 'bot.log'),
    maxBytes=5*1024*1024,
    backupCount=3,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logger = logging.getLogger("Trendcord")

TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('COMMAND_PREFIX', '!')

# Termux Wake Lock
def acquire_wake_lock():
    """Termux'ta ekran kapanmasını engelle"""
    try:
        import subprocess
        subprocess.run(['termux-wake-lock'], capture_output=True, timeout=5)
        logger.info("Wake lock aktif edildi")
    except Exception:
        pass

def release_wake_lock():
    """Termux wake lock'ı serbest bırak"""
    try:
        import subprocess
        subprocess.run(['termux-wake-unlock'], capture_output=True, timeout=5)
    except Exception:
        pass

class TrendcordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(command_prefix=PREFIX, intents=intents, help_command=None)
        self.db = Database()
        self.scraper = TrendyolScraper()
        self._synced = False

    async def setup_hook(self):
        if os.path.exists("cogs"):
            for filename in os.listdir("cogs"):
                if filename.endswith(".py") and not filename.startswith("__"):
                    try:
                        await self.load_extension(f"cogs.{filename[:-3]}")
                        logger.info(f"Modül Yüklendi: {filename}")
                    except Exception as e:
                        logger.error(f"Modül Yüklenemedi ({filename}): {e}")

        set_instances(self, self.db)
        
        if not check_prices.is_running():
            check_prices.start()
            logger.info("Fiyat kontrol döngüsü aktif edildi.")

    async def on_ready(self):
        self.start_time = __import__('time').time()
        if not self._synced:
            try:
                synced = await self.tree.sync()
                self._synced = True
                logger.info(f"Slash komutları senkronize edildi: {len(synced)} komut")
            except Exception as e:
                logger.error(f"Komut senkronizasyonu hatası: {e}")
        logger.info(f"Sistem Hazır: {self.user.name} | ID: {self.user.id}")
        
        # Başlangıç bildirimi
        try:
            import subprocess
            subprocess.run([
                'termux-notification',
                '--title', 'Trendcord',
                '--content', f'{self.user.name} çevrimiçi',
                '--id', 'trendcord-status'
            ], capture_output=True, timeout=5)
        except Exception:
            pass

bot = TrendcordBot()

@tasks.loop(minutes=60)
async def check_prices():
    """Arka planda ürün fiyatlarını kontrol eder."""
    products = bot.db.get_all_products()
    if not products: return

    for p in products:
        try:
            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(None, functools.partial(bot.scraper.scrape_product, p['url']))
            
            if data and data.get('success'):
                old_p = p['current_price']
                new_p = bot.db._safe_float(data.get('current_price', 0))
                orig_p = bot.db._safe_float(data.get('original_price', 0))
                basket_p = bot.db._safe_float(data.get('basket_price', 0))
                disc_pct = bot.db._safe_float(data.get('discount_pct', 0))
                camp_name = data.get('campaign_name', '')
                camp_type = data.get('campaign_type', '')
                camp_end = data.get('campaign_end', '')
                price_changed = abs(new_p - old_p) > 0.01
                
                if price_changed and new_p > 0 and old_p > 0:
                    bot.db.update_product_price(p['product_id'], new_p, orig_p, basket_p, disc_pct, camp_name, camp_type, camp_end)
                    
                    active_alerts = bot.db.get_active_alerts()
                    for alert in active_alerts:
                        if alert.get('product_id') == p['product_id']:
                            target = alert.get('target_price', 0)
                            direction = alert.get('direction', 'below')
                            triggered = False
                            if direction == 'below' and new_p <= target:
                                triggered = True
                            elif direction == 'above' and new_p >= target:
                                triggered = True
                            
                            if triggered:
                                bot.db.trigger_alert(alert['id'])
                                ch_id = alert.get('channel_id', '')
                                if ch_id and ch_id.isdigit():
                                    ch = bot.get_channel(int(ch_id))
                                    if ch:
                                        emoji = "📉" if direction == 'below' else "📈"
                                        embed = discord.Embed(
                                            title=f"{emoji} Alarm Tetiklendi!",
                                            url=p['url'],
                                            color=0x10B981 if direction == 'below' else 0xF59E0B
                                        )
                                        embed.add_field(name="Ürün", value=p['name'][:100], inline=False)
                                        embed.add_field(name="Hedef", value=f"{target:.2f} TL ({'Altına' if direction == 'below' else 'Üzerine'})", inline=True)
                                        embed.add_field(name="Güncel", value=f"**{new_p:.2f} TL**", inline=True)
                                        await ch.send(content=f"<@{alert['user_id']}>", embed=embed)
                    
                    c_id = str(p.get('channel_id', '0'))
                    if c_id and c_id != "0" and c_id.isdigit():
                        ch = bot.get_channel(int(c_id))
                        if ch:
                            color = 0x10B981 if new_p < old_p else 0xEF4444
                            embed = discord.Embed(title="📊 Fiyat Güncellemesi", url=p['url'], color=color)
                            
                            img_url = data.get('image_url')
                            if img_url and isinstance(img_url, str) and img_url.startswith('http'):
                                try:
                                    embed.set_thumbnail(url=img_url)
                                except: pass
                            
                            embed.add_field(name="Ürün", value=p['name'][:100], inline=False)
                            
                            eski_sepet = p.get('basket_price') or old_p
                            yeni_sepet = basket_p if basket_p and basket_p < new_p else new_p
                            
                            eski_txt = f"~~{old_p:.2f} TL~~"
                            if eski_sepet and eski_sepet < old_p:
                                eski_txt += f" (sepette ~~{eski_sepet:.2f} TL~~)"
                            embed.add_field(name="Eski Fiyat", value=eski_txt, inline=False)
                            
                            yeni_txt = f"**{new_p:.2f} TL**"
                            if yeni_sepet and yeni_sepet < new_p:
                                yeni_txt += f" (sepette **{yeni_sepet:.2f} TL**)"
                            embed.add_field(name="Yeni Fiyat", value=yeni_txt, inline=False)
                            
                            if disc_pct and disc_pct > 0:
                                embed.add_field(name="İndirim", value=f"**%{disc_pct:.0f}**", inline=True)
                            if camp_name:
                                embed.add_field(name="Kampanya", value=camp_name, inline=True)
                            if camp_end:
                                try:
                                    from datetime import datetime
                                    bitis = datetime.fromisoformat(camp_end.replace('Z', '+00:00'))
                                    kalan = bitis - datetime.now(bitis.tzinfo)
                                    embed.add_field(name="Kampanya Bitişi", value=f"{kalan.days} gün {kalan.seconds//3600} saat", inline=True)
                                except: pass
                            
                            await ch.send(content=f"<@{p['user_id']}>", embed=embed)
                            await asyncio.sleep(0.5)
                elif price_changed and new_p > 0 and old_p <= 0:
                    bot.db.update_product_price(p['product_id'], new_p)
            
            await asyncio.sleep(2) 
        except Exception as e:
            logger.error(f"Döngü hatası ({p.get('product_id', 'Bilinmiyor')}): {e}")

def run_web(port):
    logger.info(f"Web sunucusu başlatılıyor: 0.0.0.0:{port}")
    web_log_handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, 'web.log'),
        maxBytes=5*1024*1024,
        backupCount=3,
        encoding='utf-8'
    )
    web_log_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.addHandler(web_log_handler)
    uvicorn_logger.setLevel(logging.INFO)
    uvicorn.run(web_app, host="0.0.0.0", port=port, log_level="info")

async def main():
    if not TOKEN:
        logger.critical("DISCORD_TOKEN bulunamadı! .env dosyasını kontrol edin.")
        return

    # Wake lock
    acquire_wake_lock()

    port = int(os.getenv("PORT", 8000))
    t = threading.Thread(target=run_web, args=(port,), daemon=True)
    t.start()

    # Graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(bot)))
        except NotImplementedError:
            pass

    while True:
        try:
            await bot.start(TOKEN)
        except KeyboardInterrupt:
            logger.info("Sistem kapatıldı.")
            break
        except Exception as e:
            logger.error(f"Bağlantı hatası: {e}. 30 sn sonra yeniden bağlanılıyor...")
            await asyncio.sleep(30)

async def shutdown(bot_instance):
    """Temiz kapatma"""
    logger.info("Sistem kapatılıyor...")
    release_wake_lock()
    await bot_instance.close()
    sys.exit(0)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Sistem kapatıldı.")
        release_wake_lock()
