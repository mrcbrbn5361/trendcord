from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    discord_id: str
    username: str
    avatar_url: str = ""


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    username: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserSession(BaseModel):
    id: int
    discord_id: str
    username: str
    avatar_url: str
