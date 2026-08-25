"""Kanal icerik sistemi — her kanalin sabit embed/panel mesajlari.

Idempotent: her mesaj managed_entities'e 'MESSAGE' tipiyle kaydedilir
(key = msg:<kanal-key>); mesaj yasiyorsa tekrar post edilmez.
"""
import logging
import os

import discord

from provisioner.official.data import SELF_ASSIGNABLE

logger = logging.getLogger("Trendcord")

WEB = "https://trendcord.miracdeveloper.com.tr"
IMG = WEB + "/static/img/og-image.png"
ORANGE = 0xF27A1A


def invite_url(client_id: str) -> str:
    perms = 311385517136  # G2
    return (f"https://discord.com/api/oauth2/authorize?client_id={client_id}"
            f"&permissions={perms}&scope=bot%20applications.commands")


def E(title, desc, *, url=None, image=False, thumbnail=None):
    e = discord.Embed(title=title[:256], description=desc[:4096],
                      color=ORANGE, url=url)
    e.set_footer(text="Trendcord • Trendyol Fiyat Takip",
                 icon_url=IMG)
    if image:
        e.set_image(url=IMG)
    if thumbnail:
        e.set_thumbnail(url=thumbnail)
    return e


def link_view(*links):
    """URL butonlari — callback gerektirmez, restart sonrasi da calisir."""
    rows = [discord.ui.Button(label=l, url=u, row=0) for l, u in links]
    v = discord.ui.View(timeout=None)
    for b in rows:
        v.add_item(b)
    return v


# ---------------- icerik ureticileri ----------------

def _c(guild, *keys_names):
    """Kanal ismiyle arar; mention dondurur, yoksa #isim yazar."""
    try:
        for n in keys_names:
            ch = discord.utils.find(lambda c: c.name == n, guild.text_channels)
            if ch:
                return ch.mention
    except Exception:
        pass
    return "`#" + keys_names[-1] + "`"


def b_hosgeldin(g):
    e = E("👋 Trendcord'a Hoş Geldin!",
          f"{_c(g,'oh:hosgeldin','hoş-geldin')} • Sunucu haritası:\n\n"
          f"**1.** {_c(g,'oh:trendcord','trendcord')} — Trendcord nedir?\n"
          f"**2.** {_c(g,'oh:kullanım-rehberi','kullanım-rehberi')} — 3 adımda ilk ürününü takip et\n"
          f"**3.** {_c(g,'oh:rol-seçimi','rol-seçimi')} — bildirim rollerini seç\n"
          f"**4.** {_c(g,'oh:komutlar','komutlar')} — slash komut alanı\n"
          f"**5.** Sorun mu var? {_c(g,'oh:destek-paneli','destek-paneli')}\n\n"
          f"🌐 Web Paneli: {WEB}", image=True)
    return [(e, None)]


def b_kurallar(g):
    e = E("📜 Sunucu Kuralları",
          "**1.** Saygı temeldir — hakaret, trollük, ayrımcılık yok.\n"
          "**2.** Spam ve flood yasak.\n"
          "**3.** Reklam/davet linki paylaşmak yasak (partnerler hariç).\n"
          "**4.** NSFW içerik kesinlikle yasak.\n"
          "**5.** Yanıltıcı fiyat/ürün paylaşımı yapma.\n"
          "**6.** Affiliate linki yalnız `#fırsatlar`'da, kurallara uygun paylaş.\n"
          "**7.** Yetkililere saygılı ol; kararlar `#moderasyon`'da alınır.\n"
          "**8.** Kişisel veri paylaşma (kendi veya başkasının).\n"
          "**9.** Botu kötüye kullanma (komut spam'i).\n"
          "**10.** Kurallara uymayanlar uyarısız ceza alabilir.\n\n"
          "⚠️ Sunucuda kalmak = kuralları kabul etmek sayılır.")
    return [(e, None)]


def b_duyurular(g):
    e = E("📢 Duyurular",
          "Resmi duyurular bu kanalda paylaşılır.\n"
          "Yeni özellikler, bakım çalışmaları ve önemli güncellemeler için "
          "kanalı takipte kal.\n\n"
          "🔔 Duyu bildirimleri istersen rol paneline göz at.")
    return [(e, None)]


def b_trendcord(g):
    e = E("🛒 Trendcord Nedir?",
          "**Trendcord**, Trendyol ürünlerinin fiyatını 7/24 takip eden "
          "Discord botu ve platformudur.\n\n"
          "✅ Ürün fiyatı takibi\n"
          "✅ Fiyat düşüşünde anında bildirim\n"
          "✅ Fiyat alarmı (hedef fiyat)\n"
          "✅ Fiyat geçmişi grafiği\n"
          "✅ Web paneli: ürün/sunucu/kullanıcı istatistikleri\n"
          "✅ 7/24 bulut altyapısı\n\n"
          "🌐 " + WEB, url=WEB, image=True)
    v = link_view(("🌐 Web Paneli", WEB), ("➕ Botu Ekle", invite_url(os.getenv("CLIENT_ID", ""))))
    return [(e, v)]


def b_rehber(g):
    e = E("📖 Kullanım Rehberi",
          "**Ürün takibe alma:**\n"
          "└ `/ekle` → Trendyol ürün linkini yapıştır\n\n"
          "**Takip listesi:**\n"
          "└ `/takiptekiler` → sunucundaki takipler\n\n"
          "**Fiyat alarmı:**\n"
          "└ `/alarm <ürün-id> <hedef-fiyat> alt` → fiyat düşünce haber ver\n"
          "└ `/alarmlar` → alarmlarını gör · `/alarm-sil` → kaldır\n\n"
          "**Ürün karşılaştırma:**\n"
          "└ `/karşılaştır <id1> <id2>`\n\n"
          "**İstatistik:**\n"
          "└ `/istatistik` · `/sunucuistatistik`\n\n"
          "🌐 Detaylı panel: " + WEB + "/dashboard")
    v = link_view(("🌐 Dashboard", WEB + "/dashboard"), ("📊 Sunucular", WEB + "/servers"))
    return [(e, v)]


def b_sss(g):
    e = E("❓ Sık Sorulan Sorular",
          "Aşağıdaki butonlardan en çok sorulan soruların cevaplarını "
          "görebilirsin. Cevabın yoksa destek panelini kullan.")
    return [(e, "SSS")]


def b_durum(g):
    return [("DURUM", None)]  # status task yonetir


def b_rol_secimi(g):
    e = E("🎨 Rol Seçimi",
          "Aşağıdaki menüden **bildirim** ve **ilgi alanı** rollerini seç.\n"
          "Aynı menüden seçimi kaldırırsan rol bırakılır.\n\n"
          "🔔 Fiyat Bildirim — her fiyat düşüşü ping\n"
          "🏷️ İndirim Bildirim — büyük indirimler ping\n"
          "🎁 Kampanya Bildirim — kampanya duyuruları\n"
          "📰 Güncelleme Bildirim — sürüm notları")
    return [(e, "ROL")]


def b_komutlar(g):
    e = E("⌨️ Komut Alanı",
          "Bu kanalda **yalnızca slash komut** kullanılır.\n\n"
          "`/ekle` `/sil` `/takiptekiler` — ürün takibi\n"
          "`/alarm` `/alarmlar` `/alarm-sil` — fiyat alarmları\n"
          "`/karşılaştır` — iki ürünü kıyasla\n"
          "`/istatistik` `/sunucuistatistik` — istatistikler\n"
          "`/yardım` — tüm komutlar\n\n"
          "⚠️ Normal mesajlar bu kanalda yazılamaz.")
    v = link_view(("🌐 Web Paneli", WEB), ("➕ Botu Ekle", invite_url(os.getenv("CLIENT_ID", ""))))
    return [(e, v)]


def b_fiyat_dususleri(g):
    e = E("📉 Fiyat Düşüşleri",
          "Takip edilen ürünlerin fiyatı düştüğünde **otomatik bildirim** "
          "bu kanala düşer.\n\n"
          "🔔 Ping almak istersen rolünü seç: "
          f"{_c(g,'oh:rol-secimi','rol-seçimi')}\n"
          "🌐 Tüm ürünlerin fiyat geçmişi ve grafikleri web panelinde:")
    v = link_view(("🌐 Ürünler", WEB + "/dashboard"))
    return [(e, v)]


def b_urun_takip(g):
    e = E("📦 Ürün Takip",
          "Takip ettiğin ürünleri paylaş, fiyat yorumları yap, "
          "diğer takipçilerle tartış.\n\n"
          "➕ Yeni ürün: `/ekle` komutunu kullan\n"
          "🌐 Web panelinden detaylı takip:")
    v = link_view(("🌐 Web Paneli", WEB), ("📖 Rehber", WEB + "/how-it-works"))
    return [(e, v)]


def b_buyuk_indirimler(g):
    e = E("🔥 Büyük İndirimler",
          "**≥%30** ve üzeri indirimler otomatik olarak bu kanala düşer.\n"
          "🏷️ İndirim Bildirim rolü ile ping alabilirsin.\n"
          "🌐 Fırsatları web'den de izle:")
    v = link_view(("🌐 Web Paneli", WEB))
    return [(e, v)]


def b_firsatlar(g):
    e = E("💡 Fırsatlar",
          "Topluluğun bulduğu iyi fırsatları burada paylaş!\n"
          "**Format:** ürün linki + kısa açıklama + fiyat.\n"
          "⚠️ Yanıltıcı paylaşım ceza sebebidir.")
    v = link_view(("🌐 Web Paneli", WEB))
    return [(e, v)]


def b_kuponlar(g):
    e = E("🎟️ Kuponlar",
          "Kupon kodlarını burada paylaş.\n"
          "**Format:** `kod` — geçerlilik — kapsamı\n"
          "⚠️ Süresi bitmiş/yanıltıcı kupon paylaşma.")
    v = link_view(("🌐 Web Paneli", WEB))
    return [(e, v)]


def b_kampanyalar(g):
    e = E("🎁 Kampanyalar",
          "Resmi Trendyol ve Trendcord kampanyaları burada duyurulur. "
          "Takipte kal!")
    return [(e, None)]


def b_genel(g):
    e = E("💬 Genel Sohbet",
          "Serbest sohbet alanı. Saygı çerçevesinde her şey konuşulur — "
          "kurallar için #kurallar'a bak.")
    return [(e, None)]


def b_alisveris(g):
    e = E("🛍️ Alışveriş Sohbeti",
          "E-ticaret deneyimleri: kargo, iade, satıcı yorumları, "
          "Trendyol ipuçları…")
    return [(e, None)]


def b_teknoloji(g):
    e = E("🖥️ Teknoloji Sohbeti",
          "Donanım, telefon, yazılım ve teknoloji gündemi. "
          "Ürün tavsiyesi için #ürün-tavsiye forumunu kullan.")
    return [(e, None)]


def b_soru_cevap(g):
    e = E("❓ Soru-Cevap Forumu",
          "Sorunu **post olarak** aç, etiket seç. Çözülen sorular "
          "`çözüldü` olarak işaretlenir.\n\n"
          "**Tagler:** bot-kullanımı · fiyat-takip · hesap · diğer")
    return [(e, None)]


def b_urun_tavsiye(g):
    e = E("🛒 Ürün Tavsiye Forumu",
          "Ne alacağımı bilmiyorum diyenler buraya! Bütçeni ve ihtiyacını "
          "yaz, topluluk tavsiye versin.\n\n"
          "**Tagler:** telefon · bilgisayar · beyaz-eşya · kozmetik · diğer")
    return [(e, None)]


def b_bug(g):
    e = E("🐛 Bug Bildirimi",
          "Hata bulduysan **post aç** ve şu formu kullan:\n\n"
          "```\n🐛 SORUN: <tek cümle>\n"
          "KOMUT: <kullanılan komut>\n"
          "ÜRÜN URL: <link veya yok>\n"
          "HATA MESAJI: <hata / ekran görüntüsü>\n"
          "TEKRAR: 1)... 2)... 3)...\n"
          "TARİH: <ne zaman>\n```"
          "\nTagler: `açık → inceleniyor → çözüldü / bilinen-hata`")
    return [(e, None)]


def b_oneri(g):
    e = E("💡 Özellik Önerileri",
          "Yeni özellik fikrini **post** olarak paylaş, topluluk oylasın 👍\n\n"
          "Durum akışı: `değerlendiriliyor → planlandı → geliştiriliyor → "
          "tamamlandı` (veya `reddedildi` + gerekçe)")
    return [(e, None)]


def b_changelog(g):
    e = E("📰 Değişiklik Günlüğü",
          "Trendcord sürüm notları burada yayınlanır.\n"
          "📰 Güncelleme Bildirim rolü ile haberdar olabilirsin: "
          f"{_c(g,'oh:rol-secimi','rol-seçimi')}")
    return [(e, None)]


def b_destek_paneli(g):
    e = E("🎫 Destek",
          "Aşağıdaki menüden destek türünü seç — özel bir thread açalım, "
          "sadece sen ve destek ekibi görsün.\n\n"
          "**Türler:** Genel · Bot · Fiyat Takibi · Ürün Sorunu · Hesap · "
          "İş Birliği · Şikayet · Diğer")
    return [(e, "TICKET")]


def b_partner_duyuru(g):
    e = E("🤝 Partner Duyuruları",
          "Trendcord partner sunucu ve markaların resmi duyuruları.")
    return [(e, None)]


def b_partner_sohbet(g):
    e = E("🤝 Partner Sohbeti",
          "Partnerler arası koordinasyon alanı. İş birliği teklifleri için "
          "destek panelini kullan.")
    return [(e, None)]


def b_staff_sohbet(g):
    e = E("🛡️ Staff Sohbet",
          "Ekip içi koordinasyon. Kullanıcılar göremez.")
    return [(e, None)]


def b_staff_duyuru(g):
    e = E("📌 Staff Duyuruları",
          "Ekip duyuruları — yönetim tarafından yazılır.")
    return [(e, None)]


def b_moderasyon(g):
    e = E("🔨 Moderasyon",
          "Ceza kararları ve vaka tartışmaları. Tüm eylemler #mod-log'a düşer.")
    return [(e, None)]


def b_log_rehber(name, aciklama):
    def _b(g):
        e = E(f"📊 {name}", aciklama + "\nBu kanal bot tarafından yazılır; "
              "insan yazamaz. Mesaj silinmez.")
        return [(e, None)]
    return _b


def b_welcome_member(member):
    """Yeni uye karsilama (on_member_join)."""
    g = member.guild
    e = discord.Embed(
        title=f"👋 Hoş geldin {member.display_name}!",
        description=(
            f"{member.mention} • **{g.name}** ailesine katıldı!\n\n"
            f"📜 Kurallar: {_c(g,'oh:kurallar','kurallar')}\n"
            f"🎨 Roller: {_c(g,'oh:rol-secimi','rol-seçimi')}\n"
            f"📖 Rehber: {_c(g,'oh:kullanım-rehberi','kullanım-rehberi')}\n"
            f"🎫 Destek: {_c(g,'oh:destek-paneli','destek-paneli')}\n\n"
            f"🌐 {WEB}"),
        color=ORANGE)
    e.set_thumbnail(url=member.display_avatar.url)
    e.set_image(url=IMG)
    e.set_footer(text=f"Üye #{g.member_count}")
    return e


# ---------------- kayit defteri ----------------
# keys: once managed key, sonra kanal adi ile arama yapilir
# view: "ROL"|"TICKET"|"SSS" = dinamik panel; None = view'suz; dict = link view

CONTENT = [
    {"keys": ["oh:hosgeldin", "ch:hosgeldin", "hoş-geldin"], "build": b_hosgeldin},
    {"keys": ["oh:kurallar", "kurallar"], "build": b_kurallar, "official_only": True},
    {"keys": ["oh:duyurular", "ch:duyurular", "duyurular"], "build": b_duyurular},
    {"keys": ["oh:trendcord", "trendcord"], "build": b_trendcord, "official_only": True},
    {"keys": ["oh:kullanim-rehberi", "ch:kullanim-rehberi", "kullanım-rehberi"],
     "build": b_rehber},
    {"keys": ["oh:sss", "sss"], "build": b_sss, "official_only": True},
    {"keys": ["oh:rol-secimi", "rol-seçimi"], "build": b_rol_secimi},
    {"keys": ["oh:komutlar", "ch:komutlar", "komutlar"], "build": b_komutlar},
    {"keys": ["oh:fiyat-dususleri", "ch:fiyat-dususleri", "fiyat-düşüşleri"],
     "build": b_fiyat_dususleri},
    {"keys": ["oh:urun-takip", "ch:urun-takip", "ürün-takip"], "build": b_urun_takip},
    {"keys": ["oh:buyuk-indirimler", "ch:buyuk-indirimler", "büyük-indirimler"],
     "build": b_buyuk_indirimler},
    {"keys": ["oh:firsatlar", "ch:firsatlar", "fırsatlar"], "build": b_firsatlar},
    {"keys": ["oh:kuponlar", "ch:kuponlar", "kuponlar"], "build": b_kuponlar},
    {"keys": ["oh:kampanyalar", "kampanyalar"], "build": b_kampanyalar},
    {"keys": ["oh:genel", "genel"], "build": b_genel},
    {"keys": ["oh:alisveris-sohbet", "alışveriş-sohbet"], "build": b_alisveris},
    {"keys": ["oh:teknoloji-sohbet", "teknoloji-sohbet"], "build": b_teknoloji},
    {"keys": ["oh:soru-cevap", "soru-cevap"], "build": b_soru_cevap},
    {"keys": ["oh:urun-tavsiye", "ürün-tavsiye"], "build": b_urun_tavsiye},
    {"keys": ["oh:bug-bildirimi", "bug-bildirimi"], "build": b_bug},
    {"keys": ["oh:ozellik-onerileri", "özellik-önerileri"], "build": b_oneri},
    {"keys": ["oh:degisiklik-gunlugu", "değişiklik-günlüğü"], "build": b_changelog},
    {"keys": ["oh:destek-paneli", "ch:destek-paneli", "destek-paneli"],
     "build": b_destek_paneli},
    {"keys": ["oh:partner-duyurulari", "partner-duyuruları"],
     "build": b_partner_duyuru, "official_only": True},
    {"keys": ["oh:partner-sohbet", "partner-sohbet"],
     "build": b_partner_sohbet, "official_only": True},
    {"keys": ["oh:staff-sohbet", "staff-sohbet"], "build": b_staff_sohbet,
     "official_only": True},
    {"keys": ["oh:staff-duyurulari", "staff-duyuruları"], "build": b_staff_duyuru,
     "official_only": True},
    {"keys": ["oh:moderasyon", "moderasyon"], "build": b_moderasyon,
     "official_only": True},
    {"keys": ["oh:mod-log", "mod-log"], "build": b_log_rehber(
        "Mod Log", "Ceza ve otomod olayları."), "official_only": True},
    {"keys": ["oh:mesaj-log", "mesaj-log"], "build": b_log_rehber(
        "Mesaj Log", "Silinen/düzenlenen mesajlar."), "official_only": True},
    {"keys": ["oh:uye-log", "uye-log"], "build": b_log_rehber(
        "Üye Log", "Giriş/çıkış/nick/rol olayları."), "official_only": True},
    {"keys": ["oh:sunucu-log", "sunucu-log"], "build": b_log_rehber(
        "Sunucu Log", "Kanal/rol/emoji değişimleri."), "official_only": True},
    {"keys": ["oh:bot-log", "bot-log"], "build": b_log_rehber(
        "Bot Log", "Komut, ürün, alarm ve API olayları."), "official_only": True},
    {"keys": ["oh:sistem-log", "sistem-log"], "build": b_log_rehber(
        "Sistem Log", "Restart, bağlantı ve kritik hatalar."), "official_only": True},
    {"keys": ["oh:ticket-log", "ticket-log"], "build": b_log_rehber(
        "Ticket Log", "Ticket transcript kayıtları."), "official_only": True},
]


async def post_channel_content(guild, spec, db, force=False) -> bool:
    """Tek kanalin icerigini idempotent post eder. Donus: post edildi mi."""
    from provisioner.common.store import SetupStore
    store = SetupStore(db)
    ch = None
    for k in spec["keys"]:
        ent = store.entity(str(guild.id), k)
        if ent:
            ch = guild.get_channel(int(ent["discord_id"]))
            if ch:
                break
    if ch is None:
        for n in spec["keys"]:
            ch = discord.utils.find(lambda c: c.name == n, guild.text_channels)
            if ch:
                break
    if ch is None:
        return False

    msg_key = "msg:" + spec["keys"][0]
    if not force:
        ent = store.entity(str(guild.id), msg_key)
        if ent:
            try:
                m = await ch.fetch_message(int(ent["discord_id"]))
                if m:
                    return False  # zaten var
            except (discord.NotFound, discord.HTTPException):
                pass

    if isinstance(ch, discord.ForumChannel):
        return False  # forumlara intro mesaji post edilmez; tagler yeterli
    perms = ch.permissions_for(guild.me)
    if not (perms.send_messages and perms.embed_links):
        return False

    built = spec["build"](guild)
    last_msg = None
    for item in built:
        if item == ("DURUM", None):
            continue  # durum mesajini status task yonetir
        embed, view = item
        if view == "ROL":
            from provisioner.common.views import RolePanelView
            view = RolePanelView()
        elif view == "TICKET":
            from provisioner.common.views import TicketPanelView
            view = TicketPanelView()
        elif view == "SSS":
            from provisioner.common.views import SSSView
            view = SSSView()
        last_msg = await ch.send(embed=embed, view=view)

    if last_msg:
        store.mark(str(guild.id), msg_key, "MESSAGE", last_msg.id)
    return True


async def post_all_content(guild, db=None, official: bool = False) -> int:
    """Tum kanallarin icerigini post eder; sayi dondurur."""
    assert db is not None, "db gerekli"
    from provisioner.common.store import SetupStore
    store = SetupStore(db)
    n = 0
    for spec in CONTENT:
        if spec.get("official_only") and not official:
            continue
        try:
            if await post_channel_content(guild, spec, db):
                n += 1
        except Exception as e:
            logger.warning(f"[Content] {guild.id}/{spec['keys'][0]}: {e}")
    logger.info(f"[Content] {guild.id}: {n} kanal icerigi post edildi")
    return n


async def post_status_message(guild, db=None, bot=None) -> None:
    """#durum kanalina/edit: canli sistem durumu (tek mesaj)."""
    assert db is not None, "db gerekli"
    import time as _time
    from provisioner.common.store import SetupStore
    store = SetupStore(db)
    ch = None
    for k in ("oh:durum", "ch:durum", "durum"):
        ent = store.entity(str(guild.id), k)
        if ent:
            ch = guild.get_channel(int(ent["discord_id"]))
            if ch:
                break
    if ch is None:
        ch = discord.utils.find(lambda c: c.name == "durum", guild.text_channels)
    if ch is None:
        return

    web_ok = "🟢"
    try:
        import httpx
        async with httpx.AsyncClient(timeout=6.0) as cli:
            r = await cli.get(WEB)
            web_ok = "🟢" if r.status_code == 200 else "🟡"
    except Exception:
        web_ok = "🔴"

    uptime = "?"
    if hasattr(bot, "start_time"):
        s = int(_time.time() - bot.start_time)
        uptime = f"{s//86400}g {s%86400//3600}s {s%3600//60}dk"
    try:
        urun = len(bot.db.get_all_products(guild_id=str(guild.id)))
    except Exception:
        urun = 0

    e = discord.Embed(title="🟢 Sistem Durumu", color=0x4ADE80)
    e.add_field(name="🤖 Bot", value="🟢 Çalışıyor", inline=True)
    e.add_field(name="🌐 Web Panel", value=f"{web_ok} Online", inline=True)
    e.add_field(name="⚙️ Fiyat Motoru", value="🟢 Aktif", inline=True)
    e.add_field(name="💾 Veritabanı", value="🟢 Bağlı (SQLite/WAL)", inline=True)
    e.add_field(name="🔔 Bildirim Sistemi", value="🟢 Aktif", inline=True)
    e.add_field(name="⏱️ Uptime", value=uptime, inline=True)
    e.add_field(name=f"📦 Bu sunucuda takip", value=f"{urun} ürün", inline=False)
    e.description = f"Son güncelleme: <t:{int(_time.time())}:R>"
    e.set_footer(text="Bu mesaj bot tarafından otomatik güncellenir")
    e.set_thumbnail(url=IMG)

    msg_key = "msg:oh:durum"
    ent = store.entity(str(guild.id), msg_key)
    if ent:
        try:
            m = await ch.fetch_message(int(ent["discord_id"]))
            await m.edit(embed=e)
            return
        except (discord.NotFound, discord.HTTPException):
            pass
    perms = ch.permissions_for(guild.me)
    if perms.send_messages and perms.embed_links:
        m = await ch.send(embed=e)
        store.mark(str(guild.id), msg_key, "MESSAGE", m.id)
