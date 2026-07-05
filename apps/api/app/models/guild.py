from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class Guild(Base):
    __tablename__ = "guilds"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    icon_url = Column(String(512), default="")
    owner_id = Column(String(64), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    products = relationship("Product", back_populates="guild")
    
    def __repr__(self):
        return f"<Guild {self.name} ({self.discord_id})>"
