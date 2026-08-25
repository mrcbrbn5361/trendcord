import discord
import logging
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger("Trendcord")

class PriceAlerts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.orange = 0xF27A1A

    async def cog_load(self):
        logger.info("PriceAlerts cog yüklendi.")

    async def cog_unload(self):
        logger.info("PriceAlerts cog kaldırıldı.")

    @commands.hybrid_command(name="alarm", description="Fiyat alarmı kur")
    async def set_alert(self, ctx, product_id: str, target_price: float, direction: str = "alt"):
        """Belirli bir fiyatta bildirim almak için alarm kurar.
        
        direction: 'alt' (fiyat düşünce) veya 'üzeri' (fiyat yükseldiğinde)
        """
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()

        if direction.lower() not in ['alt', 'üzeri', 'above', 'below']:
            msg = "❌ Geçersiz yön. `alt` veya `üzeri` kullanın."
            if isinstance(ctx, commands.Context):
                await ctx.send(msg)
            else:
                await ctx.followup.send(msg)
            return

        dir_map = {'alt': 'below', 'üzeri': 'above', 'below': 'below', 'above': 'above'}
        dir_val = dir_map[direction.lower()]

        products = self.bot.db.get_all_products(guild_id=str(ctx.guild.id) if ctx.guild else None)
        product = next((p for p in products if p['product_id'] == product_id), None)

        if not product:
            msg = f"❌ `{product_id}` ID'li ürün bulunamadı. `/takiptekiler` ile ürün listesini kontrol edin."
            if isinstance(ctx, commands.Context):
                await ctx.send(msg)
            else:
                await ctx.followup.send(msg)
            return

        gid = str(ctx.guild.id) if ctx.guild else "0"
        cid = str(ctx.channel.id)
        uid = str(ctx.author.id)

        alert_id = self.bot.db.add_alert(product_id, uid, gid, cid, target_price, dir_val)

        if alert_id:
            embed = discord.Embed(title="🔔 Fiyat Alarmı Kuruldu", color=self.orange)
            embed.add_field(name="Ürün", value=product['name'][:80], inline=False)
            embed.add_field(name="Mevcut Fiyat", value=f"**{product['current_price']:.2f} TL**", inline=True)
            embed.add_field(name="Hedef Fiyat", value=f"**{target_price:.2f} TL**", inline=True)
            emoji = "📉" if dir_val == 'below' else "📈"
            embed.add_field(name="Yön", value=f"{emoji} {'Fiyat düşünce' if dir_val == 'below' else 'Fiyat yükseldiğinde'}", inline=True)
            embed.set_footer(text=f"Alarm ID: {alert_id}")
            msg_obj = embed
        else:
            msg_obj = "❌ Alarm oluşturulamadı."

        if isinstance(ctx, commands.Context):
            await ctx.send(embed=msg_obj) if isinstance(msg_obj, discord.Embed) else await ctx.send(msg_obj)
        else:
            await ctx.followup.send(embed=msg_obj) if isinstance(msg_obj, discord.Embed) else await ctx.followup.send(msg_obj)

    @commands.hybrid_command(name="alarmlar", description="Aktif fiyat alarmlarını listele")
    async def list_alerts(self, ctx):
        """Kullanıcının aktif fiyat alarmlarını listeler."""
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()

        uid = str(ctx.author.id)
        alerts = self.bot.db.get_user_alerts(uid)

        if not alerts:
            msg = "📭 Hiç aktif alarmınız yok."
            if isinstance(ctx, commands.Context):
                await ctx.send(msg)
            else:
                await ctx.followup.send(msg)
            return

        embed = discord.Embed(title="🔔 Fiyat Alarmlarım", color=self.orange)
        for a in alerts[:10]:
            emoji = "📉" if a.get('direction') == 'below' else "📈"
            current = f"{a['current_price']:.2f} TL" if a.get('current_price') else "N/A"
            embed.add_field(
                name=f"{emoji} {a.get('product_name', 'Ürün')[:40]}",
                value=f"Mevcut: {current}\nHedef: **{a['target_price']:.2f} TL**\nID: `{a['id']}`",
                inline=False
            )
        embed.set_footer(text=f"Toplam {len(alerts)} alarm aktif")

        if isinstance(ctx, commands.Context):
            await ctx.send(embed=embed)
        else:
            await ctx.followup.send(embed=embed)

    @commands.hybrid_command(name="alarm-sil", description="Fiyat alarmını sil")
    async def delete_alert(self, ctx, alert_id: int):
        """Belirtilen fiyat alarmını kaldırır."""
        uid = str(ctx.author.id)
        res = self.bot.db.delete_alert(alert_id, uid)
        msg = f"✅ Alarm `{alert_id}` silindi." if res else "❌ Alarm bulunamadı veya size ait değil."
        if isinstance(ctx, commands.Context):
            await ctx.send(msg)
        else:
            await ctx.response.send_message(msg)

async def setup(bot):
    await bot.add_cog(PriceAlerts(bot))
