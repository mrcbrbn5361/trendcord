"""Client guild kurulum cog'u: /setup, /setup-kaldir + guild eventleri (Modul B)."""
import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from provisioner.common.store import SetupStore
from provisioner.common.analyzer import analyze_roles
from provisioner.common.views import TicketPanelView
from provisioner.common import content as ccontent
from provisioner.client import runner
from provisioner.client.data import CATEGORIES

logger = logging.getLogger("Trendcord")
ORANGE = 0xF27A1A
import os

AUTO_SETUP_DEFAULT = os.getenv("AUTO_SETUP_DEFAULT", "true").lower() in ("1", "true", "yes")


class ModuleSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Büyük İndirimler (≥%30)", value="big_deals",
                                 description="BOT_FEED kanalı: büyük-indirimler"),
            discord.SelectOption(label="Kuponlar", value="coupons",
                                 description="OPEN kanal: kuponlar"),
            discord.SelectOption(label="Topluluk Fırsatları", value="community_deals",
                                 description="OPEN kanal: fırsatlar"),
        ]
        super().__init__(placeholder="Opsiyonel modüller (isteğe bağlı)",
                         min_values=0, max_values=len(options), options=options)


class SetupPanel(discord.ui.View):
    def __init__(self, cog, analysis):
        super().__init__(timeout=180)
        self.cog = cog
        self.analysis = analysis
        self.modules = {}
        self.add_item(ModuleSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "Bu panel için **Sunucuyu Yönet** izni gerekir.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Kur", style=discord.ButtonStyle.success)
    async def kur(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        sel = next((c for c in self.children if isinstance(c, ModuleSelect)), None)
        modules = {v: True for v in (sel.values if sel else [])}
        self.cog.bot.db.set_guild_settings(str(interaction.guild_id), modules=modules)
        report = await runner.apply_setup(interaction.guild, modules=modules,
                                          analysis=self.analysis, db=self.bot.db)
        try:
            await self.cog.post_ticket_panel(interaction.guild)
        except Exception:
            pass
        await interaction.followup.send(embed=self.cog.report_embed(report))
        button.disabled = True
        try:
            await interaction.edit_original_response(view=self)
        except Exception:
            pass
        self.stop()

    @discord.ui.button(label="Vazgeç", style=discord.ButtonStyle.secondary)
    async def vazgec(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Kurulum iptal edildi.", view=None)
        self.stop()


class RemoveConfirm(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Evet, kaldır", style=discord.ButtonStyle.danger)
    async def evet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        report = await runner.remove_setup(interaction.guild, db=self.bot.db)
        embed = discord.Embed(title="🗑️ Kurulum Kaldırıldı", color=ORANGE,
                              description=f"Silinen: **{len(report['removed'])}** kaynak")
        if report["errors"]:
            embed.add_field(name="Hatalar", value="\n".join(report["errors"][:10]),
                            inline=False)
        await interaction.followup.send(embed=embed)
        self.stop()

    @discord.ui.button(label="Vazgeç", style=discord.ButtonStyle.secondary)
    async def vazgec(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Kaldırma iptal edildi.", view=None)
        self.stop()


class GuildSetup(commands.Cog):
    """Modul B komutlari ve guild eventleri."""

    def __init__(self, bot):
        self.bot = bot
        self.store = SetupStore(bot.db)

    async def cog_load(self):
        logger.info("GuildSetup cog yüklendi.")
        if not self.status_loop.is_running():
            self.status_loop.start()

    async def cog_unload(self):
        self.status_loop.cancel()

    # ---------- canli durum mesaji (#durum) ----------
    @tasks.loop(minutes=5)
    async def status_loop(self):
        for guild in list(self.bot.guilds):
            try:
                await ccontent.post_status_message(guild, db=self.bot.db)
            except Exception as e:
                logger.debug(f"[Durum] {guild.id}: {e}")

    @status_loop.before_loop
    async def before_status(self):
        await self.bot.wait_until_ready()

    # ---------- hos geldin sistemi (tum sunucular) ----------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            e = ccontent.b_welcome_member(member)
            hedef = None
            for key in ("oh:hosgeldin", "ch:hosgeldin", "hoş-geldin"):
                ent = self.store.entity(str(member.guild.id), key)
                if ent:
                    hedef = member.guild.get_channel(int(ent["discord_id"]))
                    if hedef:
                        break
            if hedef is None:
                hedef = discord.utils.find(
                    lambda c: c.name in ("hoş-geldin", "genel", "hoş-geldin"),
                    member.guild.text_channels)
            if hedef is None:
                hedef = member.guild.system_channel
            if hedef and hedef.permissions_for(member.guild.me).send_messages:
                await hedef.send(embed=e)
        except Exception as e:
            logger.error(f"[Welcome] {member.guild.id}: {e}")

    # ---------- /duyuru ----------
    @commands.hybrid_command(name="duyuru",
                             description="Duyurular kanalına embed duyuru gönderir")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    async def duyuru(self, ctx: commands.Context, baslik: str, mesaj: str,
                     rol: str = "yok"):
        """rol: yok | fiyat | indirim | kampanya | guncelleme"""
        rol_map = {
            "fiyat": "🔔 Fiyat Bildirim",
            "indirim": "🏷️ İndirim Bildirim",
            "kampanya": "🎁 Kampanya Bildirim",
            "guncelleme": "📰 Güncelleme Bildirim",
        }
        hedef = None
        for key in ("oh:duyurular", "ch:duyurular"):
            ent = self.store.entity(str(ctx.guild.id), key)
            if ent:
                hedef = ctx.guild.get_channel(int(ent["discord_id"]))
                if hedef:
                    break
        if hedef is None:
            hedef = discord.utils.find(lambda c: c.name == "duyurular",
                                       ctx.guild.text_channels) or ctx.channel
        e = discord.Embed(title=baslik, description=mesaj, color=ORANGE)
        e.set_author(name=ctx.author.display_name,
                     icon_url=ctx.author.display_avatar.url)
        e.set_footer(text="Trendcord Duyuru", 
                     icon_url=ccontent.IMG)
        icerik = None
        rname = rol_map.get(rol.lower())
        if rname:
            r = discord.utils.find(lambda x: x.name == rname, ctx.guild.roles)
            if r:
                icerik = r.mention
        await hedef.send(content=icerik, embed=e)
        await ctx.reply(f"✅ Duyuru {hedef.mention} kanalına gönderildi.",
                        ephemeral=True)

    # ---------- /destek ----------
    @commands.hybrid_command(name="destek",
                             description="Destek talebi panelini açar")
    @commands.guild_only()
    async def destek(self, ctx: commands.Context):
        e = discord.Embed(
            title="🎫 Destek Talebi",
            description="Aşağıdaki menüden destek türünü seç — özel bir thread "
                        "açılsın, sadece sen ve destek ekibi görsün.",
            color=ORANGE)
        await ctx.reply(embed=e, view=TicketPanelView(), ephemeral=True)

    # ---------- yardimcilar ----------
    def report_embed(self, report: dict) -> discord.Embed:
        status_map = {"RAN": ("✅", discord.Color.green()),
                      "PARTIAL": ("⚠️", ORANGE),
                      "FAILED": ("❌", discord.Color.red())}
        icon, color = status_map.get(report.get("status"), ("ℹ️", ORANGE))
        embed = discord.Embed(title=f"{icon} Kurulum Sonucu", color=color)
        if report.get("reason") == "missing_perms":
            embed.description = (
                "❗ Bot için **Kanalları Yönet** izni gerekli.\n"
                "Botu şu izinlerle yeniden davet edin:\n"
                f"`{' '.join(report.get('missing', []))}`")
            return embed
        if report.get("created"):
            embed.add_field(name=f"Oluşturulan ({len(report['created'])})",
                            value="\n".join(report["created"][:20]) or "—", inline=False)
        if report.get("skipped"):
            embed.add_field(name=f"Zaten Var ({len(report['skipped'])})",
                            value=", ".join(report["skipped"][:15]) or "—", inline=True)
        if report.get("errors"):
            embed.add_field(name=f"Hatalar ({len(report['errors'])})",
                            value="\n".join(report["errors"][:10]), inline=False)
        ar = report.get("analysis") or {}
        if ar:
            embed.add_field(
                name="Rol Analizi",
                value=(f"Admin: **{len(ar.get('admin_roles', []))}** · "
                       f"Mod: **{len(ar.get('mod_roles', []))}** · "
                       f"Destek: **{len(ar.get('support_hint', []))}**"),
                inline=False)
        return embed

    async def _preview_embed(self, guild, analysis) -> discord.Embed:
        embed = discord.Embed(
            title="📊 Trendcord Kurulum Önizleme",
            color=ORANGE,
            description="Rol oluşturulmayacak; mevcut roller analiz edilerek "
                        "kategori + kanallar açılacak.\n\u200b")
        admins = ", ".join(r["name"] for r in analysis["admin_roles"][:5]) or "—"
        mods = ", ".join(r["name"] for r in analysis["mod_roles"][:5]) or "—"
        embed.add_field(name="Tespit Edilen Admin Rolleri", value=admins, inline=True)
        embed.add_field(name="Mod Rolleri", value=mods, inline=True)
        kanallar = "\n".join(
            f"📂 **{c['name']}**\n" + "\n".join(f"└ #{ch['name']}" for ch in c["channels"])
            for c in CATEGORIES)
        embed.add_field(name="Oluşturulacak Yapı", value=kanallar[:1024], inline=False)
        embed.set_footer(text="Aşağıdan opsiyonel modülleri seçip 'Kur'a basın.")
        return embed

    # ---------- /setup ----------
    @commands.hybrid_command(name="setup",
                             description="Trendcord kanallarını sunucunuza kurar")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    async def setup_cmd(self, ctx: commands.Context,
                        eylem: str = "kur"):
        """eylem: kur | repair | status"""
        if not ctx.interaction:
            await ctx.send("Bu komut slash olarak kullanılmalı.")
            return
        await ctx.defer()

        if eylem == "status":
            ents = self.store.entities(str(ctx.guild.id))
            state = self.store.state(str(ctx.guild.id))
            embed = discord.Embed(title="📊 Kurulum Durumu", color=ORANGE)
            embed.add_field(name="Durum", value=state["status"] if state else "KURULMAMIŞ",
                            inline=True)
            embed.add_field(name="Yönetilen Kaynak", value=str(len(ents)), inline=True)
            if ents:
                embed.description = "\n".join(
                    f"`{e['key']}` → <#{e['discord_id']}>" for e in ents[:25])
            await ctx.reply(embed=embed)
            return

        missing = runner.check_permissions(ctx.guild)
        if missing and eylem != "status":
            embed = discord.Embed(title="❗ Yetersiz İzin", color=discord.Color.red(),
                                  description="Bot için gerekli izinler eksik:\n`"
                                              + "`, `".join(missing) + "`\n\n"
                                              "Botu yeniden davet edin: /botdavet")
            await ctx.reply(embed=embed)
            return

        analysis = analyze_roles(ctx.guild)
        self.store.save_state(str(ctx.guild.id), "CLIENT", "PENDING", analysis)

        if eylem == "repair":
            report = await runner.repair_setup(ctx.guild, db=self.bot.db)
            await ctx.reply(embed=self.report_embed(report))
            return

        panel = SetupPanel(self, analysis)
        await ctx.reply(embed=await self._preview_embed(ctx.guild, analysis),
                        view=panel)

    # ---------- /setup-kaldir ----------
    @commands.hybrid_command(name="setup-kaldir",
                             description="Trendcord'un kurduğu kanalları kaldırır")
    @app_commands.default_permissions(manage_guild=True)
    @commands.guild_only()
    async def setup_kaldir(self, ctx: commands.Context):
        if not ctx.interaction:
            await ctx.send("Bu komut slash olarak kullanılmalı.")
            return
        ents = self.store.entities(str(ctx.guild.id))
        if not ents:
            await ctx.reply("Kaldırılacak yönetilen kaynak yok.", ephemeral=True)
            return
        await ctx.reply(content=f"⚠️ **{len(ents)}** kanal/kategori silinecek "
                                "(yalnızca Trendcord'un kurdukları). Emin misiniz?",
                        view=RemoveConfirm())

    # ---------- EVENTLER (4.8) ----------
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        try:
            self.bot.db.ensure_guild_settings(str(guild.id))
            cfg = self.store.settings(str(guild.id))
            logger.info(f"[GuildJoin] {guild.name} ({guild.id}) — "
                        f"auto_setup={cfg['auto_setup']}")
            if not (cfg["auto_setup"] and AUTO_SETUP_DEFAULT):
                return
            missing = runner.check_permissions(guild)
            analysis = analyze_roles(guild)
            if missing:
                embed = discord.Embed(
                    title="👋 Trendcord eklendi — kurulum için izin gerekli",
                    color=ORANGE,
                    description="Kanallarımı kurabilmem için `Kanalları Yönet` izni "
                                "lazım. Botu doğru izinlerle davet edin, sonra "
                                "`/setup` çalıştırın.")
                await self._send_somewhere(guild, embed)
                return
            report = await runner.apply_setup(guild, modules=cfg["modules_parsed"],
                                              analysis=analysis, db=self.bot.db)
            embed = self.report_embed(report)
            embed.title = "✅ Trendcord kanalları kuruldu"
            await self._send_somewhere(guild, embed)
        except Exception as e:
            logger.error(f"[GuildJoin] {guild.id}: {e}")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        try:
            from datetime import datetime, timezone
            self.bot.db.set_guild_settings(str(guild.id),
                                           left_at=datetime.now(timezone.utc).isoformat())
            self.store.save_state(str(guild.id), "CLIENT", "REMOVED")
            logger.info(f"[GuildLeave] {guild.name} ({guild.id}) işaretlendi")
        except Exception as e:
            logger.error(f"[GuildLeave] {guild.id}: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        try:
            ent = self.store.entity_by_discord_id(str(channel.id))
            if ent:
                self.store.mark_deleted(ent["guild_id"], ent["key"])
                logger.info(f"[ChannelDelete] managed kaynak silindi: {ent['key']} "
                            f"({ent['guild_id']}) — /setup repair ile onarılır")
        except Exception as e:
            logger.error(f"[ChannelDelete] {e}")

    async def post_ticket_panel(self, guild: discord.Guild):
        """destek-paneli kanalina ticket panelini yerlestirir (4.6, best-effort)."""
        ent = self.store.entity(str(guild.id), "ch:destek-paneli")
        if not ent:
            return
        channel = guild.get_channel(int(ent["discord_id"]))
        if not channel:
            return
        for m in channel.history(limit=10):
            if m.author == guild.me and m.components:
                return  # panel zaten var
        embed = discord.Embed(
            title="🎫 Destek",
            description="Aşağıdan destek türünü seç, özel bir thread açalım.",
            color=ORANGE)
        await channel.send(embed=embed, view=TicketPanelView())

    async def _send_somewhere(self, guild, embed):
        for ch in guild.text_channels:
            perms = ch.permissions_for(guild.me)
            if perms.send_messages and perms.embed_links:
                await ch.send(embed=embed)
                return
        try:
            if guild.system_channel:
                await guild.system_channel.send(embed=embed)
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(GuildSetup(bot))
