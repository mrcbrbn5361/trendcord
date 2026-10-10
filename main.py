import discord
import asyncio
import os
import sys
import signal
import logging
import logging.handlers
import warnings
import dotenv
import functools
import threading
import uvicorn
from discord.ext import commands, tasks

from database import Database
from scraper import TrendyolScraper
from web.app import app as web_app, set_instances

# discord.py 2.7.x dahili `asyncio.iscoroutinefunction` kullaniyor (Python 3.12+
# deprecation, 3.16'da kalkacak). Kutuphane duzeltince kaldirilacak log-kirliligi filtresi.
warnings.filterwarnings(
    "ignore",
    message=".*asyncio\\.iscoroutinefunction.*",
    category=DeprecationWarning,
)

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
        # Trendcord Bot Owner rolu yalnizca bot sahibinde kalmali; rol
        # verildiginde anlikca geri alabilmek icin member update gerekir.
        # (Developer Portal > Bot > Privileged Gateway Intents > SERVER MEMBERS INTENT)
        intents.members = True
        super().__init__(command_prefix=PREFIX, intents=intents, help_command=None)
        self.db = Database()
        self.scraper = TrendyolScraper()
        self._synced = False

    async def setup_hook(self):
        # Kalici paneller: rol-secimi / destek / sss butonlari restart sonrasi
        # da calisir (sabit custom_id + add_view).
        try:
            from provisioner.common.views import register_persistent_views
            register_persistent_views(self)
        except Exception as e:
            logger.error(f"Kalici panel kaydi basarisiz: {e}")

        # /takiptekiler mesajindaki kalici "Urun Sil" butonu
        try:
            import cogs.product_commands as pc
            pc.register(self)
        except Exception as e:
            logger.error(f"Urun sil butonu kaydi basarisiz: {e}")

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
        if not refresh_stale_prices.is_running():
            refresh_stale_prices.start()
            logger.info(f"Bayat fiyat döngüsü aktif ({STALE_LOOP_MINUTES} dk, "
                        f"eşik {STALE_MINUTES} dk).")

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


@bot.tree.on_error
async def on_app_command_error(interaction: discord.Interaction, error):
    """Slash komut hatasi: hem logla hem kullaniciya bildir.

    Aksi halde komut defer edilmeden patlarsa Discord 3 sn sonra
    "uygulama yanit vermedi" gosterir ve kullanici nedenini bilemez.
    """
    logger.error(f"[Slash] /{interaction.command.qualified_name if interaction.command else '?'} "
                 f"({interaction.user}): {type(error).__name__}: {error.original or error}")
    msg = "❌ Komut çalıştırılırken bir hata oluştu."
    if isinstance(error, discord.app_commands.MissingPermissions):
        msg = "⛔ Bu komut için gerekli iznin yok."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        pass

# Fiyat tazeleme ayarlari
PRICE_CHECK_MINUTES = int(os.getenv("PRICE_CHECK_MINUTES", "60") or 60)
STALE_MINUTES = int(os.getenv("STALE_MINUTES", "45") or 45)
STALE_LOOP_MINUTES = int(os.getenv("STALE_LOOP_MINUTES", "15") or 15)
STALE_BATCH = int(os.getenv("STALE_BATCH", "40") or 40)

_refresh_lock = asyncio.Lock()


async def refresh_product(p, notify=True):
    """Tek bir urunu tazeler: fiyat, alarm ve kanal bildirimi.

    Hem saatlik `check_prices` hem bayat `refresh_stale_prices` bunu kullanir.
    """
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(
        None, functools.partial(bot.scraper.scrape_product, p['url']))

    if not data or not data.get('success'):
        return False

    old_p = p['current_price']
    new_p = bot.db._safe_float(data.get('current_price', 0))
    orig_p = bot.db._safe_float(data.get('original_price', 0))
    basket_p = bot.db._safe_float(data.get('basket_price', 0))
    disc_pct = bot.db._safe_float(data.get('discount_pct', 0))
    camp_name = data.get('campaign_name', '')
    camp_type = data.get('campaign_type', '')
    camp_end = data.get('campaign_end', '')
    price_changed = abs(new_p - old_p) > 0.01

    if new_p <= 0:
        return False

    if not (price_changed and old_p > 0):
        # Fiyat degismedi: son kontrol zamanini guncelle + saatlik
        # gecmis noktasi (grafik canli kalsin)
        bot.db.update_product_price(p['product_id'], new_p, orig_p, basket_p,
                                    disc_pct, camp_name, camp_type, camp_end)

    active_alerts = bot.db.get_active_alerts()
    for alert in active_alerts:
        if alert.get('product_id') != p['product_id']:
            continue
        target = alert.get('target_price', 0)
        direction = alert.get('direction', 'below')
        triggered = (direction == 'below' and new_p <= target) or \
                    (direction == 'above' and new_p >= target)
        if not triggered:
            continue
        bot.db.trigger_alert(alert['id'])
        ch_id = alert.get('channel_id', '')
        if ch_id and ch_id.isdigit():
            ch = bot.get_channel(int(ch_id))
            if ch:
                emoji = "📉" if direction == 'below' else "📈"
                embed = discord.Embed(
                    title=f"{emoji} Alarm Tetiklendi!", url=p['url'],
                    color=0x10B981 if direction == 'below' else 0xF59E0B)
                embed.add_field(name="Ürün", value=p['name'][:100], inline=False)
                embed.add_field(name="Hedef",
                                value=f"{target:.2f} TL "
                                      f"({'Altına' if direction == 'below' else 'Üzerine'})",
                                inline=True)
                embed.add_field(name="Güncel", value=f"**{new_p:.2f} TL**", inline=True)
                await ch.send(content=f"<@{alert['user_id']}>", embed=embed)

    if price_changed and old_p > 0:
        bot.db.update_product_price(p['product_id'], new_p, orig_p, basket_p,
                                    disc_pct, camp_name, camp_type, camp_end)
    elif old_p <= 0:
        bot.db.update_product_price(p['product_id'], new_p)

    if not (notify and price_changed and old_p > 0):
        return True

    c_id = str(p.get('channel_id', '0'))
    if not (c_id.isdigit() and c_id != "0"):
        return True
    ch = bot.get_channel(int(c_id))
    if not ch:
        return True

    color = 0x10B981 if new_p < old_p else 0xEF4444
    embed = discord.Embed(title="📊 Fiyat Güncellemesi", url=p['url'], color=color)

    img_url = data.get('image_url')
    if img_url and isinstance(img_url, str) and img_url.startswith('http'):
        try:
            embed.set_thumbnail(url=img_url)
        except Exception:
            pass

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
            embed.add_field(name="Kampanya Bitişi",
                            value=f"{kalan.days} gün {kalan.seconds // 3600} saat",
                            inline=True)
        except Exception:
            pass

    await ch.send(content=f"<@{p['user_id']}>", embed=embed)
    await asyncio.sleep(0.5)
    return True


@tasks.loop(minutes=PRICE_CHECK_MINUTES)
async def check_prices():
    """Arka planda ürün fiyatlarını kontrol eder (tüm ürünler)."""
    if _refresh_lock.locked():
        logger.debug("Fiyat kontrolü atlandı: bayat döngü çalışıyor.")
        return
    products = bot.db.get_all_products()
    if not products:
        return
    async with _refresh_lock:
        for p in products:
            try:
                await refresh_product(p)
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Döngü hatası ({p.get('product_id', 'Bilinmiyor')}): {e}")


@tasks.loop(minutes=STALE_LOOP_MINUTES)
async def refresh_stale_prices():
    """Saatlik turunu beklemeyen bayat urunleri kisa araliklarla tazeler."""
    if _refresh_lock.locked():
        return
    stale = bot.db.get_stale_products(older_than_minutes=STALE_MINUTES,
                                      limit=STALE_BATCH)
    if not stale:
        return
    logger.info(f"[Fiyat] {len(stale)} bayat ürün tazeleniyor "
                f"(>{STALE_MINUTES} dk).")
    async with _refresh_lock:
        for p in stale:
            try:
                await refresh_product(p)
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Bayat yenileme hatası "
                             f"({p.get('product_id', '?')}): {e}")


@check_prices.before_loop
async def before_check_prices():
    await bot.wait_until_ready()


@refresh_stale_prices.before_loop
async def before_refresh_stale():
    await bot.wait_until_ready()


async def force_refresh(guild_id=None, limit=STALE_BATCH):
    """Beklemeden fiyat tazele (web paneli / komut tetikler). Donus: sayi.

    Not: check_prices/refresh_stale_prices calisirsa atlanir (cakisma yok).
    """
    if _refresh_lock.locked():
        logger.info("Zorunlu yenileme atlandi: periyodik döngü çalışıyor.")
        return 0
    products = (bot.db.get_stale_products(older_than_minutes=0, limit=limit)
                if guild_id is None else
                [p for p in bot.db.get_all_products(guild_id=guild_id)][:limit])
    n = 0
    async with _refresh_lock:
        for p in products:
            try:
                if await refresh_product(p):
                    n += 1
                await asyncio.sleep(1.5)
            except Exception as e:
                logger.error(f"Zorunlu yenileme hatası "
                             f"({p.get('product_id', '?')}): {e}")
    return n

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

    retry = 0
    while True:
        try:
            await bot.start(TOKEN)
            # bot.start() normal sekilde donerse (logout) tekrar baglanma
            logger.info("Bot oturumu kapandi, cikiliyor.")
            break
        except KeyboardInterrupt:
            logger.info("Sistem kapatıldı.")
            break
        except SystemExit as e:
            raise
        except discord.errors.PrivilegedIntentsRequired:
            # Developer Portal'da SERVER MEMBERS INTENT acik degil.
            # Botu TAMAMEN dusurmeyelim: intents'i kapatip members'siz devam et.
            if bot._connection._intents.members:
                logger.critical(
                    "SERVER MEMBERS INTENT Developer Portal'da acik degil. "
                    "Intent kapatilip bot members'siz olarak devam ediyor "
                    "(bot sahibi rolu denetimi 6 saatlik taramaya kalir).")
                bot._connection._intents.members = False
                try:
                    await bot.close()
                except Exception:
                    pass
                retry = 0
                continue
            logger.critical("Privileged intent hatasi (members kapali) — cikis (kod 1).")
            sys.exit(1)
        except Exception as e:
            msg = f"{e} {type(e).__name__}".lower()
            auth_markers = (
                "4004", "401", "unauthorized", "authentication failed",
                "invalid token", "incorrect token", "login failure",
            )
            # Discord auth hatalari tekrar denenmemeli - sonsuz donguye girer
            is_auth_error = isinstance(e, discord.LoginFailure)
            if not is_auth_error:
                try:
                    is_auth_error = any(m in msg for m in auth_markers)
                except Exception:
                    pass
            if is_auth_error:
                logger.critical(
                    f"Token/auth hatasi: {e}. Yeniden denenmiyor - "
                    "DISCORD_TOKEN'i kontrol edin. Cikis (kod 1)."
                )
                try:
                    await bot.close()
                except Exception:
                    pass
                sys.exit(1)
            retry += 1
            # 20 basarisiz deneme (~10 dk) -> temiz restart icin cik.
            # Task Scheduler RestartOnFailure ile taze process baslatir,
            # sizmis session/event-loop ile sonsuz spam engellenir.
            if retry >= 20:
                logger.critical(
                    f"20 kez art arda baglanti basarisiz (son: {e}). "
                    "Temiz restart icin cikiliyor (kod 1)."
                )
                try:
                    if not bot.is_closed():
                        await bot.close()
                except Exception:
                    pass
                sys.exit(1)
            logger.error(f"Bağlantı hatası (deneme {retry}): {e}. 30 sn sonra yeniden bağlanılıyor...")
            try:
                if not bot.is_closed():
                    await bot.close()
            except Exception:
                pass
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
