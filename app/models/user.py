# models/user.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    store_url = Column(String, nullable=True)
    plan = Column(String, nullable=True)
    
    # حقول إضافية للإدارة
    is_admin = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    is_subscribed = Column(Boolean, default=False)
    subscription_tier = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # العلاقات
    salla_stores = relationship("SallaStore", back_populates="user")
    points = relationship("UserPoints", back_populates="user", uselist=False)  # علاقة واحد لواحد