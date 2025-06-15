from fastapi import APIRouter, HTTPException, Form, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import User
from utils import verify_password, hash_password, create_access_token

router = APIRouter()

# ✅ تسجيل الدخول اليدوي
@router.post("/manual-login")
def manual_login(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="❌ البريد أو كلمة المرور غير صحيحة")
    
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

# ✅ تسجيل مستخدم جديد
@router.post("/register")
def register(
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم بالفعل")

    new_user = User(
        full_name=full_name,
        email=email,
        hashed_password=hash_password(password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token(data={"sub": str(new_user.id)})
    return {"token": token, "clientName": new_user.full_name}
