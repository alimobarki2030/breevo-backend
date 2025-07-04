# app/models/pending_store.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from app.database import Base
from datetime import datetime, timedelta
import uuid

class PendingStore(Base):
    """جدول للمتاجر المؤقتة في انتظار الربط بحساب مستخدم"""
    __tablename__ = "pending_stores"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # بيانات المتجر من سلة
    store_id = Column(String, unique=True, index=True)  # ID المتجر في سلة
    store_name = Column(String)  # اسم المتجر
    store_domain = Column(String)  # رابط المتجر  
    store_email = Column(String, index=True)  # إيميل المتجر
    store_phone = Column(String)  # جوال المتجر
    store_plan = Column(String)  # خطة المتجر في سلة
    store_status = Column(String)  # حالة المتجر
    
    # OAuth tokens من سلة
    access_token = Column(Text)  # رمز الوصول
    refresh_token = Column(Text)  # رمز التحديث
    token_expires_at = Column(DateTime)  # تاريخ انتهاء الرمز
    
    # نظام التحقق والربط
    verification_token = Column(String, unique=True, index=True)  # رمز التحقق للربط
    is_claimed = Column(Boolean, default=False)  # هل تم ربطه بحساب
    claimed_by_user_id = Column(Integer, nullable=True)  # ID المستخدم الذي ربطه
    claimed_at = Column(DateTime, nullable=True)  # تاريخ الربط
    
    # معلومات المنتجات
    products_count = Column(Integer, default=0)  # عدد المنتجات المكتشفة
    products_synced = Column(Boolean, default=False)  # هل تم مزامنة المنتجات
    
    # تتبع الإيميلات
    welcome_email_sent = Column(Boolean, default=False)  # هل تم إرسال إيميل الترحيب
    reminder_email_sent = Column(Boolean, default=False)  # هل تم إرسال إيميل التذكير
    last_email_sent_at = Column(DateTime, nullable=True)  # آخر إيميل مرسل
    
    # تواريخ مهمة
    created_at = Column(DateTime, default=datetime.utcnow)  # تاريخ التثبيت
    expires_at = Column(DateTime)  # تاريخ انتهاء الصلاحية (7 أيام)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # تعيين قيم افتراضية
        if not self.verification_token:
            self.verification_token = str(uuid.uuid4())
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(days=7)
    
    @property
    def is_expired(self) -> bool:
        """تحقق من انتهاء صلاحية الرابط"""
        return datetime.utcnow() > self.expires_at
    
    @property
    def days_remaining(self) -> int:
        """عدد الأيام المتبقية قبل انتهاء الصلاحية"""
        if self.is_expired:
            return 0
        diff = self.expires_at - datetime.utcnow()
        return max(0, diff.days)
    
    @property
    def should_send_reminder(self) -> bool:
        """هل يجب إرسال إيميل تذكير؟"""
        if self.is_claimed or self.reminder_email_sent or self.is_expired:
            return False
        
        # إرسال تذكير بعد 24 ساعة من الترحيب
        if self.welcome_email_sent and self.last_email_sent_at:
            time_since_last = datetime.utcnow() - self.last_email_sent_at
            return time_since_last.total_seconds() > 24 * 3600  # 24 ساعة
        
        return False
    
    def to_dict(self) -> dict:
        """تحويل لـ dictionary للاستخدام في API"""
        return {
            'id': self.id,
            'store_id': self.store_id,
            'store_name': self.store_name,
            'store_domain': self.store_domain,
            'store_email': self.store_email,
            'store_phone': self.store_phone,
            'store_plan': self.store_plan,
            'store_status': self.store_status,
            'products_count': self.products_count,
            'is_claimed': self.is_claimed,
            'is_expired': self.is_expired,
            'days_remaining': self.days_remaining,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }