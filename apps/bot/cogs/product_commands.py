import discord
from discord.ext import commands
from discord import app_commands


class ProductCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.orange = 0xF27A1A

    async def _handle_add(self, target, url):
        """Handle product addition from command or slash command."""
        data = await self.bot.loop.run_in_executor(
            None, self.bot.scraper.scrape_product, url
        )
        
        if data:
            gid = str(target.guild.id if hasattr(target, "guild") else target.guild_id)
            uid = str(target.author.id if hasattr(target, "author") else target.user.id)
            uname = str(target.author.name if hasattr(target, "author") else target.user.name)
            cid = str(target.channel.id if hasattr(target, "channel") else target.channel_id)
            
            author = target.author if hasattr(target, "author") else target.user
            if author.avatar:
                avatar_url = author.avatar.url
            else:
                avatar_url = f"https://cdn.discordapp.com/embed/avatars/{(author.id >> 22) % 6}.png"
            
            await self.bot.db.add_product(data, gid, uid, cid, uname, str(avatar_url))
            
            embed = discord.Embed(
                title="✅ Takip Başlatıldı",
                url=data["url"],
                color=self.orange
            )
            
            if data.get("image_url"):
                embed.set_thumbnail(url=data["image_url"])
            
            embed.add_field(name="Ürün", value=data["name"][:100], inline=False)
            embed.add_field(
                name="Fiyat",
                value=f"**{data['current_price']:.2f} TL**",
                inline=True
            )
            embed.add_field(
                name="ID",
                value=f"`{data['product_id']}`",
                inline=True
            )
            
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

    @commands.command(name="ekle")
    async def ekle_p(self, ctx, url: str):
        await self._handle_add(ctx, url)

    @app_commands.command(name="ekle", description="Ürün ekle")
    async def ekle_s(self, itn: discord.Interaction, url: str):
        await itn.response.defer(thinking=True)
        await self._handle_add(itn, url)

    @commands.command(name="takiptekiler")
    async def list_p(self, ctx):
        await self._handle_list(ctx)

    @app_commands.command(name="takiptekiler", description="Liste")
    async def list_s(self, itn: discord.Interaction):
        await itn.response.defer()
        await self._handle_list(itn)

    async def _handle_list(self, target):
        gid = str(target.guild.id if hasattr(target, "guild") else target.guild_id)
        prods = await self.bot.db.get_all_products(guild_id=gid)
        
        if prods:
            embed = discord.Embed(title="📋 Takip Listesi", color=self.orange)
            for p in prods[:10]:
                embed.add_field(
                    name=p["name"][:50],
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

    @commands.command(name="sil")
    async def sil_p(self, ctx, pid: str):
        res = await self.bot.db.delete_product(pid)
        await ctx.send(f"✅ Silindi: `{pid}`" if res else "❌ Bulunamadı.")

    @app_commands.command(name="sil", description="Ürün sil")
    async def sil_s(self, itn: discord.Interaction, pid: str):
        res = await self.bot.db.delete_product(pid)
        await itn.response.send_message(
            f"✅ Silindi: `{pid}`" if res else "❌ Bulunamadı."
        )

    @commands.command(name="yardım")
    async def help_p(self, ctx):
        embed = discord.Embed(title="Trendcord Yardım", color=self.orange)
        embed.add_field(name="!ekle <link>", value="Ürün ekler", inline=False)
        embed.add_field(name="!takiptekiler", value="Listeler", inline=False)
        embed.add_field(name="!sil <ID>", value="Siler", inline=False)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ProductCommands(bot))
