# models/user.py
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    store_url = Column(String, nullable=True)
    plan = Column(String, nullable=True)
    
    # العلاقة مع متاجر سلة
    salla_stores = relationship("SallaStore", back_populates="user")