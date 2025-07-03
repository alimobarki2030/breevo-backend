# services/auth_service.py
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.config import settings
from app.models.user import User

class AuthService:
    """خدمة المصادقة المركزية"""
    
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    
    def hash_password(self, password: str) -> str:
        """تشفير كلمة المرور"""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """التحقق من كلمة المرور"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """إنشاء JWT token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> dict:
        """التحقق من صحة التوكن"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="التوكن غير صحيح",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def authenticate_user(self, db: Session, email: str, password: str) -> Optional[User]:
        """التحقق من بيانات المستخدم"""
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user
    
    def get_user_by_id(self, db: Session, user_id: int) -> Optional[User]:
        """جلب المستخدم بالـ ID"""
        return db.query(User).filter(User.id == user_id).first()
    
    def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        """جلب المستخدم بالإيميل"""
        return db.query(User).filter(User.email == email).first()
    
    def create_user(self, db: Session, user_data: dict) -> User:
        """إنشاء مستخدم جديد"""
        # التحقق من عدم وجود المستخدم
        if self.get_user_by_email(db, user_data["email"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="البريد الإلكتروني مستخدم بالفعل"
            )
        
        # تشفير كلمة المرور
        hashed_password = self.hash_password(user_data["password"])
        
        # إنشاء المستخدم
        user = User(
            full_name=user_data["full_name"],
            email=user_data["email"],
            hashed_password=hashed_password,
            phone=user_data.get("phone"),
            store_url=user_data.get("store_url"),
            plan=user_data.get("plan", "free")
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

# إنشاء instance من الخدمة
auth_service = AuthService()