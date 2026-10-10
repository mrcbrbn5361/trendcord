import asyncio
import discord
import os
import logging
from discord.ext import commands
from discord import app_commands

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

logger = logging.getLogger("Trendcord")

CID_PRODUCT_LIST = "tc:urun-liste"
MAX_PICKER_OPTIONS = 25


def _owner_id() -> str:
    return str(os.getenv("OWNER_ID", "") or "").strip()


class ProductPickerView(discord.ui.View):
    """Urun seim menusu -> onay butonlari (ephemeral, yalnizca bu kullanim icin)."""

    def __init__(self, products: list):
        super().__init__(timeout=300)
        self.products = products[:MAX_PICKER_OPTIONS]
        self.selected = None
        opts = []
        for i, p in enumerate(self.products):
            fiyat = float(p.get("current_price") or 0)
            opts.append(discord.SelectOption(
                label=p["name"][:100],
                description=f"{fiyat:.2f} TL • {p['product_id']}"[:100],
                value=str(i)))
        self.select_menu = discord.ui.Select(placeholder="Silinecek ürünü seç…",
                                             options=opts, min_values=1, max_values=1)
        self.select_menu.callback = self._on_select
        self.add_item(self.select_menu)
        self.confirm_btn = discord.ui.Button(label="🗑️ Sil", style=discord.ButtonStyle.danger)
        self.confirm_btn.callback = self._on_confirm
        self.add_item(self.confirm_btn)
        self.cancel_btn = discord.ui.Button(label="Vazgeç", style=discord.ButtonStyle.secondary)
        self.cancel_btn.callback = self._on_cancel
        self.add_item(self.cancel_btn)
        self.disable_controls()

    def _current(self):
        if self.selected is None:
            return None
        return self.products[int(self.selected)]

    def disable_controls(self):
        self.confirm_btn.disabled = self.selected is None

    @property
    def has_items(self):
        return bool(self.products)

    async def _on_select(self, interaction: discord.Interaction):
        self.selected = self.select_menu.values[0]
        self.confirm_btn.disabled = False
        p = self._current()
        await interaction.response.edit_message(
            content=f"**{p['name'][:100]}** — `{p['product_id']}` silinecek. Onaylıyor musun?",
            view=self)

    async def _on_confirm(self, interaction: discord.Interaction):
        p = self._current()
        if p is None:
            await interaction.response.send_message("⏳ Önce ürün seçmelisin.", ephemeral=True)
            return
        await interaction.response.defer()
        bot = interaction.client
        db = bot.db
        res = db.delete_product(p["product_id"])
        e = discord.Embed(title="🗑️ Ürün Silindi" if res["product"] else "❌ Silinemedi",
                          color=0xF27A1A if res["product"] else 0xDC2626)
        e.description = f"**{p['name'][:120]}**\n`{p['product_id']}`"
        if res["alerts"]:
            e.add_field(name="🗑️ Bağlı alarmlar",
                        value=f"{res['alerts']} alarm da silindi", inline=False)
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(content=None, embed=e, view=self)

    async def _on_cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="İptal edildi.", view=None)
        self.stop()


class ProductListView(discord.ui.View):
    """/takiptekiler mesajindaki kalici buton (sabit custom_id -> restart sonrasi calisir)."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🗑️ Ürün Sil", style=discord.ButtonStyle.danger,
                       custom_id=CID_PRODUCT_LIST, row=0)
    async def open_picker(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "Bu panel sunucuda kullanılır.", ephemeral=True)
            return
        cog = interaction.client.get_cog("ProductCommands")
        cands = cog._candidates(guild, interaction.user.id) if cog else []
        if not cands:
            await interaction.response.send_message(
                "📭 Bu sunucuda silinecek ürün yok.", ephemeral=True)
            return
        await interaction.response.send_message(
            "🗑️ **Silinecek ürünü seç:**", ephemeral=True,
            view=ProductPickerView(cands))


def register(bot):
    """Kalici butonu kaydet (bot acilirken cagrilir)."""
    from provisioner.common.views import add_persistent
    if not add_persistent(bot, ProductListView()):
        logger.error("Kalici 'Urun Sil' butonu kaydedilemedi.")


class ProductCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.orange = 0xF27A1A

    async def cog_load(self):
        logger.info("ProductCommands cog yüklendi.")

    async def cog_unload(self):
        logger.info("ProductCommands cog kaldırıldı.")

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            logger.error(f"Komut hatası ({ctx.command}): {error.original}")
            if isinstance(ctx, commands.Context):
                await ctx.send("❌ Bir hata oluştu. Lütfen tekrar deneyin.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Eksik parametre: `{error.param.name}`")
        else:
            logger.error(f"Beklenmeyen hata ({ctx.command}): {error}")

    async def _handle_add(self, target, url):
        data = self.bot.scraper.scrape_product(url)
        if data:
            if isinstance(target, commands.Context):
                gid = str(target.guild.id) if target.guild else "0"
                uid = str(target.author.id)
                uname = str(target.author.name)
                cid = str(target.channel.id)
                author = target.author
            else:
                gid = str(target.guild_id) if target.guild_id else "0"
                uid = str(target.user.id)
                uname = str(target.user.name)
                cid = str(target.channel_id)
                author = target.user

            if author.avatar:
                avatar_url = author.avatar.url
            else:
                avatar_url = f"https://cdn.discordapp.com/embed/avatars/{(author.id >> 22) % 6}.png"

            self.bot.db.add_product(data, gid, uid, cid, username=uname, avatar_url=avatar_url)

            embed = discord.Embed(title="✅ Takip Başlatıldı", url=data['url'], color=self.orange)
            if data.get('image_url'):
                embed.set_thumbnail(url=data['image_url'])
            embed.add_field(name="Ürün", value=data['name'][:100], inline=False)
            
            satis = data.get('current_price', 0)
            sepet = data.get('basket_price', 0)
            indirim = data.get('discount_pct', 0)
            kampanya = data.get('campaign_name', '')
            
            fiyat_txt = f"**{satis:.2f} TL**"
            if sepet and sepet < satis:
                fiyat_txt += f"\n Sepette: **{sepet:.2f} TL**"
            embed.add_field(name="Fiyat", value=fiyat_txt, inline=True)
            
            if indirim and indirim > 0:
                embed.add_field(name="İndirim", value=f"**%{indirim:.0f}**", inline=True)
            if kampanya:
                embed.add_field(name="Kampanya", value=kampanya, inline=True)
            
            embed.add_field(name="ID", value=f"`{data['product_id']}`", inline=True)

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

    @commands.hybrid_command(name="ekle", description="Trendyol ürününü takip et")
    async def ekle(self, ctx, url: str):
        """Trendyol ürün linkini takibe alır."""
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer(thinking=True)
        else:
            async with ctx.typing():  # Prefix komutları için typing indicator
                await self._handle_add(ctx, url)
                return
        await self._handle_add(ctx, url)

    async def _handle_list(self, target):
        if isinstance(target, commands.Context):
            gid = str(target.guild.id) if target.guild else "0"
        else:
            gid = str(target.guild_id) if target.guild_id else "0"

        prods = self.bot.db.get_all_products(guild_id=gid)

        if prods:
            embed = discord.Embed(title="📋 Takip Listesi", color=self.orange)
            for p in prods[:10]:
                fiyat = self.bot.db._safe_float(p['current_price'])
                embed.add_field(
                    name=p['name'][:50],
                    value=f"{fiyat:.2f} TL | ID: `{p['product_id']}`",
                    inline=False
                )
            if len(prods) > 10:
                embed.set_footer(text=f"+{len(prods) - 10} ürün daha")
            view = ProductListView() if gid != "0" else None
            if isinstance(target, commands.Context):
                await target.send(embed=embed, view=view)
            else:
                await target.followup.send(embed=embed, view=view)
        else:
            msg = "📭 Liste boş."
            if isinstance(target, commands.Context):
                await target.send(msg)
            else:
                await target.followup.send(msg)

    @commands.hybrid_command(name="takiptekiler", description="Takip edilen ürünleri listele")
    async def takiptekiler(self, ctx):
        """Sunucudaki takip edilen ürünleri listeler."""
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()
        await self._handle_list(ctx)

    # ---------- silme yardimcilari ----------
    def _can_delete(self, guild, user_id, product) -> bool:
        """Kendi urununu her zaman; sunucu yoneticisi her urunu silebilir."""
        if str(product.get('user_id')) == str(user_id):
            return True
        if guild is None:
            return False
        perms = guild.get_member(int(user_id))
        perms = perms.guild_permissions if perms else None
        return bool(perms and (perms.manage_guild or perms.administrator))

    def _candidates(self, guild, user_id, query=None):
        """Silinebilecek urunler: once benim, sonra sunucunun digerleri."""
        if guild is None:
            return self.bot.db.search_products(query=query, limit=25)
        gid, uid = str(guild.id), str(user_id)
        mine = self.bot.db.search_products(guild_id=gid, user_id=uid,
                                          query=query, limit=25)
        others = []
        if self._is_manager(guild, user_id):
            others = [p for p in self.bot.db.search_products(guild_id=gid,
                                                            query=query, limit=50)
                      if str(p.get('user_id')) != uid][:25 - len(mine)]
        return mine + others

    def _is_manager(self, guild, user_id):
        if guild is None:
            return False
        m = guild.get_member(int(user_id))
        p = m.guild_permissions if m else None
        return bool(p and (p.manage_guild or p.administrator))

    async def _delete_and_reply(self, target, guild, user_id, product, confirm_text=None):
        res = self.bot.db.delete_product(product['product_id'])
        if not res["product"]:
            emb = discord.Embed(title="❌ Silinemedi", color=discord.Color.red(),
                                description=f"`{product['product_id']}` bulunamadı.")
        else:
            emb = discord.Embed(title="🗑️ Ürün Silindi", color=self.orange)
            emb.description = f"**{product['name'][:120]}**\n`{product['product_id']}`"
            if res["alerts"]:
                emb.add_field(name="🗑️ Bağlı alarmlar",
                              value=f"{res['alerts']} alarm da silindi", inline=False)
        if confirm_text:
            emb.set_footer(text=confirm_text)
        if isinstance(target, commands.Context):
            await target.send(embed=emb)
        else:
            await target.followup.send(embed=emb)
        return res

    @commands.hybrid_command(name="sil", description="Takip edilen ürünü siler (ID veya isim)")
    @app_commands.describe(sorgu="Ürün ID'si veya ürün adı. Boş bırakılırsa liste açılır.")
    async def sil(self, ctx, sorgu: str = ""):
        """sorgu: ürün ID'si veya adı (bos -> secim menusu)."""
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()
        else:
            await ctx.typing()

        guild = ctx.guild
        user_id = ctx.author.id
        sorgu = (sorgu or "").strip()

        # 1) Tam ID ile dogrudan sil
        if sorgu.isdigit():
            p = self.bot.db.get_product(sorgu)
            if not p:
                await self._reply(ctx, f"❌ `{sorgu}` bulunamadı.", discord.Color.red())
                return
            if not self._can_delete(guild, user_id, p):
                await self._reply(ctx, "⛔ Bu ürün sana ait değil ve sunucuyu yönetmiyorsun.",
                                  discord.Color.red())
                return
            await self._delete_and_reply(ctx, guild, user_id, p)
            return

        # 2) Isim ile arama
        if sorgu:
            cands = self._candidates(guild, user_id, sorgu)
            if not cands:
                await self._reply(
                    ctx, f"🔍 **{sorgu}** için ürün bulunamadı. "
                         "`/takiptekiler` ile listeyi görebilirsin.", discord.Color.red())
                return
            if len(cands) == 1:
                await self._delete_and_reply(ctx, guild, user_id, cands[0])
                return
            await self._reply(ctx, f"🔍 **{len(cands)}** ürün eşleşti — "
                                  f"silmek için seç:", self.orange,
                          view=ProductPickerView(cands))
            return

        # 3) Secim menusu
        cands = self._candidates(guild, user_id)
        if not cands:
            await self._reply(ctx, "📭 Bu sunucuda silinecek ürün yok.", self.orange)
            return
        await self._reply(ctx, "🗑️ **Silinecek ürünü seç:**", self.orange,
                          view=ProductPickerView(cands))

    async def _reply(self, ctx, text, color, view=None):
        emb = discord.Embed(description=text, color=color)
        if isinstance(ctx, discord.Interaction):
            if ctx.response.is_done():
                await ctx.followup.send(embed=emb, view=view, ephemeral=True)
            else:
                await ctx.response.send_message(embed=emb, view=view, ephemeral=True)
        else:
            await ctx.send(embed=emb, view=view)

    @commands.hybrid_command(name="yardım", aliases=["yardim", "help"], description="Trendcord komutlarını göster")
    async def yardim(self, ctx):
        """Güncel komut listesi (botun kendi komutlarından otomatik)."""
        from provisioner.common.content import COMMAND_HELP, commands_help_text
        embed = discord.Embed(title="🧰 Trendcord Yardım", color=self.orange,
                              description="Trendyol fiyat takip botu — güncel komutlar")
        for baslik, cmdlar in COMMAND_HELP:
            embed.add_field(name=baslik, value=f"`{cmdlar}`", inline=False)
        embed.add_field(name="📌 Tüm komutlar", value=commands_help_text(),
                        inline=False)
        embed.set_footer(text="Trendcord • Trendyol Fiyat Takip Botu")
        if isinstance(ctx, commands.Context):
            await ctx.send(embed=embed)
        else:
            await ctx.response.send_message(embed=embed)

    # ---------- /icerik-guncelle ----------
    @commands.hybrid_command(
        name="icerik-guncelle",
        description="Trendcord kategorilerindeki tüm bot mesajlarını yeniler")
    @app_commands.describe(kapsam="tumu | resmi | buradaki")
    @app_commands.choices(kapsam=[
        app_commands.Choice(name="buradaki — sadece bu sunucu", value="buradaki"),
        app_commands.Choice(name="resmi — sadece resmi sunucu", value="resmi"),
        app_commands.Choice(name="tumu — botun olduğu tüm sunucular", value="tumu"),
    ])
    @commands.guild_only()
    async def icerik_guncelle(self, ctx, kapsam: str = "buradaki"):
        """Trendcord'un oluşturduğu tüm kanallardaki mesajları yeniden post eder."""
        if str(ctx.author.id) != _owner_id():
            await ctx.reply("⛔ Bu komut yalnızca bot sahibine açık.", ephemeral=True)
            return
        if kapsam == "buradaki":
            hedefler = [ctx.guild]
        elif kapsam == "resmi":
            from provisioner.common import official_guard as oguard
            hedefler = [g for g in self.bot.guilds if oguard.is_official(g.id)]
        else:
            hedefler = list(self.bot.guilds)

        if ctx.interaction:
            await ctx.interaction.response.defer(thinking=True)
        else:
            await ctx.defer()
        from provisioner.common.content import refresh_guild_content
        ok, hatali, toplam_silinen = [], [], 0
        toplam = 0
        for guild in hedefler:
            try:
                r = await refresh_guild_content(guild, db=self.bot.db, force=True)
                toplam_silinen += r.get("deleted", 0)
                toplam += r.get("channels", 0)
                ok.append(f"{r['guild_name']} → {r['channels']} kanal, "
                          f"{r.get('deleted', 0)} mesaj temizlendi")
            except Exception as e:
                hatali.append(f"{guild.name}: {type(e).__name__}")
            await asyncio.sleep(0.4)

        embed = discord.Embed(title="🧹 İçerik Güncellendi", color=self.orange,
                              description=f"Kapsam: **{kapsam}** · Sunucu: **{len(hedefler)}**")
        embed.add_field(name="Yenilenen kanal", value=str(toplam), inline=True)
        embed.add_field(name="🗑️ Silinen mesaj", value=str(toplam_silinen), inline=True)
        embed.add_field(name="Başarılı sunucu", value=str(len(ok)), inline=True)
        if ok:
            embed.add_field(name="Detay", value="\n".join(ok[:25]), inline=False)
        if hatali:
            embed.add_field(name="❌ Hatalı", value="\n".join(hatali[:15]), inline=False)
        # Context.send() hem message baglaminda hem defer edilmis
        # interaction'da calisir (discord.py 2.7'de Context.followup yok).
        await ctx.send(embed=embed, ephemeral=True)

    @commands.command(name="istatistik", aliases=["stats", "bilgi"])
    @commands.is_owner()
    async def system_stats(self, ctx):
        """Sadece bot sahibinin görebileceği sistem metrikleri."""
        if HAS_PSUTIL:
            process = psutil.Process(os.getpid())
            ram_usage = process.memory_info().rss / (1024 * 1024)
        else:
            ram_usage = 0.0

        db_path = "data/trendyol_tracker.sqlite"
        db_size = os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0.0

        guild_count = len(self.bot.guilds)
        total_products = len(self.bot.db.get_all_products())
        ping = int(self.bot.latency * 1000)

        embed = discord.Embed(
            title="SİSTEM METRİKLERİ",
            description="Trendcord anlık donanım ve ağ istatistikleri.",
            color=self.orange
        )
        embed.add_field(name="Sunucu", value=f"**{guild_count}**", inline=True)
        embed.add_field(name="Ürün", value=f"**{total_products}**", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="RAM", value=f"**{ram_usage:.2f}** MB", inline=True)
        embed.add_field(name="DB", value=f"**{db_size:.2f}** MB", inline=True)
        embed.add_field(name="Gecikme", value=f"**{ping}** ms", inline=True)
        embed.set_footer(text=f"Trendcord Core v2.0")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ProductCommands(bot))
