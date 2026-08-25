"""Resmi ana sunucu blueprint veri seti (Bolum 3).

Yalnizca OFFICIAL_GUILD_ID eslesmesinde kullanilir (3.1 guard).
Rol sirasi = hiyerarşi (ustten alta). Renkler int hex.
"""
import discord

# --- 3.3 ROLLER (19 adet; bot rolu Discord yonetir, kod olusturmaz) ---
OFFICIAL_ROLES = [
    {"name": "👑 Founder", "color": 0xE11D48, "hoist": True,
     "permissions": ["administrator"], "mentionable": False},
    {"name": "⚜️ Co-Owner", "color": 0xF97316, "hoist": True,
     "permissions": ["manage_guild", "manage_channels", "manage_roles",
                     "manage_webhooks", "ban_members", "kick_members",
                     "moderate_members", "manage_messages", "view_audit_log",
                     "change_nickname"], "mentionable": False},
    {"name": "🛡️ Administrator", "color": 0x8B5CF6, "hoist": True,
     "permissions": ["manage_channels", "manage_roles", "manage_webhooks",
                     "ban_members", "kick_members", "moderate_members",
                     "manage_messages", "view_audit_log", "change_nickname",
                     "move_members", "mute_members", "mention_everyone"],
     "mentionable": False},
    {"name": "📣 Community Manager", "color": 0x06B6D4, "hoist": True,
     "permissions": ["manage_messages", "moderate_members", "view_audit_log",
                     "mention_everyone"], "mentionable": False},
    {"name": "💻 Developer", "color": 0x3B82F6, "hoist": True,
     "permissions": ["manage_messages"], "mentionable": False},
    {"name": "🚨 Moderator", "color": 0x22C55E, "hoist": True,
     "permissions": ["manage_messages", "moderate_members", "kick_members",
                     "ban_members", "view_audit_log", "move_members",
                     "mute_members", "change_nickname"], "mentionable": False},
    {"name": "🎧 Support Team", "color": 0x14B8A6, "hoist": True,
     "permissions": ["manage_messages"], "mentionable": False},
    {"name": "🤝 Partner", "color": 0xEC4899, "hoist": True,
     "permissions": [], "mentionable": False},
    {"name": "✅ Üye", "color": 0x99AAB5, "hoist": True,
     "permissions": ["view_channel", "send_messages", "embed_links",
                     "attach_files", "add_reactions", "read_message_history",
                     "use_application_commands", "create_public_threads",
                     "send_messages_in_threads"], "mentionable": False},
    {"name": "🔔 Fiyat Bildirim", "color": 0xF59E0B, "hoist": False,
     "permissions": [], "mentionable": True, "self_assign": True},
    {"name": "🏷️ İndirim Bildirim", "color": 0xEF4444, "hoist": False,
     "permissions": [], "mentionable": True, "self_assign": True},
    {"name": "🎁 Kampanya Bildirim", "color": 0xA855F7, "hoist": False,
     "permissions": [], "mentionable": True, "self_assign": True},
    {"name": "📰 Güncelleme Bildirim", "color": 0x0EA5E9, "hoist": False,
     "permissions": [], "mentionable": True, "self_assign": True},
    {"name": "💻 Teknoloji", "color": 0x64748B, "hoist": False,
     "permissions": [], "mentionable": True, "self_assign": True},
    {"name": "🖥️ Bilgisayar", "color": 0x334155, "hoist": False,
     "permissions": [], "mentionable": True, "self_assign": True},
    {"name": "📱 Telefon", "color": 0x475569, "hoist": False,
     "permissions": [], "mentionable": True, "self_assign": True},
    {"name": "🎮 Oyun", "color": 0x7C3AED, "hoist": False,
     "permissions": [], "mentionable": True, "self_assign": True},
    {"name": "⛔ Karantina", "color": 0x747F8D, "hoist": False,
     "permissions": [], "mentionable": False},
]

SELF_ASSIGNABLE = [r["name"] for r in OFFICIAL_ROLES if r.get("self_assign")]

STAFF_WRITE = ["👑 Founder", "⚜️ Co-Owner", "🛡️ Administrator"]
MOD_PLUS = ["👑 Founder", "⚜️ Co-Owner", "🛡️ Administrator", "📣 Community Manager",
            "🚨 Moderator"]
DEV_PLUS = ["👑 Founder", "⚜️ Co-Owner", "🛡️ Administrator", "💻 Developer"]
SUPPORT_PLUS = MOD_PLUS + ["🎧 Support Team"]

MEMBER = "✅ Üye"


def _ro_overwrites():
    """3.5 RO sablonu: @everyone V,W✗ | Üye V,W✗,Rxn✓ | Staff W✓."""
    return [
        ("@everyone", {"view_channel": True, "send_messages": False}),
        (MEMBER, {"view_channel": True, "send_messages": False, "add_reactions": True,
                  "read_message_history": True}),
        *[(n, {"send_messages": True, "view_channel": True}) for n in STAFF_WRITE],
        ("__BOT__", {"view_channel": True, "send_messages": True, "embed_links": True}),
    ]


def _feed_overwrites(ping_roles):
    """3.5 BOT_FEED: Üye V✓,W✗,Rxn✓; BOT yazar; Moderator Mmsg✓; ping rolü görür."""
    ow = [
        ("@everyone", {"view_channel": True, "send_messages": False}),
        (MEMBER, {"view_channel": True, "send_messages": False, "add_reactions": True,
                  "read_message_history": True}),
        ("__BOT__", {"view_channel": True, "send_messages": True, "embed_links": True,
                     "attach_files": True, "mention_everyone": False}),
        ("🚨 Moderator", {"manage_messages": True}),
        *[(n, {"view_channel": True}) for n in ping_roles],
    ]
    return ow


def _slash_overwrites():
    return [
        ("@everyone", {"view_channel": True, "send_messages": False,
                       "use_application_commands": True, "read_message_history": True}),
        (MEMBER, {"view_channel": True, "send_messages": False,
                  "use_application_commands": True, "read_message_history": True}),
        ("__BOT__", {"view_channel": True, "send_messages": True, "embed_links": True,
                     "use_application_commands": True, "manage_messages": True}),
    ]


def _open_overwrites(slowmode=None):
    return [
        ("__BOT__", {"send_messages": False, "view_channel": True}),
        ("🚨 Moderator", {"manage_messages": True}),
        *[(n, {"view_channel": True, "send_messages": True}) for n in STAFF_WRITE],
    ]


def _forum_overwrites():
    return [
        ("@everyone", {"view_channel": True, "send_messages": False}),
        (MEMBER, {"view_channel": True, "create_public_threads": True,
                  "send_messages_in_threads": True, "add_reactions": True,
                  "read_message_history": True}),
        ("__BOT__", {"view_channel": True, "send_messages": True, "manage_threads": True,
                     "embed_links": True}),
    ]


def _private_cat_overwrites():
    """STAFF/LOGS/TICKETS: @everyone DENY VIEW; Üye DENY VIEW; BOT full."""
    return [
        ("@everyone", {"view_channel": False}),
        (MEMBER, {"view_channel": False}),
        ("__BOT__", {"view_channel": True, "send_messages": True, "embed_links": True,
                     "manage_messages": True, "manage_channels": True}),
    ]


def _voice_overwrites():
    return [
        ("__BOT__", {"view_channel": True, "connect": True}),
        ("🚨 Moderator", {"move_members": True, "mute_members": True}),
    ]


def _view_for(names):
    return [(n, {"view_channel": True, "send_messages": True}) for n in names]


def _logs_overwrites():
    """3.4 KATEGORI 10 VIEW dagilimi; hepsi bot-yazılır."""
    base = _private_cat_overwrites()
    base += _view_for(MOD_PLUS) + [("🛡️ Administrator", {"view_channel": True})]
    return base


# --- 3.4 KATEGORI + KANALLAR ---
OFFICIAL_CATEGORIES = [
    {"key": "oc:baslangic", "name": "🏁 BAŞLANGIÇ",
     "overwrites": [
         ("@everyone", {"view_channel": True, "add_reactions": True}),
         ("__BOT__", {"view_channel": True, "send_messages": True, "embed_links": True,
                      "manage_channels": True}),
     ],
     "channels": [
         {"key": "oh:hosgeldin", "name": "hoş-geldin", "kind": "RO", "topic": "Karşılama + sunucu haritası"},
         {"key": "oh:kurallar", "name": "kurallar", "kind": "RO", "topic": "Kurallar — rules screening bağlı"},
         {"key": "oh:duyurular", "name": "duyurular", "kind": "RO", "news": True, "topic": "Resmi duyurular"},
         {"key": "oh:trendcord", "name": "trendcord", "kind": "RO", "topic": "Trendcord nedir + linkler"},
         {"key": "oh:kullanim-rehberi", "name": "kullanım-rehberi", "kind": "RO", "topic": "Bot kullanım rehberi"},
         {"key": "oh:sss", "name": "sss", "kind": "RO", "topic": "Sık sorulan sorular"},
         {"key": "oh:durum", "name": "durum", "kind": "RO", "topic": "Canlı sistem durumu (bot editler)"},
         {"key": "oh:rol-secimi", "name": "rol-seçimi", "kind": "RO_PANEL", "topic": "Bildirim + ilgi rol panelleri"},
     ]},
    {"key": "oc:fiyat-takibi", "name": "💹 FİYAT TAKİBİ",
     "overwrites": [
         ("@everyone", {"view_channel": False}),
         (MEMBER, {"view_channel": True}),
         ("__BOT__", {"view_channel": True, "send_messages": True, "embed_links": True}),
     ],
     "channels": [
         {"key": "oh:komutlar", "name": "komutlar", "kind": "SLASH_ONLY"},
         {"key": "oh:fiyat-dususleri", "name": "fiyat-düşüşleri", "kind": "BOT_FEED",
          "ping_roles": ["🔔 Fiyat Bildirim"]},
         {"key": "oh:urun-takip", "name": "ürün-takip", "kind": "OPEN"},
     ]},
    {"key": "oc:indirim", "name": "🔥 İNDİRİM",
     "overwrites": [
         ("@everyone", {"view_channel": False}),
         (MEMBER, {"view_channel": True}),
         ("__BOT__", {"view_channel": True, "send_messages": True, "embed_links": True}),
     ],
     "channels": [
         {"key": "oh:buyuk-indirimler", "name": "büyük-indirimler", "kind": "BOT_FEED",
          "ping_roles": ["🏷️ İndirim Bildirim"]},
         {"key": "oh:firsatlar", "name": "fırsatlar", "kind": "OPEN"},
         {"key": "oh:kuponlar", "name": "kuponlar", "kind": "OPEN"},
         {"key": "oh:kampanyalar", "name": "kampanyalar", "kind": "RO",
          "ping_roles": ["🎁 Kampanya Bildirim"]},
     ]},
    {"key": "oc:topluluk", "name": "💬 TOPLULUK",
     "overwrites": [("__BOT__", {"view_channel": True})],
     "channels": [
         {"key": "oh:genel", "name": "genel", "kind": "OPEN", "slowmode": 5},
         {"key": "oh:alisveris-sohbet", "name": "alışveriş-sohbet", "kind": "OPEN", "slowmode": 5},
         {"key": "oh:teknoloji-sohbet", "name": "teknoloji-sohbet", "kind": "OPEN", "slowmode": 5},
         {"key": "oh:soru-cevap", "name": "soru-cevap", "kind": "FORUM",
          "tags": ["bot-kullanımı", "fiyat-takip", "hesap", "diğer"]},
         {"key": "oh:urun-tavsiye", "name": "ürün-tavsiye", "kind": "FORUM",
          "tags": ["telefon", "bilgisayar", "beyaz-eşya", "kozmetik", "diğer"]},
         {"key": "oh:genel-ses", "name": "Genel Ses", "kind": "VOICE", "limit": 50},
         {"key": "oh:sohbet-odasi", "name": "Sohbet Odası", "kind": "VOICE", "limit": 8},
         {"key": "oh:afk", "name": "AFK", "kind": "VOICE", "afk": True},
     ]},
    {"key": "oc:geri-bildirim", "name": "🧭 GERİ BİLDİRİM",
     "overwrites": [("__BOT__", {"view_channel": True, "send_messages": True})],
     "channels": [
         {"key": "oh:bug-bildirimi", "name": "bug-bildirimi", "kind": "FORUM",
          "tags": ["açık", "inceleniyor", "çözüldü", "bilinen-hata"]},
         {"key": "oh:ozellik-onerileri", "name": "özellik-önerileri", "kind": "FORUM",
          "tags": ["değerlendiriliyor", "planlandı", "geliştiriliyor",
                   "tamamlandı", "reddedildi"]},
         {"key": "oh:degisiklik-gunlugu", "name": "değişiklik-günlüğü", "kind": "RO"},
     ]},
    {"key": "oc:destek", "name": "🎫 DESTEK",
     "overwrites": [
         ("@everyone", {"view_channel": True, "send_messages": False}),
         ("__BOT__", {"view_channel": True, "send_messages": True, "embed_links": True,
                      "manage_channels": True}),
     ],
     "channels": [
         {"key": "oh:destek-paneli", "name": "destek-paneli", "kind": "RO_PANEL",
          "topic": "Destek talebi aç"},
     ]},
    {"key": "oc:tickets", "name": "🎟️ TICKETS",
     "overwrites": _private_cat_overwrites(),
     "channels": []},
    {"key": "oc:partnerlik", "name": "🤝 PARTNERLİK",
     "overwrites": [
         ("@everyone", {"view_channel": False}),
         (MEMBER, {"view_channel": False}),
         ("🤝 Partner", {"view_channel": True}),
         ("__BOT__", {"view_channel": True, "send_messages": True}),
     ],
     "channels": [
         {"key": "oh:partner-duyurulari", "name": "partner-duyuruları", "kind": "RO"},
         {"key": "oh:partner-sohbet", "name": "partner-sohbet", "kind": "OPEN",
          "partner_only": True},
     ]},
    {"key": "oc:staff", "name": "🛡️ STAFF",
     "overwrites": _private_cat_overwrites() + _view_for(SUPPORT_PLUS),
     "channels": [
         {"key": "oh:staff-sohbet", "name": "staff-sohbet", "kind": "OPEN"},
         {"key": "oh:staff-duyurulari", "name": "staff-duyuruları", "kind": "RO"},
         {"key": "oh:moderasyon", "name": "moderasyon", "kind": "OPEN"},
         {"key": "oh:staff-odasi", "name": "Staff Odası", "kind": "VOICE", "limit": 10},
     ]},
    {"key": "oc:logs", "name": "📊 LOGS",
     "overwrites": _logs_overwrites(),
     "channels": [
         {"key": "oh:mod-log", "name": "mod-log", "kind": "BOT_FEED"},
         {"key": "oh:mesaj-log", "name": "mesaj-log", "kind": "BOT_FEED"},
         {"key": "oh:uye-log", "name": "uye-log", "kind": "BOT_FEED"},
         {"key": "oh:sunucu-log", "name": "sunucu-log", "kind": "BOT_FEED"},
         {"key": "oh:bot-log", "name": "bot-log", "kind": "BOT_FEED"},
         {"key": "oh:sistem-log", "name": "sistem-log", "kind": "BOT_FEED"},
         {"key": "oh:ticket-log", "name": "ticket-log", "kind": "BOT_FEED"},
     ]},
]

# --- 3.6 AUTOMOD ---
AUTOMOD_RULES = [
    {"name": "tc-spam-block", "trigger": "spam", "actions": ["block"],
     "reason": "Discord ML spam"},
    {"name": "tc-mass-mention", "trigger": "mention_spam", "mention_limit": 5,
     "actions": ["block"], "reason": "≥5 mention"},
    {"name": "tc-invite-block", "trigger": "keyword",
     "patterns": [r"discord\.gg/\w+", r"discord(?:app)?\.com/invite/\w+"],
     "actions": ["block"], "reason": "davet linki"},
    {"name": "tc-phishing", "trigger": "keyword",
     "patterns": ["free nitro", "free-nitro", "seed phrase", "kurtarma ifadesi",
                  "stealer link"],
     "actions": ["block"], "reason": "phishing"},
]

# --- 3.7 MANUEL ADIMLAR ---
MANUAL_STEPS = [
    "Community özelliğini etkinleştir",
    "Rules Screening'i #kurallar'a bağla",
    "Onboarding formu: ilgi alanları + bildirim tercihleri (✅ Üye otomatik)",
    "Sunucu ayarlarından AFK kanalı = #AFK (5 dk)",
    "Verification Level: Medium | 2FA moderation: ON",
    "#duyurular Follow linkini partnerlere paylaş",
    "Server Template snapshot al (yedek katmanı)",
    "#trendcord içeriğine site/bot davet linklerini ekle",
]

KIND_TO_OVERWRITES = {
    "RO": _ro_overwrites,
    "RO_PANEL": _ro_overwrites,
    "SLASH_ONLY": _slash_overwrites,
    "BOT_FEED": _feed_overwrites,
    "OPEN": _open_overwrites,
    "FORUM": _forum_overwrites,
    "VOICE": _voice_overwrites,
}
