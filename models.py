from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    google_id = Column(String, nullable=True)
    auth_provider = Column(String, default='manual')

    # ✅ الحقول المضافة
    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    store_url = Column(String, nullable=False)
    heard_from = Column(String, nullable=True)
    plan = Column(String, nullable=True)

    analytics_tokens = relationship("UserAnalyticsToken", back_populates="user")

class UserAnalyticsToken(Base):
    __tablename__ = 'user_analytics_tokens'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    token_uri = Column(String, nullable=False)
    client_id = Column(String, nullable=False)
    client_secret = Column(String, nullable=False)
    scopes = Column(String, nullable=False)

    user = relationship("User", back_populates="analytics_tokens")
