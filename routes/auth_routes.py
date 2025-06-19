from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from database import get_db
from models import User
from schemas import UserRegister, UserLogin
from dotenv import load_dotenv
from urllib.parse import urlparse
import os

load_dotenv()

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

router = APIRouter()
auth_router = router  # للتوافق مع الكود القديم


def normalize_url(url: str) -> str:
    """Normalize URL format"""
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)
    netloc = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.rstrip("/")
    return f"https://{netloc}{path}" if netloc else ""


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user


@router.post("/auth/register")
def register_user(user: UserRegister, db: Session = Depends(get_db)):
    """Register a new user"""
    try:
        print(f"محاولة تسجيل مستخدم: {user.email}")
        
        existing_user = db.query(User).filter(User.email == user.email).first()
        if existing_user:
            print(f"البريد الإلكتروني موجود بالفعل: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="البريد الإلكتروني مستخدم بالفعل"
            )
    except Exception as e:
        print(f"خطأ في التحقق من البريد الإلكتروني: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="حدث خطأ في الخادم"
        )

    try:
        hashed_password = get_password_hash(user.password)
        new_user = User(
            full_name=user.full_name,
            email=user.email,
            hashed_password=hashed_password,
            phone=user.phone,
            store_url=normalize_url(user.store_url),
            plan=user.plan
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        access_token = create_access_token(data={"sub": str(new_user.id)})
        print(f"تم تسجيل المستخدم بنجاح: {user.email}")
        return {
            "token": access_token,  # غيّر access_token إلى token
            "access_token": access_token,  # احتفظ بـ access_token للتوافق
            "token_type": "bearer", 
            "client_name": new_user.full_name
        }
    except Exception as e:
        print(f"خطأ في إنشاء المستخدم: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="حدث خطأ في إنشاء المستخدم"
        )


@router.post("/auth/login")
def login_user(user: UserLogin, db: Session = Depends(get_db)):
    """Login user and return access token"""
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="البريد الإلكتروني أو كلمة المرور غير صحيحة"
        )

    access_token = create_access_token(data={"sub": str(db_user.id)})
    return {
        "token": access_token,  # غيّر access_token إلى token
        "access_token": access_token,  # احتفظ بـ access_token للتوافق
        "token_type": "bearer", 
        "client_name": db_user.full_name
    }


@router.get("/auth/check-email")
def check_email_exists(email: str, db: Session = Depends(get_db)):
    """Check if email already exists in database"""
    existing_user = db.query(User).filter(User.email == email).first()
    return JSONResponse(content={"exists": bool(existing_user)})


@router.get("/auth/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "phone": current_user.phone,
        "store_url": current_user.store_url,
        "plan": current_user.plan
    }