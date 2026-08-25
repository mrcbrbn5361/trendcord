import discord
import os
import logging
from discord.ext import commands
from discord import app_commands

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

logger = logging.getLogger("Trendcord")

class ProductCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.orange = 0xF27A1A

    async def cog_load(self):
        logger.info("ProductCommands cog yüklendi.")

    async def cog_unload(self):
        logger.info("ProductCommands cog kaldırıldı.")

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            logger.error(f"Komut hatası ({ctx.command}): {error.original}")
            if isinstance(ctx, commands.Context):
                await ctx.send("❌ Bir hata oluştu. Lütfen tekrar deneyin.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Eksik parametre: `{error.param.name}`")
        else:
            logger.error(f"Beklenmeyen hata ({ctx.command}): {error}")

    async def _handle_add(self, target, url):
        data = self.bot.scraper.scrape_product(url)
        if data:
            if isinstance(target, commands.Context):
                gid = str(target.guild.id) if target.guild else "0"
                uid = str(target.author.id)
                uname = str(target.author.name)
                cid = str(target.channel.id)
                author = target.author
            else:
                gid = str(target.guild_id) if target.guild_id else "0"
                uid = str(target.user.id)
                uname = str(target.user.name)
                cid = str(target.channel_id)
                author = target.user

            if author.avatar:
                avatar_url = author.avatar.url
            else:
                avatar_url = f"https://cdn.discordapp.com/embed/avatars/{(author.id >> 22) % 6}.png"

            self.bot.db.add_product(data, gid, uid, cid, username=uname, avatar_url=avatar_url)

            embed = discord.Embed(title="✅ Takip Başlatıldı", url=data['url'], color=self.orange)
            if data.get('image_url'):
                embed.set_thumbnail(url=data['image_url'])
            embed.add_field(name="Ürün", value=data['name'][:100], inline=False)
            
            satis = data.get('current_price', 0)
            sepet = data.get('basket_price', 0)
            indirim = data.get('discount_pct', 0)
            kampanya = data.get('campaign_name', '')
            
            fiyat_txt = f"**{satis:.2f} TL**"
            if sepet and sepet < satis:
                fiyat_txt += f"\n Sepette: **{sepet:.2f} TL**"
            embed.add_field(name="Fiyat", value=fiyat_txt, inline=True)
            
            if indirim and indirim > 0:
                embed.add_field(name="İndirim", value=f"**%{indirim:.0f}**", inline=True)
            if kampanya:
                embed.add_field(name="Kampanya", value=kampanya, inline=True)
            
            embed.add_field(name="ID", value=f"`{data['product_id']}`", inline=True)

            if isinstance(target, commands.Context):
                await target.send(embed=embed)
            else:
                await target.followup.send(embed=embed)
        else:
            msg = "❌ Ürün bulunamadı veya taranamadı."
            if isinstance(target, commands.Context):
                await target.send(msg)
            else:
                await target.followup.send(msg)

    @commands.hybrid_command(name="ekle", description="Trendyol ürününü takip et")
    async def ekle(self, ctx, url: str):
        """Trendyol ürün linkini takibe alır."""
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer(thinking=True)
        else:
            async with ctx.typing():  # Prefix komutları için typing indicator
                await self._handle_add(ctx, url)
                return
        await self._handle_add(ctx, url)

    async def _handle_list(self, target):
        if isinstance(target, commands.Context):
            gid = str(target.guild.id) if target.guild else "0"
        else:
            gid = str(target.guild_id) if target.guild_id else "0"

        prods = self.bot.db.get_all_products(guild_id=gid)

        if prods:
            embed = discord.Embed(title="📋 Takip Listesi", color=self.orange)
            for p in prods[:10]:
                embed.add_field(
                    name=p['name'][:50],
                    value=f"{p['current_price']} TL | ID: `{p['product_id']}`",
                    inline=False
                )
            if isinstance(target, commands.Context):
                await target.send(embed=embed)
            else:
                await target.followup.send(embed=embed)
        else:
            msg = "📭 Liste boş."
            if isinstance(target, commands.Context):
                await target.send(msg)
            else:
                await target.followup.send(msg)

    @commands.hybrid_command(name="takiptekiler", description="Takip edilen ürünleri listele")
    async def takiptekiler(self, ctx):
        """Sunucudaki takip edilen ürünleri listeler."""
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()
        await self._handle_list(ctx)

    @commands.hybrid_command(name="sil", description="Takip edilen ürünü sil")
    async def sil(self, ctx, product_id: str):
        """Belirtilen ürün takibini kaldırır."""
        res = self.bot.db.delete_product(product_id)
        msg = f"✅ Silindi: `{product_id}`" if res else "❌ Bulunamadı."
        if isinstance(ctx, commands.Context):
            await ctx.send(msg)
        else:
            await ctx.response.send_message(msg)

    @commands.hybrid_command(name="yardım", aliases=["yardim", "help"], description="Trendcord komutlarını göster")
    async def yardim(self, ctx):
        """Tüm komutları listeler."""
        embed = discord.Embed(title="Trendcord Yardım", color=self.orange,
            description="Trendyol fiyat takip botu komutları")
        embed.add_field(name="/ekle <link>", value="Ürün takibe alır", inline=False)
        embed.add_field(name="/takiptekiler", value="Takip listesini gösterir", inline=False)
        embed.add_field(name="/sil <ID>", value="Ürün takibini kaldırır", inline=False)
        embed.add_field(name="/alarm <ID> <fiyat> [alt|üzeri]", value="Fiyat alarmı kurar", inline=False)
        embed.add_field(name="/alarmlar", value="Aktif alarmları listeler", inline=False)
        embed.add_field(name="/karşılaştır", value="Ürünleri karşılaştırır", inline=False)
        embed.add_field(name="/sunucuistatistik", value="Sunucu raporu gösterir", inline=False)
        embed.add_field(name="/bildirim-kanal <#kanal>", value="Bildirim kanalını ayarlar", inline=False)
        embed.add_field(name="/bildirim-ayarla", value="Bildirim tercihlerini düzenler", inline=False)
        embed.set_footer(text="Trendcord • Trendyol Fiyat Takip Botu")
        if isinstance(ctx, commands.Context):
            await ctx.send(embed=embed)
        else:
            await ctx.response.send_message(embed=embed)

    @commands.command(name="istatistik", aliases=["stats", "bilgi"])
    @commands.is_owner()
    async def system_stats(self, ctx):
        """Sadece bot sahibinin görebileceği sistem metrikleri."""
        if HAS_PSUTIL:
            process = psutil.Process(os.getpid())
            ram_usage = process.memory_info().rss / (1024 * 1024)
        else:
            ram_usage = 0.0

        db_path = "data/trendyol_tracker.sqlite"
        db_size = os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0.0

        guild_count = len(self.bot.guilds)
        total_products = len(self.bot.db.get_all_products())
        ping = int(self.bot.latency * 1000)

        embed = discord.Embed(
            title="SİSTEM METRİKLERİ",
            description="Trendcord anlık donanım ve ağ istatistikleri.",
            color=self.orange
        )
        embed.add_field(name="Sunucu", value=f"**{guild_count}**", inline=True)
        embed.add_field(name="Ürün", value=f"**{total_products}**", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="RAM", value=f"**{ram_usage:.2f}** MB", inline=True)
        embed.add_field(name="DB", value=f"**{db_size:.2f}** MB", inline=True)
        embed.add_field(name="Gecikme", value=f"**{ping}** ms", inline=True)
        embed.set_footer(text=f"Trendcord Core v2.0")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ProductCommands(bot))
