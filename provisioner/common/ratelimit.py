"""Siral olusturma + rate limit guvenli cagri yardimcisi (2.3, Bolum 7)."""
import asyncio
import logging

import discord

logger = logging.getLogger("Trendcord")

MAX_RETRY = 3


class StepResult:
    """Tek bir olusturma adiminin sonucu."""
    __slots__ = ("key", "status", "entity", "detail")

    CREATED = "CREATED"
    SKIPPED = "SKIP"
    SKIPPED_PERM = "SKIPPED_PERM"
    SKIPPED_REF = "SKIPPED_REF"
    RENAMED = "RENAMED"
    FAILED = "FAILED"

    def __init__(self, key, status, entity=None, detail=""):
        self.key = key
        self.status = status
        self.entity = entity
        self.detail = detail


async def safe_call(key, coro_factory, retry=MAX_RETRY) -> StepResult:
    """coro_factory: her denemede taze coroutine ureten callable (429 icin)."""
    attempt = 0
    while True:
        try:
            entity = await coro_factory()
            return StepResult(key, StepResult.CREATED, entity)
        except discord.Forbidden:
            logger.warning(f"[Provisioner] {key}: izin yok (50013) — atlandi")
            return StepResult(key, StepResult.SKIPPED_PERM)
        except discord.HTTPException as e:
            if e.status == 429 and attempt < retry:
                wait = getattr(e, "retry_after", None) or 2.0 * (attempt + 1)
                logger.info(f"[Provisioner] {key}: rate limit, {wait:.1f}s bekleniyor")
                await asyncio.sleep(wait)
                attempt += 1
                continue
            logger.error(f"[Provisioner] {key}: HTTP {e.status} — {e.text}")
            return StepResult(key, StepResult.FAILED, detail=str(e))
        except Exception as e:  # beklenmedik — kurulumu durdurmaz
            logger.error(f"[Provisioner] {key}: {type(e).__name__}: {e}")
            return StepResult(key, StepResult.FAILED, detail=str(e))


async def create_channel_safe(guild, key, kind, factory):
    """Kanal/kategori olustur; ayni adda bizim olmayan kanal varsa '-tc' eki dene (2.2c)."""
    res = await safe_call(key, factory)
    if res.status == StepResult.FAILED and "Zaten bu isimde" not in res.detail:
        pass  # isim cakismasi Discord'da hata vermez; isim tabanlı cakisma asagida
    return res
