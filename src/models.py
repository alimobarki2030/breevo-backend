from sqlalchemy import Column, String, Integer, Text
from src.database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String)
    name = Column(String)
    description = Column(Text)
    seo_title = Column(String)
    seo_url = Column(String)
    meta_description = Column(String)
    status = Column(String)
    seoScore = Column(Integer)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String, nullable=True)

class UserAnalyticsToken(Base):
    __tablename__ = "analytics_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, index=True)
    refresh_token = Column(String)
    client_id = Column(String)
    client_secret = Column(String)
    property_id = Column(String)

    token_uri = Column(String, default="https://oauth2.googleapis.com/token")