# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import timedelta

from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserRegister, 
    UserLogin, 
    GoogleLoginRequest,
    UserResponse,
    TokenResponse,
    UserUpdate,
    PasswordChangeRequest
)
from app.services.auth_service import auth_service
from app.config import settings

# إنشاء router
router = APIRouter(prefix="/auth", tags=["authentication"])

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Dependency للحصول على المستخدم الحالي
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """الحصول على المستخدم الحالي من التوكن"""
    payload = auth_service.verify_token(token)
    user_id = payload.get("sub")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="بيانات التوكن غير صحيحة"
        )
    
    user = auth_service.get_user_by_id(db, int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="المستخدم غير موجود"
        )
    
    return user

@router.post("/register", response_model=TokenResponse)
def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    """تسجيل مستخدم جديد"""
    try:
        # إنشاء المستخدم
        user = auth_service.create_user(db, user_data.dict())
        
        # إنشاء التوكن
        access_token = auth_service.create_access_token(
            data={"sub": str(user.id)}
        )
        
        # تحديث آخر دخول
        auth_service.update_last_login(db, user)
        
        return TokenResponse(
            access_token=access_token,
            user=UserResponse.from_orm(user)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"حدث خطأ في التسجيل: {str(e)}"
        )

@router.post("/login", response_model=TokenResponse)
def login_user(user_data: UserLogin, db: Session = Depends(get_db)):
    """تسجيل دخول المستخدم"""
    try:
        # التحقق من بيانات المستخدم
        user = auth_service.authenticate_user(db, user_data.email, user_data.password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="البريد الإلكتروني أو كلمة المرور غير صحيحة"
            )
        
        # إنشاء التوكن
        access_token = auth_service.create_access_token(
            data={"sub": str(user.id)}
        )
        
        # تحديث آخر دخول
        auth_service.update_last_login(db, user)
        
        return TokenResponse(
            access_token=access_token,
            user=UserResponse.from_orm(user)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"حدث خطأ في تسجيل الدخول: {str(e)}"
        )

@router.post("/google-login", response_model=TokenResponse)
def google_login(request: GoogleLoginRequest, db: Session = Depends(get_db)):
    """تسجيل الدخول عبر Google"""
    try:
        # التحقق من Google token
        google_data = auth_service.verify_google_token(request.id_token)
        
        # تسجيل دخول أو إنشاء المستخدم
        user = auth_service.login_or_create_google_user(db, google_data)
        
        # إنشاء التوكن
        access_token = auth_service.create_access_token(
            data={"sub": str(user.id)}
        )
        
        return TokenResponse(
            access_token=access_token,
            user=UserResponse.from_orm(user)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"حدث خطأ في تسجيل الدخول بـ Google: {str(e)}"
        )

@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """الحصول على معلومات المستخدم الحالي"""
    return UserResponse.from_orm(current_user)

@router.get("/verify")
def verify_token(current_user: User = Depends(get_current_user)):
    """التحقق من صحة التوكن"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at
    }

@router.get("/check-email")
def check_email_exists(email: str, db: Session = Depends(get_db)):
    """التحقق من وجود البريد الإلكتروني"""
    user = auth_service.get_user_by_email(db, email)
    return {"exists": bool(user)}

@router.post("/logout")
def logout_user(current_user: User = Depends(get_current_user)):
    """تسجيل خروج المستخدم"""
    # في JWT، تسجيل الخروج يتم من جانب العميل بحذف التوكن
    return {"message": "تم تسجيل الخروج بنجاح"}