from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class GuildBase(BaseModel):
    discord_id: str
    name: str
    icon_url: str = ""
    owner_id: str = ""


class GuildCreate(GuildBase):
    pass


class GuildUpdate(BaseModel):
    name: Optional[str] = None
    icon_url: Optional[str] = None
    owner_id: Optional[str] = None


class GuildResponse(GuildBase):
    id: int
    created_at: datetime
    product_count: int = 0
    
    class Config:
        from_attributes = True
