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


class SSSView(discord.ui.View):
    """#sss butonlu soru-cevap sistemi — cevaplar ephemeral embed."""

    SORULAR = {
        "📦 Ürün nasıl takip edilir?":
            "`/ekle` komutunu `#komutlar` kanalında kullan.\n"
            "Trendyol ürün linkini yapıştırman yeterli — bot fiyatı "
            "otomatik izlemeye başlar.",
        "🔔 Bildirim neden gelmiyor?":
            "1. Rol seçmiş misin? `#rol-seçimi` panelinden 🔔 Fiyat Bildirim al.\n"
            "2. Bildirim kanalı doğru mu? `/bildirim-kanal` ile kontrol et.\n"
            "3. Ürün gerçekten düştü mü? Web panelinden geçmişe bak.",
        "⏰ Alarm nasıl kurulur?":
            "`/alarm <ürün-id> <hedef-fiyat> alt` — fiyat düşünce DM + kanal "
            "bildirimi alırsın.\n`/alarmlar` ile listeleyip `/alarm-sil` ile "
            "kaldırabilirsin.",
        "📈 Fiyat geçmişi nerede?":
            "Web panelinde her ürünün sayfası var: grafik, en düşük/en yüksek, "
            "değişim yüzdesi.\n" + "https://trendcord.miracdeveloper.com.tr/dashboard",
        "🎫 Destek nasıl açılır?":
            "`#destek-paneli` kanalındaki menüden tür seç — özel thread açılır, "
            "sadece sen ve ekip görür.",
        "💰 Bu hizmet ücretli mi?":
            "Hayır — Trendcord temel özellikleriyle **tamamen ücretsizdir**. "
            "7/24 bulut altyapısında çalışır.",
    }

    def __init__(self):
        super().__init__(timeout=None)
        for i, soru in enumerate(self.SORULAR):
            btn = discord.ui.Button(label=soru.split(" ", 1)[1][:80], row=i // 3,
                                    style=discord.ButtonStyle.secondary)

            async def cb(interaction: discord.Interaction, s=soru):
                e = discord.Embed(title=s, description=self.SORULAR[s],
                                  color=0xF27A1A)
                await interaction.response.send_message(embed=e, ephemeral=True)
            btn.callback = cb
            self.add_item(btn)
