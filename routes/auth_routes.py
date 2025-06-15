from fastapi import APIRouter, HTTPException, Form, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import User
from utils import verify_password, hash_password, create_access_token

router = APIRouter()

# ✅ تسجيل مستخدم جديد
@router.post("/auth/register")
def register(
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    phone: str = Form(...),
    store_url: str = Form(...),
    heard_from: str = Form(None),
    plan: str = Form("free"),
    db: Session = Depends(get_db)
):
    try:
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم بالفعل")

        new_user = User(
            full_name=full_name,
            email=email,
            hashed_password=hash_password(password),
            phone=phone,
            store_url=store_url,
            heard_from=heard_from,
            plan=plan,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        token = create_access_token(data={"sub": str(new_user.id)})
        return {"token": token, "clientName": new_user.full_name}

    except Exception as e:
        print("🔥 حدث خطأ أثناء التسجيل:", e)
        raise HTTPException(status_code=500, detail="خطأ داخلي في الخادم")

# ✅ تسجيل الدخول اليدوي
@router.post("/auth/manual-login")
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
