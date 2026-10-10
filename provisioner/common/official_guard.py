"""Resmi sunucu guard'i (OFFICIAL_GUILD_ID tek kaynagi).

Destek talebi (ticket) ozelligi YALNIZCA resmi sunucuda calisir; diger
sunucularda bot kurulu olsa bile panel acilmaz ve komut reddedilir.
"""
import os

OFFICIAL_NAME = "Trendcord Resmi Sunucusu"


def official_guild_id() -> str:
    return os.getenv("OFFICIAL_GUILD_ID", "").strip()


def is_official(guild_id) -> bool:
    gid = official_guild_id()
    return bool(gid) and str(guild_id) == gid


def invite_url() -> str:
    from provisioner.common.content import invite_url as _invite
    return _invite(os.getenv("CLIENT_ID", ""))


def deny_message() -> str:
    return (f"🎫 Destek talepleri yalnızca **{OFFICIAL_NAME}** sunucusunda "
            f"açılabilir.\n"
            f"Sorununu oradan ilet — ekibimiz orada sana dönüş yapar.")