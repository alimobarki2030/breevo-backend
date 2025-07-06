# app/models/points.py
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey, Float, Enum, Numeric, Index, CheckConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
import enum

class TransactionType(enum.Enum):
    """أنواع معاملات النقاط"""
    PURCHASE = "purchase"      # شراء نقاط
    DEDUCT = "deduct"         # خصم نقاط
    REFUND = "refund"         # استرجاع نقاط
    BONUS = "bonus"           # نقاط مكافأة
    TRANSFER = "transfer"     # تحويل نقاط
    EXPIRED = "expired"       # نقاط منتهية
    ADMIN_CREDIT = "admin_credit"  # إضافة من الإدارة
    ADMIN_DEBIT = "admin_debit"    # خصم من الإدارة

class PaymentStatus(enum.Enum):
    """حالات الدفع"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

class ServiceType(enum.Enum):
    """أنواع الخدمات"""
    SEO_ANALYSIS = "seo_analysis"              # تحليل SEO أساسي (20 نقطة)
    SEO_OPTIMIZATION = "seo_optimization"        # تحليل SEO عميق (50 نقطة)
    AI_DESCRIPTION = "ai_description"            # توليد وصف بسيط (10 نقطة)
    AI_DESCRIPTION_ADVANCED = "ai_description_advanced"  # توليد وصف متقدم (30 نقطة)
    KEYWORD_RESEARCH = "keyword_research"        # تحليل كلمات مفتاحية (30 نقطة)
    COMPETITOR_ANALYSIS = "competitor_analysis"  # تحليل المنافسين (75 نقطة)
    BULK_OPTIMIZATION = "bulk_optimization"      # باقة كاملة (100 نقطة)
    AI_IMAGE_GENERATION = "ai_image_generation"  # توليد صور AI (150 نقطة)
    STORE_SYNC = "store_sync"                   # مزامنة متجر (50 نقطة)
    MONTHLY_REPORT = "monthly_report"           # تقرير شهري (100 نقطة)


class UserPoints(Base):
    """جدول رصيد النقاط للمستخدمين"""
    __tablename__ = "user_points"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # الرصيد
    balance = Column(Integer, default=0, nullable=False)  # الرصيد الحالي
    total_purchased = Column(Integer, default=0)  # إجمالي النقاط المشتراة
    total_spent = Column(Integer, default=0)      # إجمالي النقاط المستهلكة
    total_refunded = Column(Integer, default=0)   # إجمالي النقاط المسترجعة
    total_bonus = Column(Integer, default=0)      # إجمالي نقاط المكافآت
    
    # النقاط الشهرية من الباقة
    monthly_points = Column(Integer, default=0)   # النقاط الشهرية المستحقة
    monthly_points_used = Column(Integer, default=0)  # النقاط الشهرية المستخدمة
    monthly_reset_date = Column(DateTime)         # تاريخ تجديد النقاط الشهرية
    
    # تواريخ مهمة
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    user = relationship("User", back_populates="points")
    transactions = relationship("PointTransaction", back_populates="user_points", order_by="desc(PointTransaction.created_at)")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('balance >= 0', name='check_balance_non_negative'),
        Index('idx_user_points_user_id', 'user_id'),
    )
    
    @property
    def available_monthly_points(self):
        """النقاط الشهرية المتبقية"""
        return max(0, self.monthly_points - self.monthly_points_used)
    
    def has_sufficient_points(self, amount):
        """التحقق من توفر رصيد كافي"""
        return self.balance >= amount


class PointPackage(Base):
    """جدول باقات النقاط"""
    __tablename__ = "point_packages"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # معلومات الباقة
    name = Column(String, nullable=False)
    name_en = Column(String)  # الاسم بالإنجليزية
    description = Column(Text)
    points = Column(Integer, nullable=False)  # عدد النقاط
    price = Column(Numeric(10, 2), nullable=False)  # السعر بالريال
    
    # نوع الباقة
    is_subscription = Column(Boolean, default=False)  # هل هي اشتراك شهري
    is_addon = Column(Boolean, default=False)  # هل هي حزمة إضافية
    
    # الخصائص
    features = Column(JSON)  # قائمة المميزات
    badge = Column(String)  # شارة مميزة (الأكثر شعبية، وفر 20%)
    color_gradient = Column(String)  # تدرج الألوان للعرض
    
    # الحالة
    is_active = Column(Boolean, default=True)
    is_popular = Column(Boolean, default=False)  # الأكثر شعبية
    sort_order = Column(Integer, default=0)  # ترتيب العرض
    
    # التواريخ
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    purchases = relationship("PointPurchase", back_populates="package")


class PointTransaction(Base):
    """جدول معاملات النقاط"""
    __tablename__ = "point_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # المستخدم والنقاط
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_points_id = Column(Integer, ForeignKey("user_points.id"), nullable=False)
    
    # تفاصيل المعاملة
    transaction_type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Integer, nullable=False)  # القيمة (موجبة للإضافة، سالبة للخصم)
    balance_before = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    
    # مرجع المعاملة
    reference_type = Column(String)  # service, purchase, refund, admin
    reference_id = Column(String)    # معرف الخدمة أو الشراء
    
    # تفاصيل إضافية
    description = Column(Text)
    metadata = Column(JSON)  # معلومات إضافية (الخدمة، المنتج، إلخ)
    
    # معلومات الدفع (للشراء)
    payment_method = Column(String)
    payment_reference = Column(String)  # معرف moyasar
    
    # التواريخ
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # للنقاط التي لها صلاحية
    
    # العلاقات
    user = relationship("User")
    user_points = relationship("UserPoints", back_populates="transactions")
    
    # Indexes
    __table_args__ = (
        Index('idx_transactions_user_id', 'user_id'),
        Index('idx_transactions_type', 'transaction_type'),
        Index('idx_transactions_created_at', 'created_at'),
    )


class ServicePricing(Base):
    """جدول تسعير الخدمات بالنقاط"""
    __tablename__ = "service_pricing"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # الخدمة
    service_type = Column(Enum(ServiceType), unique=True, nullable=False)
    name = Column(String, nullable=False)
    name_en = Column(String)
    description = Column(Text)
    
    # التسعير
    point_cost = Column(Integer, nullable=False)
    
    # الفئة
    category = Column(String)  # seo, ai_generation, analysis, reports
    
    # الحالة
    is_active = Column(Boolean, default=True)
    
    # التواريخ
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PointPurchase(Base):
    """جدول مشتريات النقاط"""
    __tablename__ = "point_purchases"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # المستخدم والباقة
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    package_id = Column(Integer, ForeignKey("point_packages.id"), nullable=False)
    
    # تفاصيل الشراء
    points = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    vat_amount = Column(Numeric(10, 2))  # قيمة الضريبة
    total_amount = Column(Numeric(10, 2), nullable=False)  # المجموع مع الضريبة
    
    # الدفع
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    payment_method = Column(String)
    payment_reference = Column(String)  # معرف moyasar
    payment_data = Column(JSON)  # تفاصيل الدفع الكاملة
    
    # كود الخصم
    promo_code = Column(String)
    discount_amount = Column(Numeric(10, 2), default=0)
    
    # التواريخ
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime)
    refunded_at = Column(DateTime)
    
    # العلاقات
    user = relationship("User")
    package = relationship("PointPackage", back_populates="purchases")
    
    # Indexes
    __table_args__ = (
        Index('idx_purchases_user_id', 'user_id'),
        Index('idx_purchases_status', 'payment_status'),
        Index('idx_purchases_created_at', 'created_at'),
    )


class PromoCode(Base):
    """جدول أكواد الخصم"""
    __tablename__ = "promo_codes"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # الكود
    code = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text)
    
    # نوع وقيمة الخصم
    discount_type = Column(String)  # percentage, fixed
    discount_value = Column(Numeric(10, 2))  # النسبة أو المبلغ
    max_discount = Column(Numeric(10, 2))  # أقصى خصم (للنسبة المئوية)
    
    # القيود
    min_purchase = Column(Numeric(10, 2))  # أقل مبلغ للشراء
    max_uses = Column(Integer)  # أقصى عدد استخدامات
    max_uses_per_user = Column(Integer)  # أقصى استخدام لكل مستخدم
    
    # الباقات المسموحة
    allowed_packages = Column(JSON)  # قائمة IDs الباقات المسموحة
    
    # الصلاحية
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_until = Column(DateTime)
    
    # الإحصائيات
    times_used = Column(Integer, default=0)
    
    # الحالة
    is_active = Column(Boolean, default=True)
    
    # التواريخ
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def is_valid(self):
        """التحقق من صلاحية الكود"""
        now = datetime.utcnow()
        if not self.is_active:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_uses and self.times_used >= self.max_uses:
            return False
        return True


class UserSubscription(Base):
    """جدول اشتراكات المستخدمين"""
    __tablename__ = "user_subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # المستخدم والباقة
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    package_id = Column(Integer, ForeignKey("point_packages.id"), nullable=False)
    
    # تفاصيل الاشتراك
    monthly_points = Column(Integer, nullable=False)
    billing_cycle = Column(String)  # monthly, yearly
    
    # الحالة
    status = Column(String, default="active")  # active, paused, cancelled, expired
    
    # التواريخ
    started_at = Column(DateTime, default=datetime.utcnow)
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    cancelled_at = Column(DateTime)
    
    # الدفع التلقائي
    auto_renew = Column(Boolean, default=True)
    next_billing_date = Column(DateTime)
    
    # العلاقات
    user = relationship("User")
    package = relationship("PointPackage")
    
    # Indexes
    __table_args__ = (
        Index('idx_subscriptions_user_id', 'user_id'),
        Index('idx_subscriptions_status', 'status'),
    )