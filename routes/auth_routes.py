from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import UserCreate, UserLogin, Token
from utils import get_password_hash, verify_password, create_access_token
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from urllib.parse import urlparse
import os

load_dotenv()

auth_router = APIRouter()


def normalize_url(url: str) -> str:
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)
    netloc = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.rstrip("/")
    return f"https://{netloc}{path}" if netloc else ""


@auth_router.post("/auth/register", response_model=Token)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم بالفعل")

    hashed_password = get_password_hash(user.password)
    new_user = User(
        full_name=user.full_name,
        email=user.email,
        hashed_password=hashed_password,
        phone=user.phone,
        store_url=normalize_url(user.store_url),
        heard_from=user.heard_from,
        plan=user.plan
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    access_token = create_access_token(data={"sub": str(new_user.id)})
    return {"access_token": access_token, "token_type": "bearer", "client_name": new_user.full_name}


@auth_router.post("/auth/login", response_model=Token)
def login_user(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="البريد الإلكتروني أو كلمة المرور غير صحيحة")

    access_token = create_access_token(data={"sub": str(db_user.id)})
    return {"access_token": access_token, "token_type": "bearer", "client_name": db_user.full_name}


@auth_router.get("/auth/check-email")
def check_email_exists(email: str, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == email).first()
    return JSONResponse(content={"exists": bool(existing_user)})
