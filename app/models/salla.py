# ملف models/salla.py
# 📍 ضع هذا الملف في مجلد models (نفس مكان user.py)

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class SallaStore(Base):
    """جدول لحفظ متاجر سلة المربوطة"""
    __tablename__ = "salla_stores"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))  # ربط مع المستخدم
    
    # بيانات المتجر من سلة
    store_id = Column(String, unique=True, index=True)  # ID المتجر في سلة
    store_name = Column(String)  # اسم المتجر
    store_domain = Column(String)  # رابط المتجر
    store_plan = Column(String)  # خطة المتجر في سلة
    store_status = Column(String)  # حالة المتجر
    
    # OAuth tokens من سلة
    access_token = Column(Text)  # رمز الوصول
    refresh_token = Column(Text)  # رمز التحديث
    token_expires_at = Column(DateTime)  # تاريخ انتهاء الرمز
    
    # إعدادات التكامل
    auto_sync_enabled = Column(Boolean, default=True)  # تفعيل المزامنة التلقائية
    webhook_secret = Column(String)  # مفتاح الحماية للإشعارات
    last_sync_at = Column(DateTime)  # آخر مزامنة
    
    # تواريخ الإنشاء والتحديث
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    user = relationship("User", back_populates="salla_stores")
    products = relationship("SallaProduct", back_populates="store")


class SallaProduct(Base):
    """جدول لحفظ منتجات سلة"""
    __tablename__ = "salla_products"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("salla_stores.id"))  # ربط مع المتجر
    
    # بيانات المنتج من سلة
    salla_product_id = Column(String, index=True)  # ID المنتج في سلة
    name = Column(String)  # اسم المنتج
    description = Column(Text)  # وصف المنتج
    sku = Column(String)  # رمز المنتج
    url_slug = Column(String)  # رابط المنتج
    
    # بيانات السعر
    price_amount = Column(String)  # السعر
    price_currency = Column(String, default="SAR")  # العملة
    
    # بيانات التصنيف
    category_id = Column(String)  # ID التصنيف
    category_name = Column(String)  # اسم التصنيف
    
    # الصور
    images = Column(JSON)  # قائمة الصور
    
    # بيانات SEO
    seo_title = Column(String)  # عنوان SEO
    seo_description = Column(Text)  # وصف SEO
    
    # حالة المنتج
    status = Column(String)  # حالة (sale, out_of_stock, hidden)
    
    # بيانات المزامنة
    last_synced_at = Column(DateTime, default=datetime.utcnow)  # آخر مزامنة
    needs_update = Column(Boolean, default=False)  # يحتاج تحديث
    
    # تواريخ
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    store = relationship("SallaStore", back_populates="products")