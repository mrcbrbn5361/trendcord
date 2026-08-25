"""Client guild otomatik kurulum runner (Modul B).

G1: Bu dosyanin kod yolunda HICBIR rol olusturma/guncelleme/silme cagrisi
bulunmaz — roller yalnizca OKUNUR (analyze_roles).
"""
import logging

import discord

from provisioner.common import overwrites as owlib
from provisioner.common.analyzer import analyze_roles, resolve_role_lists
from provisioner.common.ratelimit import safe_call, StepResult
from provisioner.client import data as cdata

logger = logging.getLogger("Trendcord")

REQUIRED_PERMS = ["view_channel", "manage_channels"]


def check_permissions(guild) -> list:
    """Eksik ZORUNLU izinleri dondurur; bos liste = kurulabilir."""
    me = guild.me
    missing = []
    if me is None:
        return REQUIRED_PERMS
    for p in REQUIRED_PERMS:
        if not getattr(me.guild_permissions, p, False):
            missing.append(p)
    return missing


async def _create_category(guild, spec, overwrite_map, position_top):
    async def factory():
        cat = await guild.create_category(spec["name"], overwrites=overwrite_map)
        if position_top:
            try:
                await cat.edit(position=1)
            except Exception:
                pass
        return cat
    return await safe_call(spec["key"], factory)


async def _create_channel(guild, ch, overwrite_map):
    kind = ch["kind"]

    async def factory():
        kwargs = {
            "name": ch["name"],
            "overwrites": overwrite_map,
        }
        if ch.get("topic") and kind != "PANEL":
            kwargs["topic"] = ch["topic"]
        if ch.get("news"):
            try:
                kwargs["type"] = discord.ChannelType.news
            except Exception:
                pass
        if kind == "PANEL":
            kwargs["topic"] = ch.get("topic", "Destek talebi aç")
        return await guild.create_text_channel(**kwargs)

    res = await safe_call(ch["key"], factory)
    # NEWS olusmadiysa (Community kapali) TEXT fallback dene (4.5)
    if res.status != StepResult.CREATED and ch.get("news"):
        async def factory_text():
            return await guild.create_text_channel(
                name=ch["name"], overwrites=overwrite_map,
                topic=ch.get("topic", ""))
        res = await safe_call(ch["key"] + ":text", factory_text)
    if res.status == StepResult.CREATED and ch.get("slowmode"):
        try:
            await res.entity.edit(slowmode_delay=ch["slowmode"])
        except Exception:
            pass
    return res


def _resolve_conflict(guild, name: str, ours_ids: set) -> str:
    """Ayni adda bizim olmayan kanal varsa '-tc' eki (2.2c)."""
    existing = {c.name.lower() for c in guild.channels if c.id not in ours_ids}
    if name.lower() not in existing:
        return name
    return f"{name}-tc"


async def apply_setup(guild, modules: dict = None, analysis: dict = None, db=None) -> dict:
    """Idempotent kurulum. Donus: rapor sozlugu.

    Rapor: {"status": RAN|PARTIAL|FAILED, "created": [...], "skipped": [...],
            "errors": [...], "analysis": {...}}
    """
    from provisioner.common.store import SetupStore
    assert db is not None, 'db gerekli'
    store = SetupStore(db)

    missing = check_permissions(guild)
    if missing:
        return {"status": "FAILED", "reason": "missing_perms", "missing": missing,
                "created": [], "skipped": [], "errors": []}

    if analysis is None:
        analysis = analyze_roles(guild)
    admin_roles, mod_roles, support_roles = resolve_role_lists(guild, analysis)

    me = guild.me
    ours = store.entities(guild.id)
    ours_ids = {int(e["discord_id"]) for e in ours}

    report = {"status": "RAN", "created": [], "skipped": [], "errors": [],
              "analysis": analysis}

    for cat in cdata.channel_set(modules or {}):
        if cat.get("flat"):
            # duz kanal (modul) — managed kategoriye baglanir
            parent = next((guild.get_channel(int(e["discord_id"]))
                           for e in ours if e["key"] == cat.get("parent_key")), None)
            owmap = owlib.build_overwrites(cat["kind"], me, admin_roles,
                                           mod_roles, support_roles, everyone=False)
            name = _resolve_conflict(guild, cat["name"], ours_ids)
            res = await _create_channel(guild, {**cat, "name": name}, owmap)
            if res.status == StepResult.CREATED and parent is not None:
                try:
                    await res.entity.edit(category=parent)
                except Exception:
                    pass
            _record_channel(store, guild, cat["key"], res, report)
            continue

        # kategori
        existing_cat = store.entity(guild.id, cat["key"])
        category = None
        if existing_cat and not existing_cat["deleted_at"]:
            category = guild.get_channel(int(existing_cat["discord_id"]))
        if category is not None:
            res = StepResult(cat["key"], StepResult.SKIPPED, category)
        else:
            owmap = owlib.build_overwrites("OPEN", me, admin_roles, mod_roles,
                                           support_roles, everyone=False)
            name = _resolve_conflict(guild, cat["name"], ours_ids)
            res = await _create_category(guild, {**cat, "name": name},
                                         owmap, position_top=True)
            if res.status == StepResult.CREATED:
                store.mark(guild.id, cat["key"], "CATEGORY",
                           res.entity.id, {"name": cat["name"]})
                report["created"].append(f"📂 {res.entity.name}")
            else:
                _record(store, guild, cat["key"], "CATEGORY", res, report)
                continue
        if res.status == StepResult.SKIPPED:
            report["skipped"].append(f"📂 {category.name}")

        # kanallar
        for ch in cat.get("channels", []):
            ent = store.entity(guild.id, ch["key"])
            if ent and not ent["deleted_at"] and guild.get_channel(int(ent["discord_id"])):
                report["skipped"].append(f"#{ch['name']} (var)")
                continue
            everyone_flag = ch["kind"] != "OPEN"
            owmap = owlib.build_overwrites(ch["kind"], me, admin_roles,
                                           mod_roles, support_roles,
                                           everyone=everyone_flag)
            name = _resolve_conflict(guild, ch["name"], ours_ids)
            cres = await _create_channel(guild, {**ch, "name": name}, owmap)
            if cres.status == StepResult.CREATED and category is not None:
                try:
                    await cres.entity.edit(category=category)
                except Exception:
                    pass
            _record_channel(store, guild, ch["key"], cres, report)

    if report["errors"]:
        report["status"] = "PARTIAL"
    store.save_state(guild.id, "CLIENT", report["status"], analysis)

    # kanal icerikleri (embed/panel) — idempotent, rol dokunulmaz (G1)
    try:
        from provisioner.common.content import post_all_content
        report["content"] = await post_all_content(guild, db, official=False)
    except Exception as e:
        logger.warning(f"[ClientSetup] icerik postlama: {e}")

    logger.info(f"[ClientSetup] {guild.id}: {report['status']} "
                f"oluşturulan={len(report['created'])} atlanan={len(report['skipped'])}")
    return report


def _record(store, guild, key, etype, res, report):
    if res.status == StepResult.CREATED:
        store.mark(guild.id, key, etype, res.entity.id, {"name": res.entity.name})
        report["created"].append(res.entity.name)
    else:
        report["errors"].append(f"{key}: {res.status} {res.detail}".strip())


def _record_channel(store, guild, key, res, report):
    if res.status == StepResult.CREATED:
        store.mark(guild.id, key, "CHANNEL", res.entity.id, {"name": res.entity.name})
        report["created"].append(f"# {res.entity.name}")
    elif res.status == StepResult.SKIPPED:
        report["skipped"].append(key)
    else:
        report["errors"].append(f"{key}: {res.status} {res.detail}".strip())


async def remove_setup(guild, db=None) -> dict:
    """Yalnizca managed_entities kayitli kaynaklari siler (G4)."""
    from provisioner.common.store import SetupStore
    assert db is not None, 'db gerekli'
    store = SetupStore(db)
    removed, errors = [], []
    for ent in store.entities(guild.id):
        ch = guild.get_channel(int(ent["discord_id"]))
        if ch is None:
            store.mark_deleted(guild.id, ent["key"])
            continue

        async def factory(ch=ch):
            return await ch.delete(reason="Trendcord /setup-kaldir")
        res = await safe_call(ent["key"], factory)
        if res.status == StepResult.CREATED:
            store.mark_deleted(guild.id, ent["key"])
            removed.append(ent["key"])
        else:
            errors.append(f"{ent['key']}: {res.status}")
    return {"removed": removed, "errors": errors}


async def repair_setup(guild, modules: dict = None, db=None) -> dict:
    """Silinen managed kanallari yeniden kurar (idempotent — 4.7 repair)."""
    return await apply_setup(guild, modules=modules, db=db)
