from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from models import User
from schemas import UserRegister, UserLogin
from database import get_db
from passlib.hash import bcrypt
from jose import jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET", "secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # أسبوع

router = APIRouter()


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/auth/register")
def register_user(user: UserRegister, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم بالفعل")

    hashed_password = bcrypt.hash(user.password)
    new_user = User(
        full_name=user.full_name,
        email=user.email,
        hashed_password=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token_data = {
        "sub": new_user.email,
        "user_id": new_user.id,
    }
    token = create_access_token(token_data)

    return {
        "token": token,
        "client_name": new_user.full_name
    }


@router.post("/auth/login")
def login_user(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not bcrypt.verify(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")

    token_data = {
        "sub": db_user.email,
        "user_id": db_user.id,
    }
    token = create_access_token(token_data)

    return {
        "token": token,
        "client_name": db_user.full_name
    }
