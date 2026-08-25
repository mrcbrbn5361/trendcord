"""Etkilesim panelleri: rol secimi (resmi) + destek paneli (4.6).

G5: webhook kullanilmaz; tum islemler bot hesabiyla yapilir.
"""
import logging

import discord

from provisioner.official import data as odata

logger = logging.getLogger("Trendcord")


class RolePanelView(discord.ui.View):
    """Resmi sunucu rol-seçimi paneli — yalnizca whitelist roller (3.3)."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(placeholder="Bildirim / ilgi rollerini seç",
                       min_values=0, max_values=len(odata.SELF_ASSIGNABLE),
                       options=[discord.SelectOption(label=n, emoji=n.split(" ")[0])
                                for n in odata.SELF_ASSIGNABLE])
    async def pick(self, interaction: discord.Interaction, select: discord.ui.Select):
        if not interaction.guild:
            await interaction.response.send_message("Bu panel sunucuda kullanılır.",
                                                    ephemeral=True)
            return
        member = interaction.user
        added, removed = [], []
        for name in odata.SELF_ASSIGNABLE:
            role = discord.utils.find(lambda r: r.name == name, interaction.guild.roles)
            if not role:
                continue
            if name in select.values and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Rol paneli (self-assign)")
                    added.append(name)
                except Exception:
                    pass
            elif name not in select.values and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Rol paneli (self-assign)")
                    removed.append(name)
                except Exception:
                    pass
        msg = f"✅ Eklendi: {', '.join(added) or '—'}\n❌ Kaldırıldı: {', '.join(removed) or '—'}"
        await interaction.response.send_message(msg, ephemeral=True)


class TicketPanelView(discord.ui.View):
    """Destek paneli — private thread acar (4.6); izin yoksa DM fallback."""

    TURULER = ["Bot Kullanımı", "Fiyat Takibi", "Ürün Sorunu", "Ödeme/Abonelik",
               "Partnerlik", "Bug Bildirimi", "Özellik Talebi", "Diğer"]

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(placeholder="Destek türü seç", min_values=1, max_values=1,
                       options=[discord.SelectOption(label=t) for t in TURULER])
    async def pick(self, interaction: discord.Interaction, select: discord.ui.Select):
        konu = select.values[0]
        me = interaction.guild.me if interaction.guild else None
        can_thread = False
        if me:
            perms = interaction.channel.permissions_for(me)
            can_thread = perms.manage_threads or perms.manage_channels
        if can_thread:
            try:
                thread = await interaction.channel.create_thread(
                    name=f"[{konu}] {interaction.user.display_name}"[:100],
                    type=discord.ChannelType.private_thread,
                    reason="Trendcord destek talebi",
                    auto_archive_duration=1440)
                await thread.send(
                    f"🎫 **{konu}** talebiniz açıldı {interaction.user.mention}.\n"
                    "Sorununuzu yazın; destek ekibi en kısa sürede dönecek.")
                await interaction.response.send_message(
                    f"✅ Destek talebin açıldı: {thread.mention}", ephemeral=True)
                return
            except Exception as e:
                logger.warning(f"[Ticket] thread acilamadi: {e}")
        try:
            await interaction.user.send(
                "🎫 Destek sistemini kullanamıyoruz (izin eksik). "
                "Sorununuzu resmi sunucudan paylaşabilirsiniz.")
            await interaction.response.send_message(
                "📩 Destek talebi için size DM attım.", ephemeral=True)
        except Exception:
            await interaction.response.send_message(
                "⚠️ Destek talebi açılamadı (izin eksik) ve DM gönderilemedi.",
                ephemeral=True)
