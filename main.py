from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.google_auth import router as google_auth_router
from routes.analytics_routes import router as analytics_router
from routes.ga4 import router as ga4_router
from database import create_database

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 بدء التشغيل: إنشاء قاعدة البيانات...")
    create_database()
    yield
    print("🛑 إيقاف التطبيق")

app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost:3000",
    "https://breevo-frontend-etsh.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# إضافة الراوترات
app.include_router(google_auth_router)
app.include_router(analytics_router)
app.include_router(ga4_router)
