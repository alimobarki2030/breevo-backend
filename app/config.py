# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """إعدادات التطبيق المركزية"""
    
    # إعدادات قاعدة البيانات
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    
    # إعدادات JWT
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    
    # إعدادات Google OAuth
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    
    # إعدادات Salla API
    SALLA_CLIENT_ID = os.getenv("SALLA_CLIENT_ID")
    SALLA_CLIENT_SECRET = os.getenv("SALLA_CLIENT_SECRET")
    
    # إعدادات OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # إعدادات DataForSEO
    DATAFORSEO_LOGIN = os.getenv("DATAFORSEO_LOGIN")
    DATAFORSEO_PASSWORD = os.getenv("DATAFORSEO_PASSWORD")
    
    # إعدادات Frontend
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # إعدادات CORS
    CORS_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://yourapp.com"
    ]
    
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

settings = Settings()