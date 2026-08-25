"""PermissionOverwrite uretim yardimcilari.

Modul B (client) Tablo A'ya, Modul A (official) 3.5 sablonlarina birebir uyar.
Hicbir fonksiyon rol olusturmaz/duzenlemez; yalnizca overwrite nesnesi uretir.
"""
import discord

# Botun kendisine her kanalda acilacak izinler (4.4)
BOT_ALLOW = [
    "view_channel", "send_messages", "embed_links", "attach_files",
    "read_message_history", "add_reactions", "use_application_commands",
]

ADMIN_ALLOW = ["view_channel", "send_messages", "embed_links", "manage_messages"]
MOD_ALLOW = ["view_channel", "send_messages", "manage_messages"]
SUPPORT_ALLOW = ["view_channel", "send_messages"]


def bot_overwrite() -> discord.PermissionOverwrite:
    po = discord.PermissionOverwrite()
    for p in BOT_ALLOW:
        setattr(po, p, True)
    return po


def everyone_base(kind: str):
    """Tablo A — @everyone baz overwrite. OPEN icin None (dokunma ilkesi)."""
    po = discord.PermissionOverwrite()
    if kind == "RO":
        po.view_channel = True
        po.add_reactions = True
        po.send_messages = False
    elif kind == "SLASH_ONLY":
        po.view_channel = True
        po.use_application_commands = True
        po.add_reactions = True
        po.read_message_history = True
        po.send_messages = False
    elif kind == "BOT_FEED":
        po.view_channel = True
        po.add_reactions = True
        po.send_messages = False
        po.embed_links = False
    elif kind == "PANEL":
        po.view_channel = True
        po.send_messages = False
    elif kind == "OPEN":
        return None
    else:
        return None
    return po


def build_overwrites(kind: str, me: discord.Member, admin_roles, mod_roles,
                     support_roles, everyone: bool = True) -> dict:
    """Bir kanal spec'i icin overwrite sozlugu uretir.

    kind        : RO | SLASH_ONLY | BOT_FEED | OPEN | PANEL | VOICE | FORUM | PRIVATE
    everyone    : False ise @everyone baz overwrite yazilmaz (OPEN dokunma ilkesi)
    admin_roles/mod_roles/support_roles : discord.Role listeleri
    """
    ow: dict = {}

    def target(t):
        if t not in ow:
            ow[t] = discord.PermissionOverwrite()
        return ow[t]

    # 1) Bot kendisi
    bot_po = target(me)
    for p in BOT_ALLOW:
        setattr(bot_po, p, True)

    # 2) @everyone baz (tablo A)
    if everyone:
        base = everyone_base(kind)
        if base is not None:
            ow[me.guild.default_role] = base

    # 3) Yetkili roller (her kanal)
    for r in admin_roles:
        po = target(r)
        for p in ADMIN_ALLOW:
            setattr(po, p, True)
    for r in mod_roles:
        po = target(r)
        for p in MOD_ALLOW:
            setattr(po, p, True)

    # 4) Destek ipucu rolleri yalniz RO + PANEL kanallarda
    if kind in ("RO", "PANEL"):
        for r in support_roles:
            po = target(r)
            for p in SUPPORT_ALLOW:
                setattr(po, p, True)

    return ow
