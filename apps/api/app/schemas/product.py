from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional


class ProductBase(BaseModel):
    product_id: str
    name: str
    url: str
    image_url: str = ""
    current_price: float = 0.0
    original_price: float = 0.0


class ProductCreate(ProductBase):
    guild_id: int
    channel_id: str = "0"


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    current_price: Optional[float] = None
    original_price: Optional[float] = None


class ProductResponse(ProductBase):
    id: int
    channel_id: str
    last_checked: datetime
    created_at: datetime
    user_id: int
    guild_id: int
    
    # User info
    username: str = ""
    avatar_url: str = ""
    
    class Config:
        from_attributes = True


class PriceHistoryResponse(BaseModel):
    id: int
    price: float
    timestamp: datetime
    
    class Config:
        from_attributes = True
