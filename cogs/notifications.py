import discord
import logging
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger("Trendcord")

class Notifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.orange = 0xF27A1A

    async def cog_load(self):
        logger.info("Notifications cog yüklendi.")

    async def cog_unload(self):
        logger.info("Notifications cog kaldırıldı.")

    @commands.hybrid_command(name="bildirim-kanal", description="Bildirim kanalını ayarla")
    async def set_notify_channel(self, ctx, channel: discord.TextChannel = None):
        """Fiyat değişimlerinin bildirileceği kanalı ayarlar."""
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()

        if not channel:
            channel = ctx.channel

        gid = str(ctx.guild.id) if ctx.guild else "0"
        uid = str(ctx.author.id)

        self.bot.db.set_user_preferences(uid, gid, channel_id=str(channel.id))

        embed = discord.Embed(
            title="🔔 Bildirim Kanalı Ayarlandı",
            description=f"Fiyat değişimleri artık {channel.mention} kanalında bildirilecek.",
            color=self.orange
        )
        if isinstance(ctx, commands.Context):
            await ctx.send(embed=embed)
        else:
            await ctx.followup.send(embed=embed)

    @commands.hybrid_command(name="bildirim-ayarla", description="Bildirim tercihlerini düzenle")
    async def set_notifications(self, ctx, dusus: bool = None, yukselis: bool = None, esik: float = None):
        """Bildirim tercihlerini düzenler.
        
        dusus: Fiyat düştüğünde bildirim (True/False)
        yukselis: Fiyat yükseldiğinde bildirim (True/False)
        esik: Minimum fiyat farkı yüzdesi (örn: 5.0 = %5)
        """
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()

        gid = str(ctx.guild.id) if ctx.guild else "0"
        uid = str(ctx.author.id)

        self.bot.db.set_user_preferences(uid, gid,
            on_drop=dusus, on_rise=yukselis, threshold=esik)

        prefs = self.bot.db.get_user_preferences(uid, gid)

        embed = discord.Embed(title="⚙️ Bildirim Tercihleri Güncellendi", color=self.orange)
        embed.add_field(name="Düşüş Bildirimi",
            value="✅ Açık" if prefs.get('notify_on_drop') else "❌ Kapalı", inline=True)
        embed.add_field(name="Yükseliş Bildirimi",
            value="✅ Açık" if prefs.get('notify_on_rise') else "❌ Kapalı", inline=True)
        embed.add_field(name="Eşik",
            value=f"%{prefs.get('notify_threshold', 5.0):.1f}", inline=True)

        if isinstance(ctx, commands.Context):
            await ctx.send(embed=embed)
        else:
            await ctx.followup.send(embed=embed)

    @commands.hybrid_command(name="bildirim-test", description="Test bildirimi gönder")
    async def test_notification(self, ctx):
        """Bildirim testi gönderir."""
        embed = discord.Embed(
            title="🔔 Bildirim Testi",
            description="Bu bir test bildirimidir. Bildirim sistemi çalışıyor!",
            color=self.orange
        )
        embed.add_field(name="Durum", value="✅ Aktif", inline=True)
        embed.add_field(name="Kanal", value=ctx.channel.mention, inline=True)

        if isinstance(ctx, commands.Context):
            await ctx.send(embed=embed)
        else:
            await ctx.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Notifications(bot))
