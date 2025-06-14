from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.auth_routes import router as auth_router


from database import engine, Base
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
app.include_router(auth_router, prefix="/auth")

# ✅ مسار الجذر
@app.get("/")
def root():
    return {"message": "Hello World"}
