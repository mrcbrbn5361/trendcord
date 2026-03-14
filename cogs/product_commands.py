import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ProductCommands(commands.Cog, name="Ürün Komutları"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.scraper = bot.scraper

    async def _add_logic(self, url, guild_id, user_id, channel_id):
        if not self.scraper.is_valid_url(url):
            return False, "❌ Geçersiz Trendyol URL'si."

        product_data = self.scraper.scrape_product(url)
        if not product_data or not product_data.get('success'):
            return False, "❌ Ürün bilgileri alınamadı."
        
        if self.db.add_product(product_data, guild_id, user_id, channel_id):
            return True, product_data
        return False, "❌ Ürün eklenirken hata oluştu."

    @commands.command(name="ekle")
    @commands.guild_only()
    async def ekle_prefix(self, ctx, url: str):
        success, res = await self._add_logic(url, str(ctx.guild.id), str(ctx.author.id), str(ctx.channel.id))
        if success:
            embed = discord.Embed(title="✅ Ürün Takibe Alındı", description=f"**{res['name']}** takipte!", color=discord.Color.green())
            embed.set_thumbnail(url=res['image_url'])
            await ctx.send(embed=embed)
        else:
            await ctx.send(res)

    @commands.command(name="takiptekiler")
    @commands.guild_only()
    async def liste_prefix(self, ctx):
        products = self.db.get_user_products(str(ctx.author.id))
        if not products:
            await ctx.send("📋 Takip ettiğiniz ürün bulunmuyor.")
            return
        
        embed = discord.Embed(title="📋 Takip Ettiğiniz Ürünler", color=discord.Color.blue())
        for p in products[:10]:
            embed.add_field(name=p['name'][:50], value=f"💰 {p['current_price']} TL\n🆔 `{p['product_id']}`", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="sil")
    @commands.guild_only()
    async def sil_prefix(self, ctx, product_id: str):
        if self.db.delete_subscription(str(ctx.author.id), product_id, str(ctx.guild.id)):
            await ctx.send(f"✅ `{product_id}` takipten çıkarıldı.")
        else:
            await ctx.send("❌ Ürün bulunamadı veya yetkiniz yok.")

    # Slash commands
    @app_commands.command(name="ekle", description="Ürün ekle")
    async def ekle_slash(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
        gid = str(interaction.guild.id) if interaction.guild else None
        success, res = await self._add_logic(url, gid, str(interaction.user.id), str(interaction.channel_id))
        if success:
            await interaction.followup.send(f"✅ **{res['name']}** takibe alındı.")
        else:
            await interaction.followup.send(res)

async def setup(bot):
    await bot.add_cog(ProductCommands(bot))
