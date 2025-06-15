from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import User
from utils import hash_password, verify_password, create_access_token
from pydantic import BaseModel, EmailStr

router = APIRouter()

# ✅ تعريف الـ Schemas
class RegisterInput(BaseModel):
    full_name: str
    email: EmailStr
    password: str

class LoginInput(BaseModel):
    email: EmailStr
    password: str

# ✅ تسجيل مستخدم جديد
@router.post("/register")
def register_user(payload: RegisterInput, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم بالفعل")

    hashed_password = hash_password(payload.password)
    new_user = User(full_name=payload.full_name, email=payload.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"sub": str(new_user.id)})
    return {"token": token}

# ✅ تسجيل دخول يدوي
@router.post("/manual-login")
def manual_login(payload: LoginInput, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="البريد الإلكتروني أو كلمة المرور غير صحيحة")

    token = create_access_token({"sub": str(user.id)})
    return {"token": token}
