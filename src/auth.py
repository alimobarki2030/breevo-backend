from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from jose import jwt
from database import get_db
from models import User

router = APIRouter()

SECRET_KEY = "mysecret"
ALGORITHM = "HS256"

@router.post("/auth/register")
def register(email: str, password: str, full_name: str, db: Session = Depends(get_db)):
    existing = db.query(User).filter_by(email=email).first()
    if existing:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقًا")

    user = User(email=email, full_name=full_name)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = jwt.encode({"user_id": user.id}, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token}

# ✅ دالة المصادقة المطلوبة
def get_current_user(token: str = "", db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="رمز التوكن غير صالح")
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=401, detail="المستخدم غير موجود")
        return {"id": user.id}
    except Exception:
        raise HTTPException(status_code=401, detail="فشل التحقق من التوكن")
