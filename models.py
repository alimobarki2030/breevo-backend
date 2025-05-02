from sqlalchemy import Column, Integer, String
from database import Base

class UserAnalyticsToken(Base):
    __tablename__ = "user_analytics_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    refresh_token = Column(String, nullable=False)
    client_id = Column(String, nullable=False)
    client_secret = Column(String, nullable=False)
    property_id = Column(String, nullable=True)
