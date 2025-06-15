from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import get_db
from models import User
import os

router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY", "mysecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ✅ مخطط البيانات المستخدم للتسجيل
class RegisterUser(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    phone: str
    store_url: str
    heard_from: str
    plan: str

# ✅ مخطط البيانات المستخدم لتسجيل الدخول
class LoginUser(BaseModel):
    email: EmailStr
    password: str

# ✅ دالة لإنشاء التوكن
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ✅ مسار تسجيل مستخدم جديد
@router.post("/auth/register")
async def register_user(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    print("📦 JSON المستلم من الواجهة:", body)

    try:
        user = RegisterUser(**body)
    except Exception as e:
        print("❌ خطأ في التحقق من البيانات:", e)
        raise HTTPException(status_code=422, detail="صيغة البيانات غير صحيحة")

    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        print("⚠️ البريد الإلكتروني مستخدم بالفعل")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="البريد الإلكتروني مستخدم بالفعل"
        )

    hashed_password = pwd_context.hash(user.password)
    db_user = User(
        full_name=user.full_name,
        email=user.email,
        hashed_password=hashed_password,
        phone=user.phone,
        store_url=user.store_url,
        heard_from=user.heard_from,
        plan=user.plan
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    token = create_access_token({"sub": user.email})
    print(f"✅ تم تسجيل المستخدم بنجاح: {user.email}")
    return {
    "access_token": token,
    "token_type": "bearer",
    "full_name": db_user.full_name  # ✅ أضفنا اسم العميل
}


# ✅ مسار تسجيل الدخول اليدوي
@router.post("/auth/manual-login")
def manual_login(user: LoginUser, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not pwd_context.verify(user.password, db_user.hashed_password):
        print("❌ بيانات الدخول غير صحيحة")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="بيانات الدخول غير صحيحة"
        )

    token = create_access_token({"sub": user.email})
    print(f"🔓 تسجيل دخول ناجح: {user.email}")
    return {"access_token": token, "token_type": "bearer"}
