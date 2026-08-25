"""Resmi sunucu provisioner komutu: /provision-official (Modul A).

Guard (3.1): yalnizca OFFICIAL_GUILD_ID eslesmesinde calisir; env tanimsizsa
komut tamamen devre disidir (G3).
"""
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands

from provisioner.official import runner
from provisioner.common.views import RolePanelView, TicketPanelView

logger = logging.getLogger("Trendcord")
ORANGE = 0xF27A1A


class ProvisionOfficial(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        if not runner.module_enabled():
            logger.warning("OFFICIAL_GUILD_ID tanımlı değil — provisioner modülü "
                           "devre dışı (G3).")
        else:
            logger.info("ProvisionOfficial cog yüklendi.")

    def _guard(self, ctx) -> str | None:
        """Donus None = gecti; str = reddetme sebebi."""
        if not runner.module_enabled():
            return "OFFICIAL_GUILD_ID tanımlı değil — bu komut kapalı."
        if str(ctx.guild_id if hasattr(ctx, 'guild_id') else ctx.guild.id) \
                != runner.official_guild_id():
            return "Bu komut yalnızca resmi Trendcord sunucusunda çalışır."
        return None

    def _is_privileged(self, ctx) -> bool:
        user = ctx.author
        if ctx.guild and user == ctx.guild.owner:
            return True
        if os.getenv("OWNER_ID") and str(user.id) == os.getenv("OWNER_ID"):
            return True
        return False

    @commands.hybrid_command(name="provision-official",
                             description="Resmi sunucu yapısını kur/doğrula (yetkili)")
    @app_commands.choices(eylem=[
        app_commands.Choice(name="apply — eksikleri kur", value="apply"),
        app_commands.Choice(name="verify — raporla (değişiklik yok)", value="verify"),
        app_commands.Choice(name="diff — fark listesi", value="diff"),
    ])
    @commands.guild_only()
    async def provision_official(self, ctx: commands.Context, eylem: str = "apply"):
        deny = self._guard(ctx)
        if deny:
            await ctx.reply(deny, ephemeral=True)
            return
        if not self._is_privileged(ctx):
            await ctx.reply("Bu komut yalnızca sunucu sahibi/OWNER kullanabilir.",
                            ephemeral=True)
            return
        await ctx.defer()

        guild = ctx.guild
        if eylem in ("verify", "diff"):
            report = await runner.verify_official(guild)
            embed = discord.Embed(title="🔍 Resmi Sunucu Doğrulama", color=ORANGE)
            if not report["missing_roles"] and not report["missing_channels"]:
                embed.description = "✅ Yapı blueprint ile uyumlu. Eksik yok."
            else:
                if report["missing_roles"]:
                    embed.add_field(
                        name=f"Eksik Roller ({len(report['missing_roles'])})",
                        value="\n".join(report["missing_roles"][:20]), inline=True)
                if report["missing_channels"]:
                    embed.add_field(
                        name=f"Eksik Kanallar ({len(report['missing_channels'])})",
                        value="\n".join(report["missing_channels"][:25]), inline=True)
            embed.add_field(name="Manuel Adımlar",
                            value="\n".join(f"[ ] {m}" for m in report["manual"])[:1024],
                            inline=False)
            await ctx.reply(embed=embed)
            return

        # apply
        report = await runner.apply_official(guild)
        embed = discord.Embed(
            title="🏗️ Resmi Sunucu Provisioning",
            color=ORANGE,
            description=f"Oluşturulan: **{len(report['created'])}** · "
                        f"Zaten var: **{len(report['skipped'])}** · "
                        f"Hata: **{len(report['errors'])}**")
        if report["created"]:
            embed.add_field(name="Oluşturulan",
                            value="\n".join(report["created"][:30]), inline=False)
        if report["errors"]:
            embed.add_field(name="Hatalar",
                            value="\n".join(report["errors"][:15]), inline=False)
        if report["automod"]:
            embed.add_field(name="AutoMod Kuralları",
                            value=", ".join(report["automod"]), inline=False)
        embed.add_field(name="Manuel Adımlar",
                        value="\n".join(f"[ ] {m}" for m in report["manual"])[:1024],
                        inline=False)
        await ctx.reply(embed=embed)

        # panelleri yerlestir (best-effort)
        try:
            await self._post_panels(guild)
        except Exception as e:
            logger.warning(f"[Official] panel yerlestirme: {e}")

    async def _post_panels(self, guild: discord.Guild):
        from provisioner.common.store import SetupStore
        store = SetupStore(self.bot.db)

        rol_ch = store.entity(guild.id, "oh:rol-secimi")
        if rol_ch:
            channel = guild.get_channel(int(rol_ch["discord_id"]))
            if channel:
                embed = discord.Embed(
                    title="🎨 Rol Seçimi",
                    description="Aşağıdaki menüden bildirim ve ilgi rollerini "
                                "seçebilirsin.\nAynı menüden seçimi kaldırınca rol "
                                "silinir.", color=ORANGE)
                await channel.send(embed=embed, view=RolePanelView())

        destek = store.entity(guild.id, "oh:destek-paneli")
        if destek:
            channel = guild.get_channel(int(destek["discord_id"]))
            if channel:
                embed = discord.Embed(
                    title="🎫 Destek",
                    description="Aşağıdan destek türünü seç, özel thread açalım.",
                    color=ORANGE)
                await channel.send(embed=embed, view=TicketPanelView())


async def setup(bot):
    await bot.add_cog(ProvisionOfficial(bot))
