import discord
import logging
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger("Trendcord")

class Compare(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.orange = 0xF27A1A

    async def cog_load(self):
        logger.info("Compare cog yüklendi.")

    async def cog_unload(self):
        logger.info("Compare cog kaldırıldı.")

    @commands.hybrid_command(name="karşılaştır", aliases=["karsilastir", "compare"], description="Ürünleri karşılaştır")
    async def compare_products(self, ctx, product_id1: str = None, product_id2: str = None):
        """Sunucudaki ürünleri karşılaştırır. İki ID verilirse yan yana gösterir."""
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()
        else:
            async with ctx.typing():  # Prefix komutları için typing indicator
                await self._do_compare(ctx, product_id1, product_id2)
                return
        await self._do_compare(ctx, product_id1, product_id2)

    async def _do_compare(self, ctx, product_id1, product_id2):

        gid = str(ctx.guild.id) if ctx.guild else "0"
        products = self.bot.db.get_guild_compare(gid)

        if not products:
            msg = "📭 Bu sunucuda henüz takip edilen ürün yok."
            if isinstance(ctx, commands.Context):
                await ctx.send(msg)
            else:
                await ctx.followup.send(msg)
            return

        if product_id1 and product_id2:
            p1 = next((p for p in products if p['product_id'] == product_id1), None)
            p2 = next((p for p in products if p['product_id'] == product_id2), None)

            if not p1 or not p2:
                msg = "❌ Her iki ürün ID'si de bulunamadı."
                if isinstance(ctx, commands.Context):
                    await ctx.send(msg)
                else:
                    await ctx.followup.send(msg)
                return

            embed = discord.Embed(title="📊 Ürün Karşılaştırması", color=self.orange)

            def format_product(p, side):
                discount = p.get('discount_pct', 0)
                savings = (p.get('original_price', 0) or 0) - (p.get('current_price', 0) or 0)
                return (
                    f"**{p['name'][:60]}**\n"
                    f"Güncel: **{p['current_price']:.2f} TL**\n"
                    f"Orijinal: ~~{p.get('original_price', 0):.2f} TL~~\n"
                    f"İndirim: **%{discount:.1f}**\n"
                    f"Tasarruf: {savings:.2f} TL\n"
                    f"Ekleyen: {p.get('username', 'N/A')}"
                )

            embed.add_field(name=f"◀ {p1['name'][:25]}", value=format_product(p1, "left"), inline=True)
            embed.add_field(name="\u200b", value="**VS**", inline=True)
            embed.add_field(name=f"{p2['name'][:25]} ▶", value=format_product(p2, "right"), inline=True)

            if isinstance(ctx, commands.Context):
                await ctx.send(embed=embed)
            else:
                await ctx.followup.send(embed=embed)
        else:
            embed = discord.Embed(
                title="📊 Sunucu Ürün Karşılaştırması",
                description=f"**{ctx.guild.name if ctx.guild else 'Sunucu'}** - {len(products)} ürün",
                color=self.orange
            )

            sorted_products = sorted(products, key=lambda x: x.get('discount_pct', 0), reverse=True)

            for i, p in enumerate(sorted_products[:8], 1):
                discount = p.get('discount_pct', 0)
                current = p.get('current_price', 0) or 0
                original = p.get('original_price', 0) or 0
                savings = original - current if original > current else 0

                medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"**{i}.**"
                embed.add_field(
                    name=f"{medal} {p['name'][:40]}",
                    value=f"**{current:.0f} TL** ~~{original:.0f} TL~~ | %{discount:.1f} indirim",
                    inline=False
                )

            if len(products) > 8:
                embed.set_footer(text=f"...ve {len(products) - 8} ürün daha")

            if isinstance(ctx, commands.Context):
                await ctx.send(embed=embed)
            else:
                await ctx.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Compare(bot))
