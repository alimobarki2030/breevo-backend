# app/main.py - التحديث البسيط المطلوب فقط
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from dotenv import load_dotenv
import os

# ✅ استيرادات مصححة للـ deployment
from app.routers.products import router as product_router
from app.routers.ai import router as ai_router
from app.routers.auth import router as auth_router
from app.routers.dataforseo import router as dataforseo_router
from app.routers import salla

load_dotenv()

app = FastAPI(
    title="Salla Integration API",
    description="API لربط وإدارة متاجر سلة",
    version="1.0.0"
)

# ✅ التحديث الوحيد المطلوب: إضافة BACKEND_URL من متغيرات البيئة
origins = [
    "http://localhost:3000",
    "https://breevo-frontend.vercel.app", 
    "https://seoraysa.com",
    "https://www.seoraysa.com",
    "https://breevo-backend.onrender.com",
    "https://accounts.google.com",
    "https://www.google.com",
    os.getenv("BACKEND_URL", ""),  # إضافة البيئة المتغيرة
    os.getenv("FRONTEND_URL", "")  # إضافة البيئة المتغيرة
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in origins if origin],  # تنظيف القائمة
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("✅ Database engine created")

# إنشاء جداول قاعدة البيانات
Base.metadata.create_all(bind=engine)

# تسجيل الـ Routers
app.include_router(product_router)
app.include_router(ai_router)
app.include_router(auth_router)
app.include_router(dataforseo_router)
app.include_router(salla.router)

@app.get("/")
def read_root():
    return {
        "message": "Salla Integration API",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "services": ["salla", "products", "ai", "auth", "dataforseo"]
    }

# ✅ إضافة endpoint بسيط لمعلومات النظام
@app.get("/api/info")
def system_info():
    return {
        "backend_url": os.getenv("BACKEND_URL"),
        "frontend_url": os.getenv("FRONTEND_URL"),
        "salla_configured": bool(os.getenv("SALLA_CLIENT_ID")),
        "email_configured": bool(os.getenv("ZOHO_EMAIL_USERNAME"))
    }

# ✅ Add a test endpoint to verify products API
@app.get("/test-products")
def test_products():
    return {
        "message": "Products API is working!", 
        "endpoints": [
            "GET /products - Get user products",
            "POST /products - Create product",
            "GET /products/{id} - Get product",
            "PUT /products/{id} - Update product", 
            "DELETE /products/{id} - Delete product"
        ]
    }