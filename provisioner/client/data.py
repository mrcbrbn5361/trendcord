"""Client guild varsayilan kanal seti (4.5). Rol YOK — sadece kategori/kanal."""
import discord

# Kanal spec alanlari:
#   key, name, kind (RO|SLASH_ONLY|BOT_FEED|OPEN|PANEL), topic,
#   news (True -> NEWS denenir, hata olursa TEXT fallback),
#   forum_tags (FORUM tagleri), slowmode (saniye)

CATEGORIES = [
    {
        "key": "cat:trendcord",
        "name": "📊 TRENDCORD",
        "channels": [
            {"key": "ch:duyurular", "name": "duyurular", "kind": "RO",
             "topic": "Trendcord duyuruları", "news": True},
            {"key": "ch:durum", "name": "durum", "kind": "RO",
             "topic": "Bot/sistem durumu"},
            {"key": "ch:destek-paneli", "name": "destek-paneli", "kind": "PANEL",
             "topic": "Destek talebi aç"},
        ],
    },
    {
        "key": "cat:fiyat-takibi",
        "name": "💹 FİYAT TAKİBİ",
        "channels": [
            {"key": "ch:komutlar", "name": "komutlar", "kind": "SLASH_ONLY",
             "topic": "Slash komut alanı"},
            {"key": "ch:fiyat-dususleri", "name": "fiyat-düşüşleri", "kind": "BOT_FEED",
             "topic": "Otomatik fiyat düşüş akışı"},
            {"key": "ch:urun-takip", "name": "ürün-takip", "kind": "OPEN",
             "topic": "Ürün paylaş ve tartış"},
        ],
    },
]

OPTIONAL_MODULES = {
    "big_deals": {
        "key": "cat:indirim",
        "name": "🔥 İNDİRİM",
        "channels": [
            {"key": "ch:buyuk-indirimler", "name": "büyük-indirimler", "kind": "BOT_FEED",
             "topic": "≥%30 global fırsatlar"},
        ],
    },
    "coupons": {
        "key": "ch:kuponlar", "flat": True,
        "name": "kuponlar", "kind": "OPEN", "topic": "Kupon paylaşımları",
        "parent_key": "cat:fiyat-takibi",
    },
    "community_deals": {
        "key": "ch:firsatlar", "flat": True,
        "name": "fırsatlar", "kind": "OPEN", "topic": "Topluluk fırsatları",
        "parent_key": "cat:fiyat-takibi",
    },
}

# Bot daveti onerilen izinler (G2) — hesaplanmis deger:
# view_channel, send_messages, embed_links, attach_files, add_reactions,
# use_external_emojis, read_message_history, use_application_commands,
# manage_messages, manage_channels, create_public_threads, send_messages_in_threads
RECOMMENDED_PERMISSIONS = 311385517136


def channel_set(modules: dict):
    """Aktif modullere gore duzlestirilmis kategori/kanal listesi dondurur.

    Cikti: [ {key, name, channels: [...]}, {flat channel spec...} ]
    """
    out = [dict(c) for c in CATEGORIES]
    for mod_name, spec in OPTIONAL_MODULES.items():
        if modules.get(mod_name):
            out.append(dict(spec))
    return out
