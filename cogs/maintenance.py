import discord
from discord.ext import commands, tasks
import logging
import random
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MaintenanceCog(commands.Cog, name="Bakım"):
    def __init__(self, bot):
        self.bot = bot
        self.maintenance_task.start()

    def cog_unload(self):
        self.maintenance_task.cancel()

    @tasks.loop(hours=336) # 14 days
    async def maintenance_task(self):
        logger.info("Bi-weekly maintenance check starting...")
        await self.perform_health_check()

    @maintenance_task.before_loop
    async def before_maintenance_task(self):
        await self.bot.wait_until_ready()

    async def perform_health_check(self, ctx=None):
        """Checks if the scraper is still working correctly."""
        products = self.bot.db.get_all_products()
        if not products:
            logger.info("No products in database to check.")
            if ctx: await ctx.send("📋 Veritabanında kontrol edilecek ürün bulunamadı.")
            return

        # Pick up to 3 random products
        sample_size = min(len(products), 3)
        sample = random.sample(products, sample_size)

        success_count = 0
        for product in sample:
            try:
                data = self.bot.scraper.scrape_product(product['url'])
                if data and data.get('success'):
                    success_count += 1
            except Exception as e:
                logger.error(f"Maintenance check failed for product {product['product_id']}: {e}")

        status_msg = f"Maintenance Health Check: {success_count}/{sample_size} successful."
        logger.info(status_msg)

        if success_count == 0 and sample_size > 0:
            logger.critical("SCRAPER HEALTH CHECK FAILED! All samples failed.")
            await self.notify_owner("🚨 **KRİTİK HATA:** Trendyol Scraper tüm testlerden başarısız oldu! Sayfa yapısı değişmiş olabilir.")

        if ctx:
            await ctx.send(f"✅ Bakım kontrolü tamamlandı: `{status_msg}`")

    async def notify_owner(self, message):
        owner_id = os.getenv('OWNER_ID')
        if not owner_id:
            logger.warning("OWNER_ID not set in .env, cannot notify owner.")
            return

        try:
            owner = await self.bot.fetch_user(int(owner_id))
            if owner:
                await owner.send(message)
        except Exception as e:
            logger.error(f"Failed to notify owner: {e}")

    @commands.command(name="bakim_kontrol", help="Manuel bakım kontrolü yapar (Admin).")
    @commands.is_owner()
    async def manual_maintenance_check(self, ctx):
        await ctx.send("🔍 Bakım kontrolü başlatılıyor...")
        await self.perform_health_check(ctx)

async def setup(bot):
    await bot.add_cog(MaintenanceCog(bot))
