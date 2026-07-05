import discord
import psutil
import os
from discord.ext import commands, tasks
from datetime import datetime, timedelta


class Maintenance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.orange = 0xF27A1A
        self.last_maintenance = datetime.utcnow()

    @commands.command(name="istatistik", aliases=["stats", "bilgi"])
    @commands.is_owner()
    async def system_stats(self, ctx):
        """Sadece bot sahibinin görebileceği sistem metrikleri."""
        process = psutil.Process(os.getpid())
        ram_usage = process.memory_info().rss / (1024 * 1024)
        
        db_path = "data/trendyol_tracker.sqlite"
        db_size = os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0.0
        
        guild_count = len(self.bot.guilds)
        products = await self.bot.db.get_all_products()
        total_products = len(products)
        ping = int(self.bot.latency * 1000)
        
        embed = discord.Embed(
            title="SİSTEM METRİKLERİ",
            description="Trendcord anlık donanım ve ağ istatistikleri.",
            color=self.orange
        )
        embed.add_field(name="Sunucu", value=f"**{guild_count}** Sunucu", inline=True)
        embed.add_field(name="Ürün", value=f"**{total_products}** Ürün", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="RAM", value=f"**{ram_usage:.2f}** MB", inline=True)
        embed.add_field(name="DB", value=f"**{db_size:.2f}** MB", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        embed.set_footer(text=f"Trendcord Core v2.0 • Gecikme: {ping}ms")
        
        await ctx.send(embed=embed)

    @tasks.loop(hours=12)
    async def maintenance_check(self):
        """Periodic maintenance check."""
        self.last_maintenance = datetime.utcnow()
        print(f"[MAINTENANCE] Check completed at {self.last_maintenance}")


async def setup(bot):
    await bot.add_cog(Maintenance(bot))
