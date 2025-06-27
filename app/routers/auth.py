from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.database import get_db
from app.models import User
from app.schemas import UserRegister, UserLogin
from dotenv import load_dotenv
from urllib.parse import urlparse
import os

# إضافة مكتبات Google
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

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
    print(f"محاولة تسجيل مستخدم: {user.email}")
    
    try:
        # فحص وجود البريد الإلكتروني داخل try
        existing_user = db.query(User).filter(User.email == user.email).first()
        if existing_user:
            print(f"البريد الإلكتروني موجود بالفعل: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="البريد الإلكتروني مستخدم بالفعل"
            )

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
            "token": access_token,
            "access_token": access_token,
            "token_type": "bearer",
            "client_name": new_user.full_name
        }
        
    except HTTPException:
        # إعادة رفع HTTPException كما هي
        raise
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
    print(f"محاولة تسجيل دخول: {user.email}")
    
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        print(f"فشل تسجيل الدخول: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="البريد الإلكتروني أو كلمة المرور غير صحيحة"
        )

    access_token = create_access_token(data={"sub": str(db_user.id)})
    print(f"تم تسجيل الدخول بنجاح: {user.email}")
    
    return {
        "token": access_token,
        "access_token": access_token,
        "token_type": "bearer",
        "client_name": db_user.full_name
    }


@router.post("/auth/google-login")
def google_login(request: dict, db: Session = Depends(get_db)):
    """Login with Google OAuth"""
    print(f"محاولة تسجيل دخول Google")
    
    try:
        # التحقق من وجود id_token في الطلب
        if 'id_token' not in request:
            print("لا يوجد id_token في الطلب")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="رمز Google مفقود"
            )
        
        # التحقق من Google ID Token
        print("التحقق من Google ID Token...")
        idinfo = id_token.verify_oauth2_token(
            request['id_token'], 
            google_requests.Request(), 
            os.getenv("GOOGLE_CLIENT_ID")
        )
        
        print(f"Google ID Token صحيح للمستخدم: {idinfo.get('email')}")
        
        # التحقق من صحة المصدر
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            print(f"مصدر غير صحيح: {idinfo['iss']}")
            raise ValueError('مصدر الرمز غير صحيح')
            
        # الحصول على معلومات المستخدم من Google
        google_id = idinfo['sub']
        email = idinfo['email']
        name = idinfo.get('name', email.split('@')[0])  # إذا لم يكن هناك اسم، استخدم جزء من الإيميل
        
        print(f"بيانات المستخدم من Google: {email}, {name}")
        
        # البحث عن المستخدم في قاعدة البيانات
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"إنشاء مستخدم جديد: {email}")
            # إنشاء مستخدم جديد
            user = User(
                full_name=name,
                email=email,
                hashed_password="google_user",  # علامة للمستخدمين من Google
                phone="",  # فارغ في البداية
                store_url="",  # فارغ في البداية
                plan="free"  # خطة مجانية افتراضية
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"تم إنشاء المستخدم بنجاح: {user.id}")
        else:
            print(f"تم العثور على مستخدم موجود: {user.id}")
            # تحديث الاسم إذا كان فارغاً
            if not user.full_name and name:
                user.full_name = name
                db.commit()
        
        # إنشاء رمز الوصول (JWT Token)
        access_token = create_access_token(data={"sub": str(user.id)})
        
        print(f"تم تسجيل دخول Google بنجاح للمستخدم: {email}")
        
        return {
            "token": access_token,
            "access_token": access_token,
            "token_type": "bearer",
            "client_name": user.full_name,
            "email": user.email
        }
        
    except ValueError as e:
        print(f"خطأ في التحقق من Google Token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="رمز Google غير صحيح"
        )
    except Exception as e:
        print(f"خطأ عام في Google Login: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="حدث خطأ في تسجيل الدخول بـ Google"
        )


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