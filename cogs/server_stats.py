import discord
import logging
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger("Trendcord")

class ServerStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.orange = 0xF27A1A

    async def cog_load(self):
        logger.info("ServerStats cog yüklendi.")

    async def cog_unload(self):
        logger.info("ServerStats cog kaldırıldı.")

    @commands.hybrid_command(name="sunucuistatistik", aliases=["sunucustat", "guildstats"], description="Sunucu istatistiklerini göster")
    async def guild_stats(self, ctx):
        """Bu sunucu için detaylı istatistik raporu gösterir."""
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()

        gid = str(ctx.guild.id) if ctx.guild else "0"
        stats = self.bot.db.get_guild_stats(gid)

        if not stats or stats.get('total_products', 0) == 0:
            msg = "📭 Bu sunucuda henüz istatistik bulunmuyor."
            if isinstance(ctx, commands.Context):
                await ctx.send(msg)
            else:
                await ctx.followup.send(msg)
            return

        embed = discord.Embed(
            title=f"📊 {ctx.guild.name if ctx.guild else 'Sunucu'} İstatistikleri",
            color=self.orange
        )

        embed.add_field(name="📦 Toplam Ürün", value=f"**{stats['total_products']}**", inline=True)
        embed.add_field(name="👥 Benzersiz Kullanıcı", value=f"**{stats['unique_users']}**", inline=True)
        embed.add_field(name="💰 Toplam Tasarruf", value=f"**{stats['total_savings']:.0f} TL**", inline=True)
        embed.add_field(name="📉 İndirimli Ürün", value=f"**{stats['price_drops']}**", inline=True)

        if stats.get('top_products'):
            top_text = ""
            for i, p in enumerate(stats['top_products'][:5], 1):
                top_text += f"{i}. {p['name'][:35]} — **{p['current_price']:.0f} TL**\n"
            embed.add_field(name="🏆 En Pahalı Ürünler", value=top_text or "Yok", inline=False)

        if stats.get('recent_products'):
            recent_text = ""
            for p in stats['recent_products'][:3]:
                recent_text += f"• {p['name'][:35]} — {p['current_price']:.0f} TL\n"
            embed.add_field(name="🕐 Son Kontrol Edilenler", value=recent_text or "Yok", inline=False)

        embed.set_footer(text=f"Sunucu ID: {gid}")

        if isinstance(ctx, commands.Context):
            await ctx.send(embed=embed)
        else:
            await ctx.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ServerStats(bot))
