from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google_auth import router as google_auth_router
from analytics_routes import router as analytics_router
from routes.ga4 import router as ga4_router  # ✅ مضافة باسم منطقي
from database import create_database

print("🚀 بدء تشغيل تطبيق Breevo...")

app = FastAPI()

# ✅ إعداد CORS للسماح فقط من localhost:3000
origins = ["http://localhost:3000"]
print("🌐 إعداد CORS...")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Include routers
print("🔌 ربط google_auth_router...")
app.include_router(google_auth_router)

print("📊 ربط analytics_router...")
app.include_router(analytics_router, prefix="/analytics")

print("📈 ربط ga4_router...")
app.include_router(ga4_router, prefix="/analytics")

@app.get("/")
async def root():
    return {"message": "Breevo Backend is running 🚀"}

# ✅ Database initialization
print("🗃️ استدعاء create_database() ...")
try:
    create_database()
    print("✅ قاعدة البيانات تم إنشاؤها بنجاح.")
except Exception as e:
    print(f"❌ خطأ أثناء إنشاء قاعدة البيانات: {e}")