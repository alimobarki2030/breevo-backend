from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routes.auth_routes import router as auth_router
from routes.google_auth import router as google_router
from routes.analytics_routes import router as analytics_router
from routes.ga4 import router as ga4_router
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# ✅ إنشاء الجداول في قاعدة البيانات
Base.metadata.create_all(bind=engine)

# ✅ إعدادات CORS لرابط الواجهة فقط
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://breevo-frontend.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ إضافة المسارات (routers)
app.include_router(auth_router)
app.include_router(google_router)
app.include_router(analytics_router)
app.include_router(ga4_router)

# ✅ مسار الجذر
@app.get("/")
def root():
    return {"message": "Hello World"}
