# app/schemas/user.py
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    """المخطط الأساسي للمستخدم"""
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    store_url: Optional[str] = None
    plan: Optional[str] = "free"

class UserRegister(UserBase):
    """مخطط تسجيل مستخدم جديد"""
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('كلمة المرور يجب أن تكون 6 أحرف على الأقل')
        return v
    
    @validator('store_url')
    def validate_store_url(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            return f"https://{v}"
        return v

class UserLogin(BaseModel):
    """مخطط تسجيل الدخول"""
    email: EmailStr
    password: str

class GoogleLoginRequest(BaseModel):
    """مخطط تسجيل الدخول بـ Google"""
    id_token: str

class UserResponse(UserBase):
    """مخطط عرض بيانات المستخدم"""
    id: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True   # ✅ تم التغيير من orm_mode إلى orm_mode = True

class UserUpdate(BaseModel):
    """مخطط تحديث بيانات المستخدم"""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    store_url: Optional[str] = None
    plan: Optional[str] = None
    
    @validator('store_url')
    def validate_store_url(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            return f"https://{v}"
        return v

class TokenResponse(BaseModel):
    """مخطط استجابة التوكن"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 دقيقة
    user: UserResponse

class PasswordChangeRequest(BaseModel):
    """مخطط تغيير كلمة المرور"""
    current_password: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 6:
            raise ValueError('كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل')
        return v