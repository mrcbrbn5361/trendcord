from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
from app.models.guild import Guild
from app.models.product import Product
from app.schemas.guild import GuildCreate, GuildUpdate


async def get_guilds(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100
):
    """Get all guilds."""
    query = select(Guild).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_guild(db: AsyncSession, discord_id: str):
    """Get single guild by discord_id."""
    query = select(Guild).where(Guild.discord_id == discord_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create_guild(db: AsyncSession, guild_data: GuildCreate):
    """Create a new guild."""
    existing = await get_guild(db, guild_data.discord_id)
    if existing:
        return existing
    
    guild = Guild(**guild_data.model_dump())
    db.add(guild)
    await db.flush()
    await db.refresh(guild)
    return guild


async def update_guild(db: AsyncSession, discord_id: str, guild_data: GuildUpdate):
    """Update guild details."""
    guild = await get_guild(db, discord_id)
    
    if guild:
        update_data = guild_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(guild, key, value)
        await db.flush()
        await db.refresh(guild)
    
    return guild


async def get_guild_stats(db: AsyncSession):
    """Get guild statistics."""
    total_guilds = await db.scalar(select(func.count(Guild.id)))
    
    return {
        "guild_count": total_guilds or 0
    }
