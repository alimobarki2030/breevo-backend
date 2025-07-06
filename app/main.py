# app/main.py - نسخة نظيفة
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from dotenv import load_dotenv
import os

# ✅ استيرادات نظيفة فقط (بدون products المحذوف)
from app.routers.ai import router as ai_router
from app.routers.auth import router as auth_router
from app.routers.dataforseo import router as dataforseo_router
from app.routers import salla
from app.routers.salla_products import router as salla_products_router
from app.routers.dashboard import router as dashboard_router

load_dotenv()

app = FastAPI(
    title="Salla SEO Integration API",
    description="API لربط وإدارة متاجر سلة مع تحسين SEO بالذكاء الاصطناعي",
    version="1.0.0"
)

# ✅ إعدادات CORS محدثة
origins = [
    "http://localhost:3000",
    "https://breevo-frontend.vercel.app", 
    "https://seoraysa.com",
    "https://www.seoraysa.com",
    "https://breevo-backend.onrender.com",
    "https://accounts.google.com",
    "https://www.google.com",
    os.getenv("BACKEND_URL", ""),
    os.getenv("FRONTEND_URL", "")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in origins if origin],  # تنظيف القائمة من القيم الفارغة
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("✅ Database engine created")

# إنشاء جداول قاعدة البيانات
Base.metadata.create_all(bind=engine)

# تسجيل الـ Routers النظيفة
app.include_router(ai_router, prefix="/api/ai", tags=["ai"])
app.include_router(auth_router)
app.include_router(dataforseo_router)
app.include_router(salla.router)
app.include_router(salla_products_router)
app.include_router(dashboard_router)

@app.get("/")
def read_root():
    return {
        "message": "Salla SEO Integration API",
        "status": "running",
        "version": "1.0.0",
        "documentation": "/docs"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "services": {
            "salla": "active",
            "ai": "active",
            "auth": "active",
            "dataforseo": "active",
            "email": "configured" if os.getenv("ZOHO_EMAIL_USERNAME") else "not configured"
        }
    }

@app.get("/api/info")
def system_info():
    return {
        "backend_url": os.getenv("BACKEND_URL"),
        "frontend_url": os.getenv("FRONTEND_URL"),
        "salla_configured": bool(os.getenv("SALLA_CLIENT_ID")),
        "email_configured": bool(os.getenv("ZOHO_EMAIL_USERNAME")),
        "ai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "dataforseo_configured": bool(os.getenv("DATAFORSEO_LOGIN"))
    }

# Middleware لتسجيل الطلبات في development
if os.getenv("DEBUG", "False").lower() == "true":
    @app.middleware("http")
    async def log_requests(request, call_next):
        import time
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        print(f"⏱️ {request.method} {request.url.path} - {process_time:.3f}s")
        return response