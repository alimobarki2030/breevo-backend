# app/main.py - نسخة محدثة مع إصلاحات CORS الكاملة
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
from app.routers.points import router as points_router
from app.routers.subscription import router as subscription_router
from app.routers.admin import router as admin_router
from app.models import user, points


load_dotenv()

app = FastAPI(
    title="Salla SEO Integration API",
    description="API لربط وإدارة متاجر سلة مع تحسين SEO بالذكاء الاصطناعي",
    version="1.0.0"
)

# ✅ إعدادات CORS محدثة - إضافة allow_origins=["*"] مؤقتاً
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # السماح لجميع النطاقات مؤقتاً
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

print("✅ Database engine created")

# إنشاء جداول قاعدة البيانات
Base.metadata.create_all(bind=engine)

# Middleware لمعالجة الأخطاء
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    print(f"❌ Error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )

# تسجيل الـ Routers النظيفة
app.include_router(ai_router, prefix="/api/ai", tags=["ai"])
app.include_router(auth_router)
app.include_router(dataforseo_router)
app.include_router(salla.router)
app.include_router(salla_products_router)
app.include_router(dashboard_router)
app.include_router(points_router)
app.include_router(subscription_router)
app.include_router(admin_router)

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
@app.middleware("http")
async def log_requests(request: Request, call_next):
    import time
    start_time = time.time()
    
    # طباعة معلومات الطلب
    print(f"📨 {request.method} {request.url.path}")
    
    # معالجة OPTIONS requests بشكل خاص
    if request.method == "OPTIONS":
        return JSONResponse(
            content={},
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Credentials": "true",
            }
        )
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # إضافة headers إضافية للتأكد
        response.headers["X-Process-Time"] = str(process_time)
        
        # إضافة CORS headers لجميع الاستجابات
        origin = request.headers.get("origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        # طباعة معلومات الاستجابة
        print(f"✅ {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
        
        return response
    except Exception as e:
        process_time = time.time() - start_time
        print(f"❌ {request.method} {request.url.path} - ERROR - {process_time:.3f}s - {str(e)}")
        raise