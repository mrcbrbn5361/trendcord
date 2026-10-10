import discord
import logging
import os
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger("Trendcord")


def _owner_id() -> str:
    return str(os.getenv("OWNER_ID", "") or "").strip()


class AdminTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.orange = 0xF27A1A

    async def cog_load(self):
        logger.info("AdminTools cog yüklendi.")

    async def cog_unload(self):
        logger.info("AdminTools cog kaldırıldı.")

    @commands.hybrid_command(name="fiyat-tazele",
                             description="Bayat kalan ürün fiyatlarını hemen tazeler (bot sahibi)")
    @app_commands.describe(kapsam="hepsi | sunucu")
    @app_commands.choices(kapsam=[
        app_commands.Choice(name="hepsi — tüm bayat ürünler", value="hepsi"),
        app_commands.Choice(name="sunucu — bu sunucudakiler", value="sunucu"),
    ])
    @commands.guild_only()
    async def fiyat_tazele(self, ctx, kapsam: str = "hepsi"):
        if str(ctx.author.id) != _owner_id():
            await ctx.reply("⛔ Bu komut yalnızca bot sahibine açık.", ephemeral=True)
            return
        await ctx.defer(thinking=True)
        import main as botmain
        gid = str(ctx.guild.id) if kapsam == "sunucu" else None
        if gid is None:
            bayat = self.bot.db.count_stale_products()
        else:
            bayat = len([p for p in self.bot.db.get_all_products(guild_id=gid)
                         if not p.get("last_checked")])
        n = await botmain.force_refresh(guild_id=gid)
        await ctx.followup.send(
            f"🔄 **{n}** ürün tazelendi (işaretli: {bayat}).", ephemeral=True)

    @commands.command(name="reload")
    @commands.is_owner()
    async def reload_cog(self, ctx, cog_name: str):
        """Tek bir cog'u yeniden yükler."""
        try:
            await self.bot.reload_extension(f"cogs.{cog_name}")
            await ctx.send(f"✅ `{cog_name}` yeniden yüklendi.")
        except Exception as e:
            await ctx.send(f"❌ Yeniden yükleme hatası: `{e}`")

    @commands.command(name="reloadall")
    @commands.is_owner()
    async def reload_all(self, ctx):
        """Tüm cog'ları yeniden yükler."""
        loaded = []
        failed = []
        for filename in __import__('os').listdir("cogs"):
            if filename.endswith(".py") and not filename.startswith("__"):
                name = filename[:-3]
                try:
                    await self.bot.reload_extension(f"cogs.{name}")
                    loaded.append(name)
                except Exception as e:
                    failed.append(f"{name}: {e}")

        embed = discord.Embed(title="🔄 Cog Yeniden Yükleme", color=self.orange)
        embed.add_field(name="✅ Başarılı", value=", ".join(loaded) if loaded else "Yok", inline=False)
        if failed:
            embed.add_field(name="❌ Başarısız", value="\n".join(failed), inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="coglist")
    @commands.is_owner()
    async def list_cogs(self, ctx):
        """Yüklenen cog'ları listeler."""
        cogs = list(self.bot.cogs.keys())
        embed = discord.Embed(title="📦 Yüklenen Cog'lar", color=self.orange,
            description="\n".join(f"• `{c}`" for c in cogs) or "Hiç cog yüklenmemiş.")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="bakım", description="Bakım modunu aç/kapat")
    @commands.is_owner()
    async def toggle_maintenance(self, ctx):
        """Bakım modunu açar veya kapatır."""
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()

        current = getattr(self.bot, 'maintenance_mode', False)
        self.bot.maintenance_mode = not current
        status = "🔴 Bakım modu AÇILDI" if self.bot.maintenance_mode else "🟢 Bakım modu KAPANDI"

        if isinstance(ctx, commands.Context):
            await ctx.send(status)
        else:
            await ctx.followup.send(status)

async def setup(bot):
    await bot.add_cog(AdminTools(bot))
