from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_id = Column(String(64), unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=False)
    avatar_url = Column(String(512), default="")
    access_token = Column(String(512), default="")
    refresh_token = Column(String(512), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    products = relationship("Product", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.username} ({self.discord_id})>"
