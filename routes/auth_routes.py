# routes/auth_routes.py

from fastapi import APIRouter, HTTPException, Form, Depends
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from database import get_db
from models import User
from utils import create_access_token  # ✅ تأكد من المسار الصحيح بعد النقل

router = APIRouter()

# إعداد تشفير كلمات المرور
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/auth/manual-login")
def manual_login(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="❌ البريد الإلكتروني غير موجود")

    if not pwd_context.verify(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="❌ كلمة المرور غير صحيحة")

    # ✅ توليد JWT
    access_token = create_access_token(data={"sub": str(user.id)})

    return {
        "token": access_token,
        "google_linked": bool(user.google_id)
    }
