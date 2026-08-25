"""Resmi ana sunucu provisioner runner (Modul A).

GUARD (3.1): Tum giris noktalarinda OFFICIAL_GUILD_ID eslesmesi zorunlu.
Env tanimli degilse modul devre disi (G3) — bypass yolu yok.
"""
import logging
import os

import discord

from provisioner.common.ratelimit import safe_call, StepResult
from provisioner.official import data as odata

logger = logging.getLogger("Trendcord")

MEMBER_NAME = "✅ Üye"


def official_guild_id() -> str:
    return os.getenv("OFFICIAL_GUILD_ID", "").strip()


def is_official(guild_id) -> bool:
    gid = official_guild_id()
    return bool(gid) and str(guild_id) == gid


def module_enabled() -> bool:
    return bool(official_guild_id())


def _resolve_permissions(names) -> discord.Permissions:
    p = discord.Permissions.none()
    for n in names or []:
        setattr(p, n, True)
    return p


async def _ensure_role(guild, spec, current_by_name: dict):
    """Idempotent rol: varsa SKIP, yoksa olustur (yalniz resmi sunucu)."""
    name = spec["name"]
    existing = current_by_name.get(name)
    if existing:
        return StepResult(f"role:{name}", StepResult.SKIPPED, existing)
    async def factory():
        return await guild.create_role(
            name=name,
            colour=discord.Colour(spec["color"]),
            hoist=spec["hoist"],
            permissions=_resolve_permissions(spec["permissions"]),
            mentionable=spec["mentionable"],
            reason="Trendcord official provisioning")
    return await safe_call(f"role:{name}", factory)


async def ensure_official_roles(guild) -> list:
    """Rolleri hiyerarsi sirasinda olustur; pozisyonlari ustten alta ayarlar."""
    results = []
    by_name = {r.name: r for r in guild.roles}
    created_roles = []
    for spec in odata.OFFICIAL_ROLES:
        res = await _ensure_role(guild, spec, by_name)
        results.append(res)
        if res.status in (StepResult.CREATED, StepResult.SKIPPED):
            created_roles.append(res.entity)
    # pozisyon: listedeki sira = yukaridan asagi; en ustteki en buyuk pozisyona
    try:
        top = max((r.position for r in guild.roles
                   if r != guild.default_role and not r.managed), default=1)
        for i, role in enumerate(created_roles):
            await role.edit(position=top - i)
    except Exception as e:
        logger.warning(f"[Official] rol pozisyonlama atlandi: {e}")
    return results


def _build_overwrite_map(guild, spec, bot_member):
    """Spec'teki (rol_adi, {perm: bool}) listesini discord overwrite map'ine cevirir."""
    ow = {}
    for target_name, perms in spec.get("overwrites", []):
        if target_name == "__BOT__":
            po = discord.PermissionOverwrite(**perms)
            ow[bot_member] = po
            continue
        if target_name == "@everyone":
            target = guild.default_role
        else:
            target = discord.utils.find(lambda r: r.name == target_name, guild.roles)
        if target is None:
            logger.warning(f"[Official] rol bulunamadi: {target_name} (SKIPPED_REF)")
            continue
        ow[target] = discord.PermissionOverwrite(**perms)
    return ow


async def _ensure_channel(guild, ch, parent, overwrite_map):
    key = ch["key"]

    async def factory():
        kwargs = {"name": ch["name"], "overwrites": overwrite_map}
        if ch.get("topic"):
            kwargs["topic"] = ch["topic"]
        if ch.get("kind") == "VOICE":
            kwargs.pop("topic", None)
            if ch.get("limit"):
                kwargs["user_limit"] = ch["limit"]
            return await guild.create_voice_channel(**kwargs)
        if ch.get("kind") == "FORUM":
            return await guild.create_forum(**kwargs)
        if ch.get("news"):
            try:
                kwargs["type"] = discord.ChannelType.news
                return await guild.create_text_channel(**kwargs)
            except Exception:
                kwargs.pop("type", None)
                return await guild.create_text_channel(**kwargs)
        return await guild.create_text_channel(**kwargs)

    res = await safe_call(key, factory)
    if res.status == StepResult.CREATED:
        try:
            if parent is not None:
                await res.entity.edit(category=parent)
            if ch.get("slowmode"):
                await res.entity.edit(slowmode_delay=ch["slowmode"])
            if ch.get("kind") == "FORUM" and ch.get("tags"):
                for tag in ch["tags"]:
                    try:
                        await res.entity.create_tag(name=tag)
                    except Exception:
                        pass
        except Exception:
            pass
    return res


async def _apply_automod(guild):
    """3.6 automod kurallari — idempotent (ayni isim varsa gec)."""
    applied = []
    existing = {r.name for r in getattr(guild, "automod_rules", [])}
    try:
        existing = {r.name async for r in guild.fetch_automod_rules()}
    except Exception as e:
        logger.warning(f"[Official] automod kurallari okunamadi: {e}")
        return applied

    for spec in odata.AUTOMOD_RULES:
        if spec["name"] in existing:
            continue
        try:
            if spec["trigger"] == "spam":
                trigger = discord.AutoModTrigger(type=discord.AutoModTriggerType.spam)
            elif spec["trigger"] == "mention_spam":
                trigger = discord.AutoModTrigger(
                    type=discord.AutoModTriggerType.mention_spam,
                    mention_total_limit=spec.get("mention_limit", 5))
            else:
                trigger = discord.AutoModTrigger(
                    type=discord.AutoModTriggerType.keyword,
                    regex_patterns=spec.get("patterns") if spec["name"] == "tc-invite-block" else None,
                    keyword_filter=spec.get("patterns") if spec["name"] != "tc-invite-block" else None)
            await guild.create_automod_rule(
                name=spec["name"],
                event=discord.AutoModRuleActionType.block_message,
                trigger=trigger,
                actions=[discord.AutoModRuleAction(block_message=True)],
                enabled=True,
                reason=spec.get("reason", "Trendcord automod"),
            )
            applied.append(spec["name"])
        except Exception as e:
            logger.warning(f"[Official] automod {spec['name']}: {e}")
    return applied


async def apply_official(guild, db=None) -> dict:
    """apply: eksikleri idempotent kurar; rapor dondurur."""
    from provisioner.common.store import SetupStore
    assert db is not None, 'db gerekli'
    store = SetupStore(db)

    report = {"created": [], "skipped": [], "errors": [], "automod": [],
              "manual": odata.MANUAL_STEPS}

    role_results = await ensure_official_roles(guild)
    for r in role_results:
        if r.status == StepResult.CREATED:
            report["created"].append(f"🏷️ {r.entity.name}")
        elif r.status == StepResult.SKIPPED:
            report["skipped"].append(f"🏷️ {r.entity.name}")
        else:
            report["errors"].append(f"{r.key}: {r.status}")

    me = guild.me
    for cat in odata.OFFICIAL_CATEGORIES:
        ent = store.entity(guild.id, cat["key"])
        parent = guild.get_channel(int(ent["discord_id"])) if ent else None
        if parent is None:
            owmap = _build_overwrite_map(guild, cat, me)
            res = await safe_call(cat["key"], lambda c=cat, o=owmap:
                                  guild.create_category(c["name"], overwrites=o))
            if res.status == StepResult.CREATED:
                store.mark(guild.id, cat["key"], "CATEGORY", res.entity.id)
                parent = res.entity
                report["created"].append(f"📂 {res.entity.name}")
            else:
                report["errors"].append(f"{cat['key']}: {res.status}")
                continue
        else:
            report["skipped"].append(f"📂 {parent.name}")

        for ch in cat.get("channels", []):
            cent = store.entity(guild.id, ch["key"])
            if cent and guild.get_channel(int(cent["discord_id"])):
                report["skipped"].append(f"#{ch['name']}")
                continue
            spec = dict(ch)
            # Gizli kategorilerde kanal-bazli @everyone/Üye ALLOW'lar
            # kategori DENY'ini ezer -> filtrele (gizlilik sizmasin)
            def _cat_view(target):
                for t, perms in cat.get("overwrites", []):
                    if t == target and perms.get("view_channel") is False:
                        return True
                return False
            strip_everyone = _cat_view("@everyone")
            strip_member = _cat_view(MEMBER_NAME)

            if ch["kind"] == "BOT_FEED" and ch.get("ping_roles"):
                # ping rollerine VIEW ekle
                extra = [("__BOT__", {"view_channel": True, "send_messages": True,
                                      "embed_links": True, "attach_files": True,
                                      "mention_everyone": False}),
                         ("@everyone", {"view_channel": True, "send_messages": False}),
                         ("✅ Üye", {"view_channel": True, "send_messages": False,
                                     "add_reactions": True, "read_message_history": True}),
                         ("🚨 Moderator", {"manage_messages": True})]
                for pr in ch["ping_roles"]:
                    extra.append((pr, {"view_channel": True}))
                spec["overwrites"] = extra
            elif ch["kind"] in odata.KIND_TO_OVERWRITES:
                spec["overwrites"] = odata.KIND_TO_OVERWRITES[ch["kind"]]()
            if strip_everyone or strip_member:
                temiz = []
                for t, perms in spec.get("overwrites", []):
                    if t == "@everyone" and strip_everyone:
                        continue
                    if t == MEMBER_NAME and strip_member:
                        continue
                    temiz.append((t, perms))
                spec["overwrites"] = temiz
            owmap = _build_overwrite_map(guild, spec, me)
            cres = await _ensure_channel(guild, spec, parent, owmap)
            if cres.status == StepResult.CREATED:
                store.mark(guild.id, ch["key"], "CHANNEL", cres.entity.id)
                report["created"].append(f"# {cres.entity.name}")
            elif cres.status == StepResult.SKIPPED_PERM or cres.status == StepResult.FAILED:
                report["errors"].append(f"{ch['key']}: {cres.status}")

    report["automod"] = await _apply_automod(guild)
    store.save_state(guild.id, "OFFICIAL", "RAN" if not report["errors"] else "PARTIAL")

    # kanal icerikleri (embed/panel) — idempotent
    try:
        from provisioner.common.content import post_all_content
        report["content"] = await post_all_content(guild, db, official=True)
    except Exception as e:
        logger.warning(f"[Official] icerik postlama: {e}")
    return report


async def reset_official(guild, db=None) -> dict:
    """Resmi sunucuyu TAMAMEN SIFIRLA + yeniden kur.

    1) TUM kanallar silinir (managed + eski manuel — tam temizlik)
    2) TUM yonetilebilir roller silinir (@everyone + managed bot rolleri haric)
    3) apply_official ile blueprint sifirdan kurulur
    """
    from provisioner.common.store import SetupStore
    from provisioner.common.ratelimit import safe_call, StepResult
    assert db is not None, 'db gerekli'
    store = SetupStore(db)
    deleted = {"channels": 0, "roles": 0, "errors": []}

    me = guild.me

    # ---- 1) TUM KANALLAR (once kanallar, sonra kategoriler) ----
    normal = [c for c in guild.channels
              if not isinstance(c, discord.CategoryChannel)]
    cats = [c for c in guild.channels if isinstance(c, discord.CategoryChannel)]
    for ch in normal + cats:
        async def factory(ch=ch):
            return await ch.delete(reason="Trendcord reset: tam sifirlama")
        res = await safe_call(f"purge:{ch.name}", factory)
        if res.status == StepResult.CREATED:
            deleted["channels"] += 1
        else:
            deleted["errors"].append(f"kanal {ch.name}: {res.status}")

    # managed kayitlarini da temizle
    for ent in store.entities(guild.id, active_only=False):
        store.mark_deleted(guild.id, ent["key"])

    # ---- 2) TUM YONETILEBILIR ROLLER ----
    for role in list(guild.roles):
        if role == guild.default_role or role.managed:
            continue  # @everyone + baska botlarin rolleri dokunulmaz
        if me and role >= me.top_role:
            continue
        async def factory(role=role):
            return await role.delete(reason="Trendcord reset: tam sifirlama")
        res = await safe_call(f"role:{role.name}", factory)
        if res.status == StepResult.CREATED:
            deleted["roles"] += 1
        else:
            deleted["errors"].append(f"rol {role.name}: {res.status}")

    # ---- 3) SIFIRDAN KUR ----
    report = await apply_official(guild, db=db)
    report["reset"] = deleted
    return report


async def verify_official(guild, db=None) -> dict:
    """verify/diff: hicbir sey degistirmeden eksikleri raporlar (3.2)."""
    from provisioner.common.store import SetupStore
    assert db is not None, 'db gerekli'
    store = SetupStore(db)
    missing_roles = [r["name"] for r in odata.OFFICIAL_ROLES
                     if not discord.utils.find(lambda x: x.name == r["name"], guild.roles)]
    missing_channels = []
    for cat in odata.OFFICIAL_CATEGORIES:
        cent = store.entity(guild.id, cat["key"])
        if not cent or not guild.get_channel(int(cent["discord_id"])):
            missing_channels.append(f"📂 {cat['name']}")
            continue
        for ch in cat.get("channels", []):
            ent = store.entity(guild.id, ch["key"])
            if not ent or not guild.get_channel(int(ent["discord_id"])):
                missing_channels.append(f"# {ch['name']}")
    return {"missing_roles": missing_roles, "missing_channels": missing_channels,
            "manual": odata.MANUAL_STEPS}
