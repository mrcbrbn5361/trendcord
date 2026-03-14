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

    async def _update_logic(self, product_id, user_id):
        product = self.db.get_product(product_id)
        if not product:
            return False, "❌ Ürün veritabanında bulunamadı."

        # Sadece kullanıcının takip edip etmediğine bakmıyoruz, genel bir güncelleme yapıyoruz
        # Ancak güvenlik için kullanıcının bu ürünü takip edip etmediğini kontrol edebiliriz
        user_products = self.db.get_user_products(user_id)
        if not any(p['product_id'] == product_id for p in user_products):
            return False, "❌ Bu ürünü takip etmiyorsunuz."

        new_data = self.scraper.scrape_product(product['url'])
        if not new_data or not new_data.get('success'):
            return False, "❌ Ürün bilgileri Trendyol'dan güncellenemedi."

        old_price = product['current_price']
        self.db.update_product_price(product_id, new_data['current_price'])
        return True, {"old_price": old_price, "new_price": new_data['current_price'], "name": new_data['name']}

    # --- PREFIX KOMUTLARI ---

    @commands.command(name="ekle")
    @commands.guild_only()
    async def ekle_prefix(self, ctx, url: str):
        success, res = await self._add_logic(url, str(ctx.guild.id), str(ctx.author.id), str(ctx.channel.id))
        if success:
            embed = discord.Embed(title="✅ Ürün Takibe Alındı", description=f"**{res['name']}** takipte!", color=discord.Color.green())
            embed.set_thumbnail(url=res['image_url'])
            embed.add_field(name="Fiyat", value=f"{res['current_price']} TL")
            await ctx.send(embed=embed)
        else:
            await ctx.send(res)

    @commands.command(name="takiptekiler", aliases=["liste"])
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
            await ctx.send("❌ Ürün bulunamadı veya bu sunucuda takip etmiyorsunuz.")

    @commands.command(name="güncelle", aliases=["guncelle"])
    @commands.guild_only()
    async def guncelle_prefix(self, ctx, product_id: str):
        success, res = await self._update_logic(product_id, str(ctx.author.id))
        if success:
            await ctx.send(f"✅ **{res['name']}** güncellendi. {res['old_price']} TL ➡️ {res['new_price']} TL")
        else:
            await ctx.send(res)

    # --- SLASH KOMUTLARI ---

    @app_commands.command(name="ekle", description="Takip edilecek Trendyol ürününü ekler.")
    @app_commands.describe(url="Trendyol ürün linki")
    async def ekle_slash(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
        gid = str(interaction.guild.id) if interaction.guild else None
        cid = str(interaction.channel_id) if interaction.channel_id else None
        success, res = await self._add_logic(url, gid, str(interaction.user.id), cid)
        if success:
            await interaction.followup.send(f"✅ **{res['name']}** takibe alındı.")
        else:
            await interaction.followup.send(res)

    @app_commands.command(name="takiptekiler", description="Takip ettiğiniz ürünleri listeler.")
    async def takiptekiler_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        products = self.db.get_user_products(str(interaction.user.id))
        if not products:
            await interaction.followup.send("📋 Takip ettiğiniz ürün bulunmuyor.")
            return

        embed = discord.Embed(title="📋 Takip Ettiğiniz Ürünler", color=discord.Color.blue())
        for p in products[:10]:
            embed.add_field(name=p['name'][:50], value=f"💰 {p['current_price']} TL\n🆔 `{p['product_id']}`", inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="sil", description="Bir ürünü takip listesinden çıkarır.")
    @app_commands.describe(product_id="Silinecek ürünün ID'si")
    async def sil_slash(self, interaction: discord.Interaction, product_id: str):
        gid = str(interaction.guild.id) if interaction.guild else None
        if self.db.delete_subscription(str(interaction.user.id), product_id, gid):
            await interaction.response.send_message(f"✅ `{product_id}` takipten çıkarıldı.")
        else:
            await interaction.response.send_message("❌ Ürün bulunamadı veya yetkiniz yok.")

    @app_commands.command(name="guncelle", description="Ürün bilgilerini manuel olarak günceller.")
    @app_commands.describe(product_id="Güncellenecek ürünün ID'si")
    async def guncelle_slash(self, interaction: discord.Interaction, product_id: str):
        await interaction.response.defer()
        success, res = await self._update_logic(product_id, str(interaction.user.id))
        if success:
            await interaction.followup.send(f"✅ **{res['name']}** güncellendi. {res['old_price']} TL ➡️ {res['new_price']} TL")
        else:
            await interaction.followup.send(res)

async def setup(bot):
    await bot.add_cog(ProductCommands(bot))
