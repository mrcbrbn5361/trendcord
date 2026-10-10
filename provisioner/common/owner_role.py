"""Trendcord Bot Owner rolu (G1 istisnasi — tek istisna, bu dosya).

Kurallar:
  * Sunucuya eklendiginde/ kuruldugunde `Trendcord Bot Owner` rolu ACILIR.
  * Rolun guild-baz (tabanda) HICBIR izni yoktur; yetkisi yalnizca Trendcord'un
    OLUSTURDUGU kanallara yazilan channel overwrite'lerinden gelir.
  * Rol yalnizca OWNER_ID kullanicisina verilir. Baska bir uyeye verilirse
    (manuel / panel / bot) anlikca geri alinir.
  * Rol `mentionable=False`, `hoist=False` — member listesinde gorunmez,
    @ ile etiketlenemez; bu yuzden yanlislikla dagitilamaz.
"""
import logging
import os

import discord

logger = logging.getLogger("Trendcord")

OWNER_ROLE_NAME = "Trendcord Bot Owner"
ENTITY_KEY = "role:trendcord-bot-owner"
OWNER_COLOR = 0xF27A1A

# Botun olusturdugu kanallarda sahip rolunun tam yetkisi.
# administrator BILINCLI OLARAK VERILMEZ: rol yalnizca bu kanallarda gecerli
# olmali, sunucunun geri kalaninda hicbir sey gormemeli.
OWNER_ALLOW = [
    "view_channel", "send_messages", "send_messages_in_threads",
    "embed_links", "attach_files", "read_message_history", "add_reactions",
    "use_application_commands", "use_external_emojis",
    "manage_messages", "manage_channels", "manage_threads", "manage_roles",
    "create_public_threads", "create_private_threads",
    "move_members", "mute_members", "mention_everyone", "manage_webhooks",
    "manage_emojis",
]


def owner_user_id() -> int | None:
    """Rolun verilebileceği tek kullanıcı (OWNER_ID)."""
    raw = os.getenv("OWNER_ID", "").strip()
    return int(raw) if raw.isdigit() else None


def get_owner_role(guild) -> discord.Role | None:
    return discord.utils.find(lambda r: r.name == OWNER_ROLE_NAME, guild.roles)


def _full_po() -> discord.PermissionOverwrite:
    return discord.PermissionOverwrite(**{p: True for p in OWNER_ALLOW})


async def ensure_owner_role(guild, db=None) -> discord.Role | None:
    """Idempotent: rol yoksa olusturur, ayarlari degistiyse duzeltir.

    Donus: rol nesnesi veya None (izin yok / OWNER_ID tanimsiz).
    """
    role = get_owner_role(guild)
    if role is None:
        try:
            role = await guild.create_role(
                name=OWNER_ROLE_NAME,
                colour=discord.Colour(OWNER_COLOR),
                hoist=False,
                mentionable=False,
                permissions=discord.Permissions.none(),
                reason="Trendcord: bot sahibi rolu")
        except discord.Forbidden:
            logger.warning(f"[OwnerRole] {guild.id}: rol olusturulamadı (Manage Roles yok)")
            return None
        except Exception as e:
            logger.warning(f"[OwnerRole] {guild.id}: rol olusturma hatasi: {e}")
            return None
        logger.info(f"[OwnerRole] {guild.id}: '{OWNER_ROLE_NAME}' olusturuldu")

    if db is not None:
        from provisioner.common.store import SetupStore
        SetupStore(db).mark(guild.id, ENTITY_KEY, "ROLE", role.id,
                            {"name": OWNER_ROLE_NAME})

    # Tabanda hicbir izin, gorunur/etikeslenebilir olmamali
    if (role.permissions.value != 0 or role.hoist or role.mentionable):
        try:
            await role.edit(hoist=False, mentionable=False,
                            permissions=discord.Permissions.none(),
                            reason="Trendcord: bot sahibi rolu kilidi")
        except Exception as e:
            logger.debug(f"[OwnerRole] {guild.id}: rol ayarlari duzeltilemedi: {e}")
    return role


async def apply_owner_overwrites(guild, db, role=None) -> int:
    """Botun yonettigi tum kategori/kanallarda sahip rolune tam yetki yazar.

    Mevcut overwrite'ler korunur (bot/admin/mod matristi bozulmaz), yalnizca
    sahip rolu eklenir/eskisi duzeltilir.
    """
    from provisioner.common.store import SetupStore
    role = role or get_owner_role(guild)
    if role is None or db is None:
        return 0

    store = SetupStore(db)
    target = _full_po()
    touched = 0
    for ent in store.entities(guild.id):
        if ent["entity_type"] not in ("CHANNEL", "CATEGORY"):
            continue
        ch = guild.get_channel(int(ent["discord_id"]))
        if ch is None:
            continue
        current = dict(ch.overwrites)
        if current.get(role) == target:
            continue
        current[role] = target
        try:
            await ch.edit(overwrites=current, reason="Trendcord: bot sahibi yetkisi")
            touched += 1
        except discord.Forbidden:
            logger.debug(f"[OwnerRole] {guild.id}/{ent['key']}: overwrite yazilamadi")
        except Exception as e:
            logger.debug(f"[OwnerRole] {guild.id}/{ent['key']}: {e}")

    if touched:
        logger.info(f"[OwnerRole] {guild.id}: {touched} kanal/kategoriye tam yetki yazildi")
    return touched


def may_hold_role(user_id) -> bool:
    """Bu kullaniciya rol verilebilir mi? (beyaz liste)"""
    oid = owner_user_id()
    return oid is not None and int(user_id) == oid


async def assign_owner(guild, role=None) -> bool:
    """Rolu yalnizca OWNER_ID'ye verir. Donus: verildi mi."""
    oid = owner_user_id()
    if oid is None:
        return False
    role = role or get_owner_role(guild)
    if role is None:
        return False
    member = guild.get_member(oid)
    if member is None or role in member.roles:
        return False
    try:
        await member.add_roles(role, reason="Trendcord: bot sahibi")
        logger.info(f"[OwnerRole] {guild.id}: rol {member} uyesine verildi")
        return True
    except Exception as e:
        logger.warning(f"[OwnerRole] {guild.id}: rol verilemedi: {e}")
        return False


async def strip_unauthorized(guild, role=None) -> int:
    """Rolu sahibi olmayan her uyeden kaldirir (beyaz liste ihlali temizligi)."""
    role = role or get_owner_role(guild)
    if role is None:
        return 0
    removed = 0
    for member in list(guild.members):
        if role not in member.roles or may_hold_role(member.id):
            continue
        try:
            await member.remove_roles(role, reason="Trendcord: yetkisiz rol kullanimi")
            removed += 1
            logger.info(f"[OwnerRole] {guild.id}: rol {member} uyesinden kaldirildi")
        except Exception as e:
            logger.debug(f"[OwnerRole] {guild.id}/{member}: {e}")
    return removed


async def enforce_owner_only(guild) -> int:
    """Baska biri rolu aldiysa geri alir (event tabanli calisir)."""
    role = get_owner_role(guild)
    if role is None:
        return 0
    return await strip_unauthorized(guild, role)


async def provision(guild, db) -> dict:
    """Tam akis: rolu ac -> kanallara tam yetki ver -> sahibine ata -> yetkisizleri temizle."""
    report = {"role": False, "channels": 0, "assigned": False, "stripped": 0}
    role = await ensure_owner_role(guild, db)
    if role is None:
        return report
    report["role"] = True
    report["channels"] = await apply_owner_overwrites(guild, db, role)
    report["assigned"] = await assign_owner(guild, role)
    report["stripped"] = await strip_unauthorized(guild, role)
    return report


async def teardown(guild) -> bool:
    """/setup-kaldir: rolu ve tum overwrite'lerini temizler."""
    role = get_owner_role(guild)
    if role is None:
        return False
    for ch in list(guild.channels):
        if role in ch.overwrites:
            current = dict(ch.overwrites)
            del current[role]
            try:
                await ch.edit(overwrites=current)
            except Exception:
                pass
    try:
        await role.delete(reason="Trendcord: /setup-kaldir")
        logger.info(f"[OwnerRole] {guild.id}: '{OWNER_ROLE_NAME}' silindi")
        return True
    except Exception as e:
        logger.warning(f"[OwnerRole] {guild.id}: rol silinemedi: {e}")
        return False