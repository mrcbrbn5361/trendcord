"""Sunucu log sistemi — blueprint 10/15 (mod/mesaj/uye/sunucu/bot/sistem/ticket).

Yalnizca managed log kanali olan guildlerde yazar (resmi sunucu + isteyenler).
Her handler hatayi yutar — loglama asla ana akisi bozmaz.
"""
import logging

import discord
from discord.ext import commands

from provisioner.common.store import SetupStore

logger = logging.getLogger("Trendcord")

ORANGE = 0xF27A1A
RED = 0xED4245
GREEN = 0x57F287
BLUE = 0x5865F2
GRAY = 0x95A5A6

LOG_KEYS = {
    "mod": ("oh:mod-log", "mod-log"),
    "mesaj": ("oh:mesaj-log", "mesaj-log"),
    "uye": ("oh:uye-log", "uye-log"),
    "sunucu": ("oh:sunucu-log", "sunucu-log"),
    "bot": ("oh:bot-log", "bot-log"),
    "sistem": ("oh:sistem-log", "sistem-log"),
    "ticket": ("oh:ticket-log", "ticket-log"),
}


def _ts():
    from datetime import datetime, timezone
    return discord.utils.format_dt(datetime.now(timezone.utc), style="R")


class LogSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = SetupStore(bot.db)
        self._ready_logged = False

    async def cog_load(self):
        logger.info("LogSystem cog yüklendi.")

    # ---------- yardimcilar ----------
    def _ch(self, guild, kind):
        if guild is None:
            return None
        key, name = LOG_KEYS[kind]
        try:
            ent = self.store.entity(str(guild.id), key)
            if ent:
                ch = guild.get_channel(int(ent["discord_id"]))
                if ch:
                    return ch
        except Exception:
            pass
        return discord.utils.find(lambda c: c.name == name, guild.text_channels)

    async def log(self, guild, kind, embed):
        if guild is None:
            return
        ch = self._ch(guild, kind)
        if ch is None:
            return
        try:
            await ch.send(embed=embed)
        except Exception:
            pass

    def _base(self, title, color=GRAY):
        e = discord.Embed(title=title, color=color)
        e.timestamp = discord.utils.utcnow()
        return e

    # ---------- MESAJ LOG ----------
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        try:
            guild = self.bot.get_guild(payload.guild_id)
            if guild is None:
                return
            e = self._base("🗑️ Mesaj Silindi", RED)
            e.add_field(name="Kanal", value=f"<#{payload.channel_id}>", inline=True)
            e.add_field(name="Mesaj ID", value=str(payload.message_id), inline=True)
            cm = payload.cached_message
            if cm:
                e.add_field(name="Yazar", value=cm.author.mention, inline=True)
                icerik = (cm.content or "*(embed/embedsiz medya)*")[:1000]
                e.add_field(name="İçerik", value=icerik, inline=False)
                if cm.attachments:
                    e.add_field(name="Ekler",
                                value="\n".join(a.url for a in cm.attachments[:3]),
                                inline=False)
            else:
                e.description = "*(mesaj önbellekte yoktu — içerik bilinmiyor)*"
            await self.log(guild, "mesaj", e)
        except Exception as ex:
            logger.debug(f"[Log] mesaj silme: {ex}")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        try:
            if before.author.bot or before.content == after.content:
                return
            e = self._base("✏️ Mesaj Düzenlendi", ORANGE)
            e.add_field(name="Yazar", value=before.author.mention, inline=True)
            e.add_field(name="Kanal", value=before.channel.mention, inline=True)
            e.add_field(name="Önce", value=(before.content or "-")[:500], inline=False)
            e.add_field(name="Sonra", value=(after.content or "-")[:500], inline=False)
            e.add_field(name="Bağlantı", value=after.jump_url, inline=False)
            await self.log(before.guild, "mesaj", e)
        except Exception as ex:
            logger.debug(f"[Log] mesaj düzenleme: {ex}")

    # ---------- UYE LOG ----------
    @commands.Cog.listener()
    async def on_member_join(self, member):
        try:
            e = self._base("📥 Üye Katıldı", GREEN)
            e.add_field(name="Kullanıcı", value=f"{member.mention} (`{member}`)",
                        inline=True)
            olustur = int(member.created_at.timestamp())
            yeni = (discord.utils.utcnow() - member.created_at).days < 7
            e.add_field(name="Hesap Yaşı",
                        value=f"<t:{olustur}:R>" + (" ⚠️ YENİ HESAP" if yeni else ""),
                        inline=True)
            e.add_field(name="Üye Sayısı", value=str(member.guild.member_count),
                        inline=True)
            e.set_thumbnail(url=member.display_avatar.url)
            await self.log(member.guild, "uye", e)
        except Exception as ex:
            logger.debug(f"[Log] uye katildi: {ex}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        try:
            e = self._base("📤 Üye Ayrıldı", GRAY)
            e.add_field(name="Kullanıcı", value=f"`{member}`", inline=True)
            e.add_field(name="Üye Sayısı", value=str(member.guild.member_count),
                        inline=True)
            if member.joined_at:
                e.add_field(name="Katılmıştı",
                            value=discord.utils.format_dt(member.joined_at, "R"),
                            inline=True)
            await self.log(member.guild, "uye", e)
        except Exception as ex:
            logger.debug(f"[Log] uye ayrildi: {ex}")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        try:
            # nickname
            if before.nick != after.nick:
                e = self._base("📛 Takma Ad Değişti", BLUE)
                e.add_field(name="Kullanıcı", value=after.mention, inline=True)
                e.add_field(name="Önce", value=str(before.nick or "-"), inline=True)
                e.add_field(name="Sonra", value=str(after.nick or "-"), inline=True)
                await self.log(after.guild, "uye", e)
            # timeout (communication_disabled_until)
            if before.communication_disabled_until != after.communication_disabled_until:
                if after.communication_disabled_until:
                    e = self._base("🔇 Timeout Verildi", RED)
                    e.add_field(name="Kullanıcı", value=after.mention, inline=True)
                    e.add_field(name="Bitiş",
                                value=discord.utils.format_dt(
                                    after.communication_disabled_until, "R"),
                                    inline=True)
                    await self.log(after.guild, "mod", e)
                else:
                    e = self._base("🔊 Timeout Kaldırıldı", GREEN)
                    e.add_field(name="Kullanıcı", value=after.mention, inline=True)
                    await self.log(after.guild, "mod", e)
            # roller
            brole, arole = set(before.roles), set(after.roles)
            eklenen = [r for r in after.roles if r not in brole and not r.managed]
            kaldirilan = [r for r in before.roles if r not in arole and not r.managed]
            if eklenen or kaldirilan:
                e = self._base("🏷️ Rol Değişimi", BLUE)
                e.add_field(name="Kullanıcı", value=after.mention, inline=True)
                if eklenen:
                    e.add_field(name="Eklendi",
                                value=", ".join(r.mention for r in eklenen),
                                inline=False)
                if kaldirilan:
                    e.add_field(name="Kaldırıldı",
                                value=", ".join(r.mention for r in kaldirilan),
                                inline=False)
                await self.log(after.guild, "uye", e)
        except Exception as ex:
            logger.debug(f"[Log] uye guncelleme: {ex}")

    # ---------- MOD LOG ----------
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        try:
            e = self._base("🔨 Ban", RED)
            e.add_field(name="Kullanıcı", value=f"{user.mention} (`{user}`)",
                        inline=True)
            await self.log(guild, "mod", e)
        except Exception as ex:
            logger.debug(f"[Log] ban: {ex}")

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        try:
            e = self._base("♻️ Ban Kaldırıldı", GREEN)
            e.add_field(name="Kullanıcı", value=f"{user.mention} (`{user}`)",
                        inline=True)
            await self.log(guild, "mod", e)
        except Exception as ex:
            logger.debug(f"[Log] unban: {ex}")

    # ---------- SUNUCU LOG ----------
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        try:
            e = self._base("📁 Kanal Oluşturuldu", GREEN)
            e.add_field(name="Kanal", value=channel.mention, inline=True)
            e.add_field(name="Tür", value=str(channel.type), inline=True)
            await self.log(channel.guild, "sunucu", e)
        except Exception as ex:
            logger.debug(f"[Log] kanal olusturma: {ex}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        try:
            ent = None
            try:
                ent = self.store.entity_by_discord_id(str(channel.id))
            except Exception:
                pass
            e = self._base("🗑️ Kanal Silindi", RED)
            e.add_field(name="Kanal", value=f"`#{channel.name}`", inline=True)
            e.add_field(name="Tür", value=str(channel.type), inline=True)
            if ent:
                e.add_field(name="Trendcord Kaydı", value=f"`{ent['key']}`",
                            inline=True)
            await self.log(channel.guild, "sunucu", e)
        except Exception as ex:
            logger.debug(f"[Log] kanal silme: {ex}")

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        try:
            farklar = []
            if before.name != after.name:
                farklar.append(f"İsim: `{before.name}` → `{after.name}`")
            if before.category != after.category:
                farklar.append(f"Kategori: {before.category} → {after.category}")
            if getattr(before, "slowmode_delay", 0) != getattr(after, "slowmode_delay", 0):
                farklar.append(f"Slowmode: {before.slowmode_delay} → {after.slowmode_delay}")
            if not farklar:
                return
            e = self._base("✏️ Kanal Güncellendi", ORANGE)
            e.add_field(name="Kanal", value=after.mention, inline=True)
            e.description = "\n".join(farklar)[:4000]
            await self.log(after.guild, "sunucu", e)
        except Exception as ex:
            logger.debug(f"[Log] kanal guncelleme: {ex}")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        try:
            e = self._base("🏷️ Rol Oluşturuldu", GREEN)
            e.add_field(name="Rol", value=role.mention, inline=True)
            await self.log(role.guild, "sunucu", e)
        except Exception as ex:
            logger.debug(f"[Log] rol olusturma: {ex}")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        try:
            if role.managed:
                return
            e = self._base("🗑️ Rol Silindi", RED)
            e.add_field(name="Rol", value=f"`{role.name}`", inline=True)
            await self.log(role.guild, "sunucu", e)
        except Exception as ex:
            logger.debug(f"[Log] rol silme: {ex}")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        try:
            farklar = []
            if before.name != after.name:
                farklar.append(f"İsim: `{before.name}` → `{after.name}`")
            if before.color != after.color:
                farklar.append(f"Renk: {before.color} → {after.color}")
            if before.permissions.value != after.permissions.value:
                farklar.append("İzinler değişti")
            if not farklar:
                return
            e = self._base("✏️ Rol Güncellendi", ORANGE)
            e.add_field(name="Rol", value=after.mention, inline=True)
            e.description = "\n".join(farklar)[:4000]
            await self.log(after.guild, "sunucu", e)
        except Exception as ex:
            logger.debug(f"[Log] rol guncelleme: {ex}")

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        try:
            e = self._base("🪝 Webhook Değişimi", ORANGE)
            e.add_field(name="Kanal", value=channel.mention, inline=True)
            await self.log(channel.guild, "sunucu", e)
        except Exception as ex:
            logger.debug(f"[Log] webhook: {ex}")

    # ---------- BOT LOG ----------
    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction, command):
        try:
            guild = interaction.guild
            if guild is None:
                return
            onemli = command.name in ("ekle", "sil", "alarm", "alarm-sil",
                                      "bildirim-ayarla")
            e = self._base(f"⌨️ /{command.name}", BLUE if onemli else GRAY)
            e.add_field(name="Kullanıcı", value=interaction.user.mention,
                        inline=True)
            e.add_field(name="Kanal", value=interaction.channel.mention
                        if interaction.channel else "-", inline=True)
            opts = getattr(interaction, "namespace", None)
            if opts and onemli:
                args = {k: v for k, v in vars(opts).items() if v is not None}
                if args:
                    e.add_field(name="Parametreler",
                                value=str(args)[:1000], inline=False)
            await self.log(guild, "bot", e)
        except Exception as ex:
            logger.debug(f"[Log] komut: {ex}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        try:
            e = self._base("📥 Sunucuya Eklendi", GREEN)
            e.add_field(name="Sunucu", value=f"{guild.name} (`{guild.id}`)",
                        inline=True)
            e.add_field(name="Üye", value=str(guild.member_count), inline=True)
            await self.log(guild, "bot", e)
        except Exception as ex:
            logger.debug(f"[Log] guild join: {ex}")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        try:
            e = self._base("📤 Sunucudan Ayrıldı", RED)
            e.add_field(name="Sunucu", value=f"{guild.name} (`{guild.id}`)",
                        inline=True)
            await self.log(guild, "bot", e)
        except Exception as ex:
            logger.debug(f"[Log] guild leave: {ex}")

    # ---------- SISTEM LOG ----------
    @commands.Cog.listener()
    async def on_ready(self):
        try:
            if self._ready_logged:
                return
            self._ready_logged = True
            e = self._base("🔄 Bot Yeniden Başlatıldı", GREEN)
            e.add_field(name="Sürüm", value=f"discord.py {discord.__version__}",
                        inline=True)
            e.add_field(name="Sunucu", value=str(len(self.bot.guilds)), inline=True)
            for guild in self.bot.guilds:
                if self._ch(guild, "sistem"):
                    await self.log(guild, "sistem", e)
                    break  # tek mesaj yeter (resmi sunucu)
        except Exception as ex:
            logger.debug(f"[Log] ready: {ex}")

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        try:
            guild = interaction.guild
            e = self._base("❌ Komut Hatası", RED)
            e.add_field(name="Komut", value=f"/{getattr(command_name(interaction, error), 'name', '?')}",
                        inline=True)
            e.add_field(name="Kullanıcı", value=interaction.user.mention
                        if interaction.user else "-", inline=True)
            e.description = f"```{type(error).__name__}: {error}```"[:4000]
            await self.log(guild, "sistem", e)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_ticket_closed(self, guild, ticket_info):
        """Ticket kapatma kaydi (views.py tetikler)."""
        try:
            e = self._base("🎫 Ticket Kapatıldı", ORANGE)
            for k, v in (ticket_info or {}).items():
                e.add_field(name=k, value=str(v)[:1000], inline=True)
            await self.log(guild, "ticket", e)
        except Exception as ex:
            logger.debug(f"[Log] ticket: {ex}")


def command_name(interaction, error):
    cm = getattr(interaction, "command", None)
    return cm or getattr(error, "command", "?")


async def setup(bot):
    await bot.add_cog(LogSystem(bot))
