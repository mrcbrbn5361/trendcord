from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.models.base import get_db
from app.schemas.guild import GuildCreate, GuildUpdate, GuildResponse
from app.services.guild import get_guilds, get_guild, create_guild, update_guild
from app.services.auth import verify_token

router = APIRouter(prefix="/guilds", tags=["guilds"])


async def get_current_user_id(request: Request) -> int:
    """Extract user ID from JWT token."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return int(payload["sub"])


@router.get("/", response_model=List[GuildResponse])
async def list_guilds(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """List all guilds."""
    guilds = await get_guilds(db, skip=skip, limit=limit)
    return guilds


@router.get("/{discord_id}", response_model=GuildResponse)
async def get_single_guild(
    discord_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """Get single guild."""
    guild = await get_guild(db, discord_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    return guild


@router.post("/", response_model=GuildResponse)
async def create_new_guild(
    guild_data: GuildCreate,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """Create new guild."""
    guild = await create_guild(db, guild_data)
    return guild


@router.put("/{discord_id}", response_model=GuildResponse)
async def update_existing_guild(
    discord_id: str,
    guild_data: GuildUpdate,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """Update guild."""
    guild = await update_guild(db, discord_id, guild_data)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    return guild
