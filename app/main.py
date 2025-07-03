# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from dotenv import load_dotenv

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

origins = [
    "http://localhost:3000",
    "https://breevo-frontend.vercel.app",
    "https://seoraysa.com",
    "https://www.seoraysa.com",
    "https://breevo-backend.onrender.com",
    "https://accounts.google.com",
    "https://www.google.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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