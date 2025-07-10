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
    
    # أضف هذه الحقول المفقودة
    is_active = Column(Boolean, default=True)  # ✅ مطلوب
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)  # ✅ مطلوب
    
    # العلاقات
    salla_stores = relationship("SallaStore", back_populates="user")
    points = relationship("UserPoints", back_populates="user", uselist=False)