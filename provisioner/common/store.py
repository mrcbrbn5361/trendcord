"""managed_entities / guild_settings DB erisimi — ince facade (SQL database.py'de)."""
import json
import logging

logger = logging.getLogger("Trendcord")


class SetupStore:
    """Provisioner icin DB facade. Mevcut Database metodlarini sarar."""

    def __init__(self, db):
        self.db = db

    # guild_settings
    def settings(self, guild_id) -> dict:
        s = self.db.get_guild_settings(guild_id)
        try:
            s["modules_parsed"] = json.loads(s.get("modules") or "{}")
        except Exception:
            s["modules_parsed"] = {}
        return s

    def set_auto_setup(self, guild_id, enabled: bool):
        self.db.set_guild_settings(guild_id, auto_setup=enabled)

    def set_modules(self, guild_id, modules: dict):
        self.db.set_guild_settings(guild_id, modules=modules)

    # setup state
    def save_state(self, guild_id, mode, status, analysis=None, error=None):
        self.db.upsert_setup_state(guild_id, mode=mode, status=status,
                                   analyzed_roles=analysis, last_error=error)

    def state(self, guild_id):
        return self.db.get_setup_state(guild_id)

    # managed entities
    def mark(self, guild_id, key, entity_type, discord_id, spec=None):
        self.db.mark_entity(guild_id, key, entity_type, discord_id, spec)

    def entities(self, guild_id, active_only=True):
        return self.db.get_entities(guild_id, active_only=active_only)

    def entity(self, guild_id, key):
        return self.db.get_entity(guild_id, key)

    def entity_by_discord_id(self, discord_id):
        return self.db.get_entity_by_discord_id(discord_id)

    def mark_deleted(self, guild_id, key):
        self.db.mark_entity_deleted(guild_id, key)
