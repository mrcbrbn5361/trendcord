from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(512), nullable=False)
    url = Column(String(1024), nullable=False)
    image_url = Column(String(1024), default="")
    current_price = Column(Float, default=0.0)
    original_price = Column(Float, default=0.0)
    last_checked = Column(DateTime, default=datetime.utcnow)
    channel_id = Column(String(64), default="0")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Foreign Keys
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    guild_id = Column(Integer, ForeignKey("guilds.id"), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="products")
    guild = relationship("Guild", back_populates="products")
    price_history = relationship("PriceHistory", back_populates="product")
    
    def __repr__(self):
        return f"<Product {self.name[:30]}... ({self.product_id})>"


class PriceHistory(Base):
    __tablename__ = "price_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Foreign Keys
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    
    # Relationships
    product = relationship("Product", back_populates="price_history")
    
    def __repr__(self):
        return f"<PriceHistory {self.price} at {self.timestamp}>"
