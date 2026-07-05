from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


async def get_user(db: AsyncSession, user_id: int):
    """Get user by ID."""
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_user_by_discord_id(db: AsyncSession, discord_id: str):
    """Get user by Discord ID."""
    query = select(User).where(User.discord_id == discord_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_data: dict):
    """Create a new user."""
    user = User(**user_data)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user_id: int, user_data: UserUpdate):
    """Update user details."""
    user = await get_user(db, user_id)
    
    if user:
        update_data = user_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(user, key, value)
        await db.flush()
        await db.refresh(user)
    
    return user
