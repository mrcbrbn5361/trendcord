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


async def ensure_official_roles(guild, report=None) -> list:
    """Rolleri olustur VEYA var olanlari izin/renk/hoist acisindan esitle."""
    results = []
    by_name = {r.name: r for r in guild.roles}
    for spec in odata.OFFICIAL_ROLES:
        role = by_name.get(spec["name"])
        if role is None:
            res = await _ensure_role(guild, spec, by_name)
            results.append(res)
            if res.status == StepResult.CREATED and report is not None:
                report["created"].append(f"🏷️ {spec['name']}")
            continue
        # SENKRON: izin/renk/hoist/mentionable
        exp = _resolve_permissions(spec["permissions"])
        if (role.permissions.value != exp.value
                or role.color.value != spec["color"]
                or role.hoist != spec["hoist"]
                or role.mentionable != spec["mentionable"]):
            try:
                await role.edit(
                    colour=discord.Colour(spec["color"]),
                    hoist=spec["hoist"],
                    permissions=exp,
                    mentionable=spec["mentionable"],
                    reason="Trendcord: rol senkronu")
                if report is not None:
                    report["synced"].append(f"🏷️ {spec['name']} izinleri")
            except discord.Forbidden:
                if report is not None:
                    report["errors"].append(f"rol {spec['name']}: 50013")
        results.append(StepResult(f"role:{spec['name']}", StepResult.SKIPPED, role))
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
                event=discord.AutoModRuleEventType.message_send,
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
    """apply/SENKRON: eksikleri kur, VAR OLANLARIN IZINLERINI EŞITLE.

    - Roller: izin/renk/hoist/mentionable esitlenir + hiyerarsi duzenlenir
    - Kategori/kanallar: overwrite'lar yeniden uygulanir
    - @everyone baz izinleri sikilastirilir
    - Karantina rolune public kategorilerde yazma/voice engeli verilir
    """
    from provisioner.common.store import SetupStore
    store = SetupStore(db)
    report = {"created": [], "synced": [], "skipped": [], "errors": [],
              "automod": [], "manual": odata.MANUAL_STEPS, "content": 0}

    me = guild.me

    # ---- 0) @everyone baz izinleri (guvenli minimum) ----
    safe = discord.Permissions.none()
    for p in ("view_channel", "send_messages", "embed_links", "attach_files",
              "add_reactions", "read_message_history", "use_application_commands",
              "use_external_emojis", "create_public_threads",
              "send_messages_in_threads", "connect", "speak",
              "send_voice_messages"):
        setattr(safe, p, True)
    if guild.default_role.permissions.value != safe.value:
        try:
            await guild.default_role.edit(permissions=safe,
                                          reason="Trendcord: @everyone sikilastirma")
            report["synced"].append("🔒 @everyone baz izinleri")
        except discord.Forbidden:
            report["errors"].append("@everyone edit: izin yok")

    # ---- 1) ROLLER: olustur VEYA senkronize et ----
    role_results = await ensure_official_roles(guild, report)
    blueprint_roles = []
    for spec in odata.OFFICIAL_ROLES:
        role = discord.utils.find(lambda r: r.name == spec["name"], guild.roles)
        if role:
            blueprint_roles.append(role)

    # hiyerarsi: bot rolunun hemen altina yerlestir
    try:
        if me:
            top = me.top_role.position - 1
            for i, role in enumerate(blueprint_roles):
                if role.position != top - i:
                    await role.edit(position=top - i)
            report["synced"].append("📊 Rol hiyerarsisi")
    except Exception as e:
        logger.debug(f"[Official] pozisyonlama: {e}")

    # ---- 2) KATEGORILER + KANALLAR ----
    for cat in odata.OFFICIAL_CATEGORIES:
        ent = store.entity(guild.id, cat["key"])
        parent = guild.get_channel(int(ent["discord_id"])) if ent else None
        cat_ow = list(cat.get("overwrites", []))
        if not cat.get("private"):
            # Karantina: public kategorilerde yazma/threads/voice engeli
            cat_ow.append(("⛔ Karantina",
                           {"send_messages": False, "connect": False,
                            "create_public_threads": False, "add_reactions": False}))
        cat_map = _build_overwrite_map(guild, {"overwrites": cat_ow}, me)

        if parent is None:
            res = await safe_call(cat["key"], lambda c=cat, o=cat_map:
                                  guild.create_category(c["name"], overwrites=o))
            if res.status == StepResult.CREATED:
                store.mark(guild.id, cat["key"], "CATEGORY", res.entity.id)
                parent = res.entity
                report["created"].append(f"📂 {res.entity.name}")
            else:
                report["errors"].append(f"{cat['key']}: {res.status}")
                continue
        else:
            try:
                if _ow_farkli(parent.overwrites, cat_map):
                    await parent.edit(overwrites=cat_map,
                                      reason="Trendcord: izin senkronu")
                    report["synced"].append(f"📂 {parent.name} izinleri")
            except discord.Forbidden:
                report["errors"].append(f"{cat['key']} izin: 50013")
            report["skipped"].append(f"📂 {parent.name}")

        for ch in cat.get("channels", []):
            cent = store.entity(guild.id, ch["key"])
            existing = guild.get_channel(int(cent["discord_id"])) if cent else None
            if existing is not None:
                # izin + ozellik SENKRONU
                spec = dict(ch)
                if ch["kind"] == "BOT_FEED" and ch.get("ping_roles"):
                    extra = _feed_overwrites(ch["ping_roles"])
                    spec["overwrites"] = extra
                elif ch["kind"] in odata.KIND_TO_OVERWRITES:
                    spec["overwrites"] = odata.KIND_TO_OVERWRITES[ch["kind"]]()
                spec = _strip_private(spec, cat)
                owmap = _build_overwrite_map(guild, spec, me)
                try:
                    degisti = False
                    if _ow_farkli(existing.overwrites, owmap):
                        await existing.edit(overwrites=owmap,
                                            reason="Trendcord: izin senkronu")
                        degisti = True
                    if getattr(existing, "topic", None) != ch.get("topic") and ch.get("topic"):
                        await existing.edit(topic=ch["topic"])
                        degisti = True
                    if ch.get("slowmode") and getattr(existing, "slowmode_delay", 0) != ch["slowmode"]:
                        await existing.edit(slowmode_delay=ch["slowmode"])
                        degisti = True
                    if degisti:
                        report["synced"].append(f"# {existing.name} izinleri")
                except discord.Forbidden:
                    report["errors"].append(f"{ch['key']} izin: 50013")
                report["skipped"].append(f"#{ch['name']}")
                continue

            spec = dict(ch)
            if ch["kind"] == "BOT_FEED" and ch.get("ping_roles"):
                spec["overwrites"] = odata._feed_overwrites(ch["ping_roles"])
            elif ch["kind"] in odata.KIND_TO_OVERWRITES:
                spec["overwrites"] = odata.KIND_TO_OVERWRITES[ch["kind"]]()
            spec = _strip_private(spec, cat)
            owmap = _build_overwrite_map(guild, spec, me)
            cres = await _ensure_channel(guild, spec, parent, owmap)
            if cres.status == StepResult.CREATED:
                store.mark(guild.id, ch["key"], "CHANNEL", cres.entity.id)
                report["created"].append(f"# {cres.entity.name}")
            else:
                report["errors"].append(f"{ch['key']}: {cres.status}")

    report["automod"] = await _apply_automod(guild)
    store.save_state(guild.id, "OFFICIAL", "RAN" if not report["errors"] else "PARTIAL")

    # ---- kanal icerikleri (idempotent + eski kopyalari temizler) ----
    try:
        from provisioner.common.content import post_all_content
        report["content"] = await post_all_content(guild, db, official=True)
    except Exception as e:
        logger.warning(f"[Official] icerik postlama: {e}")
    return report


def _ow_farkli(mevcut: dict, hedef: dict) -> bool:
    """Overwrite sozlukleri esit mi? (Role/Member id bazli karsilastirma)"""
    if len(mevcut) != len(hedef):
        return True
    for target, po in hedef.items():
        if mevcut.get(target) != po:
            return True
    return False


def _strip_private(spec, cat):
    """Gizli kategorilerde kanal-bazli @everyone/Üye ALLOW'lari filtrele."""
    def _cat_view(target):
        for t, perms in cat.get("overwrites", []):
            if t == target and perms.get("view_channel") is False:
                return True
        return False
    strip_e = _cat_view("@everyone")
    strip_m = _cat_view(odata.MEMBER)
    if strip_e or strip_m:
        temiz = []
        for t, perms in spec.get("overwrites", []):
            if (t == "@everyone" and strip_e) or (t == odata.MEMBER and strip_m):
                continue
            temiz.append((t, perms))
        spec["overwrites"] = temiz
    return spec

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
