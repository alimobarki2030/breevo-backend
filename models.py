from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    google_id = Column(String, nullable=True)

class UserAnalyticsToken(Base):
    __tablename__ = "user_analytics_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    refresh_token = Column(String, nullable=False)
    client_id = Column(String, nullable=False)
    client_secret = Column(String, nullable=False)
    property_id = Column(String, nullable=True)
    access_token = Column(String, nullable=True)  # ✅ أضفناها بناءً على استدعاء analytics_routes.py
    id_token = Column(String, nullable=True)      # ✅ أضفناها بناءً على استدعاء analytics_routes.py
