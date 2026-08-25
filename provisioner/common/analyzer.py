"""Rol analiz motoru (Modul B / 4.3).

CLIENT guildlerde ASLA rol olusturmaz/silmez/duzenlemez (G1) — yalnizca okur.
"""
import re
import logging
from datetime import datetime, timezone

logger = logging.getLogger("Trendcord")

SUPPORT_HINT_RE = re.compile(r"(destek|support|yetkili|staff|mod|admin|yönetim|yonetim)", re.I)


def analyze_roles(guild) -> dict:
    """Sunucudaki MEVCUT rolleri izinlerine gore siniflandirir (4.3).

    Cikti JSON'a serilenebilir sozluk; roller position'a gore azalan sirali.
    """
    admin_roles, mod_roles, support_hint = [], [], []

    candidates = [
        r for r in guild.roles
        if r != guild.default_role and not r.managed
    ]

    for role in sorted(candidates, key=lambda r: r.position, reverse=True):
        perms = role.permissions
        entry = {"id": role.id, "name": role.name, "position": role.position}
        if perms.administrator:
            admin_roles.append(entry)
        elif (perms.manage_messages or perms.ban_members or perms.kick_members
              or perms.moderate_members or perms.manage_guild):
            mod_roles.append(entry)
        elif SUPPORT_HINT_RE.search(role.name):
            support_hint.append(entry)

    # SUPPORT_HINT: mod rolu hic yoksa ve MANAGE_MESSAGES yetkisi varsa moda yukselt (4.3 ADIM 2)
    if not mod_roles:
        promoted = []
        for entry in support_hint:
            role = guild.get_role(entry["id"])
            if role and role.permissions.manage_messages:
                mod_roles.append(entry)
                promoted.append(entry["name"])
        if promoted:
            logger.info(f"[Analyzer] {guild.id}: destek rolleri moda yukseltildi: {promoted}")

    me_perms = guild.me.guild_permissions if guild.me else guild.default_role.permissions
    return {
        "admin_roles": admin_roles,
        "mod_roles": mod_roles,
        "support_hint": [e for e in support_hint if e not in mod_roles],
        "has_admin_role": bool(admin_roles),
        "bot_permissions": {
            "view_channel": me_perms.view_channel,
            "manage_channels": me_perms.manage_channels,
            "manage_messages": me_perms.manage_messages,
            "administrator": me_perms.administrator,
        },
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


def resolve_role_lists(guild, analysis: dict):
    """Analiz sozlugunu discord.Role listelerine cevirir (silinmis roller elenir)."""
    def fetch(lst):
        out = []
        for e in lst or []:
            r = guild.get_role(e["id"])
            if r:
                out.append(r)
        return out
    return fetch(analysis.get("admin_roles")), fetch(analysis.get("mod_roles")), \
        fetch(analysis.get("support_hint"))
