from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from jose import jwt
from database import get_db
from src.models import User

router = APIRouter()

SECRET_KEY = "mysecret"
ALGORITHM = "HS256"

@router.post("/auth/register")
def register(email: str, password: str, full_name: str, db: Session = Depends(get_db)):
    existing = db.query(User).filter_by(email=email).first()
    if existing:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقًا")

    user = User(email=email, password=password, full_name=full_name)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = jwt.encode({"user_id": user.id}, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token}