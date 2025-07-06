# app/schemas/points.py
from pydantic import BaseModel, validator, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from decimal import Decimal

# Enums
class TransactionTypeEnum(str, Enum):
    PURCHASE = "purchase"
    DEDUCT = "deduct"
    REFUND = "refund"
    BONUS = "bonus"
    TRANSFER = "transfer"
    EXPIRED = "expired"
    ADMIN_CREDIT = "admin_credit"
    ADMIN_DEBIT = "admin_debit"

class PaymentStatusEnum(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

class ServiceTypeEnum(str, Enum):
    SEO_ANALYSIS = "seo_analysis"
    SEO_OPTIMIZATION = "seo_optimization"
    AI_DESCRIPTION = "ai_description"
    AI_DESCRIPTION_ADVANCED = "ai_description_advanced"
    KEYWORD_RESEARCH = "keyword_research"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    BULK_OPTIMIZATION = "bulk_optimization"
    AI_IMAGE_GENERATION = "ai_image_generation"
    STORE_SYNC = "store_sync"
    MONTHLY_REPORT = "monthly_report"

# Base Schemas
class PointsBalanceResponse(BaseModel):
    """استجابة رصيد النقاط"""
    balance: int
    monthly_points: int
    monthly_points_used: int
    available_monthly_points: int
    total_purchased: int
    total_spent: int
    monthly_reset_date: Optional[datetime]
    
    class Config:
        orm_mode = True

class PointPackageBase(BaseModel):
    """الأساس لباقات النقاط"""
    name: str
    name_en: Optional[str]
    description: Optional[str]
    points: int
    price: Decimal
    is_subscription: bool = False
    is_addon: bool = False
    features: Optional[List[str]] = []
    badge: Optional[str]
    color_gradient: Optional[str]

class PointPackageCreate(PointPackageBase):
    """إنشاء باقة نقاط"""
    is_popular: bool = False
    sort_order: int = 0

class PointPackageResponse(PointPackageBase):
    """استجابة باقة النقاط"""
    id: int
    is_active: bool
    is_popular: bool
    created_at: datetime
    
    class Config:
        orm_mode = True

class ServicePricingResponse(BaseModel):
    """استجابة تسعير الخدمة"""
    service_type: ServiceTypeEnum
    name: str
    name_en: Optional[str]
    description: Optional[str]
    point_cost: int
    category: Optional[str]
    is_active: bool
    
    class Config:
        orm_mode = True

class PointTransactionBase(BaseModel):
    """الأساس لمعاملة النقاط"""
    transaction_type: TransactionTypeEnum
    amount: int
    description: Optional[str]
    reference_type: Optional[str]
    reference_id: Optional[str]
    metadata: Optional[Dict[str, Any]]

class PointTransactionCreate(PointTransactionBase):
    """إنشاء معاملة نقاط"""
    service_type: Optional[ServiceTypeEnum]
    
    @validator('amount')
    def validate_amount(cls, v, values):
        if v == 0:
            raise ValueError('مبلغ المعاملة يجب أن يكون أكبر من صفر')
        return v

class PointTransactionResponse(PointTransactionBase):
    """استجابة معاملة النقاط"""
    id: int
    user_id: int
    balance_before: int
    balance_after: int
    created_at: datetime
    expires_at: Optional[datetime]
    
    class Config:
        orm_mode = True

class PurchasePointsRequest(BaseModel):
    """طلب شراء نقاط"""
    package_id: int
    payment_method: str = "credit_card"
    promo_code: Optional[str]
    
    @validator('payment_method')
    def validate_payment_method(cls, v):
        allowed_methods = ['credit_card', 'mada', 'apple_pay', 'stc_pay']
        if v not in allowed_methods:
            raise ValueError(f'طريقة الدفع يجب أن تكون من: {", ".join(allowed_methods)}')
        return v

class PurchasePointsResponse(BaseModel):
    """استجابة شراء النقاط"""
    purchase_id: int
    points: int
    price: Decimal
    vat_amount: Decimal
    total_amount: Decimal
    discount_amount: Decimal = Decimal('0')
    payment_url: Optional[str]  # رابط الدفع في Moyasar
    payment_reference: Optional[str]
    status: PaymentStatusEnum

class UsePointsRequest(BaseModel):
    """طلب استخدام النقاط"""
    service_type: ServiceTypeEnum
    metadata: Optional[Dict[str, Any]] = {}
    
    # للخدمات التي تحتاج معرفات
    product_id: Optional[int]
    store_id: Optional[int]
    
    @validator('metadata')
    def validate_metadata(cls, v):
        # التأكد من وجود البيانات المطلوبة حسب نوع الخدمة
        return v or {}

class UsePointsResponse(BaseModel):
    """استجابة استخدام النقاط"""
    success: bool
    transaction_id: int
    points_deducted: int
    new_balance: int
    service_details: Optional[Dict[str, Any]]

class PromoCodeValidateRequest(BaseModel):
    """طلب التحقق من كود الخصم"""
    code: str
    package_id: Optional[int]
    
    @validator('code')
    def validate_code(cls, v):
        if not v or len(v) < 3:
            raise ValueError('كود الخصم غير صحيح')
        return v.upper()

class PromoCodeValidateResponse(BaseModel):
    """استجابة التحقق من كود الخصم"""
    valid: bool
    discount_type: Optional[str]
    discount_value: Optional[Decimal]
    discount_amount: Optional[Decimal]
    message: Optional[str]

class SubscriptionCreateRequest(BaseModel):
    """طلب إنشاء اشتراك"""
    package_id: int
    billing_cycle: str = "monthly"
    auto_renew: bool = True
    promo_code: Optional[str]
    
    @validator('billing_cycle')
    def validate_billing_cycle(cls, v):
        if v not in ['monthly', 'yearly']:
            raise ValueError('دورة الفوترة يجب أن تكون شهرية أو سنوية')
        return v

class SubscriptionResponse(BaseModel):
    """استجابة الاشتراك"""
    id: int
    package_id: int
    package_name: str
    monthly_points: int
    billing_cycle: str
    status: str
    started_at: datetime
    current_period_start: datetime
    current_period_end: datetime
    next_billing_date: Optional[datetime]
    auto_renew: bool
    
    class Config:
        orm_mode = True

class PointsHistoryRequest(BaseModel):
    """طلب سجل النقاط"""
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)
    transaction_type: Optional[TransactionTypeEnum]
    date_from: Optional[datetime]
    date_to: Optional[datetime]

class PointsHistoryResponse(BaseModel):
    """استجابة سجل النقاط"""
    transactions: List[PointTransactionResponse]
    total: int
    page: int
    per_page: int
    pages: int

class PointsStatisticsResponse(BaseModel):
    """إحصائيات النقاط"""
    current_balance: int
    monthly_points_remaining: int
    total_earned: int  # كل النقاط المكتسبة
    total_spent: int   # كل النقاط المستهلكة
    
    # إحصائيات الشهر الحالي
    this_month_earned: int
    this_month_spent: int
    this_month_services: Dict[str, int]  # عدد استخدام كل خدمة
    
    # الخدمات الأكثر استخداماً
    top_services: List[Dict[str, Any]]
    
    # معدل الاستهلاك
    average_daily_usage: float
    expected_depletion_date: Optional[datetime]  # متى ستنفد النقاط

class ServiceUsageRequest(BaseModel):
    """طلب استخدام خدمة بالنقاط"""
    service_type: ServiceTypeEnum
    
    # بيانات حسب نوع الخدمة
    product_id: Optional[int]  # لخدمات المنتج
    product_ids: Optional[List[int]]  # للخدمات الجماعية
    store_id: Optional[int]  # لخدمات المتجر
    
    # خيارات إضافية
    options: Optional[Dict[str, Any]] = {}
    
    @validator('options')
    def validate_options(cls, v, values):
        service_type = values.get('service_type')
        
        # التحقق من الخيارات المطلوبة حسب نوع الخدمة
        if service_type == ServiceTypeEnum.AI_DESCRIPTION_ADVANCED:
            if not v.get('tone') or not v.get('audience'):
                raise ValueError('الجمهور المستهدف ونبرة الكتابة مطلوبة للوصف المتقدم')
        
        return v

class BatchServiceResponse(BaseModel):
    """استجابة الخدمات الجماعية"""
    success: bool
    processed_count: int
    failed_count: int
    points_used: int
    results: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]

# Dashboard Schemas
class PointsDashboardStats(BaseModel):
    """إحصائيات لوحة التحكم"""
    balance: PointsBalanceResponse
    statistics: PointsStatisticsResponse
    recent_transactions: List[PointTransactionResponse]
    available_packages: List[PointPackageResponse]
    active_subscription: Optional[SubscriptionResponse]

# Admin Schemas
class AdminAddPointsRequest(BaseModel):
    """طلب إضافة نقاط من الإدارة"""
    user_id: int
    amount: int = Field(..., gt=0)
    reason: str
    expires_after_days: Optional[int] = None

class AdminPointsReport(BaseModel):
    """تقرير النقاط للإدارة"""
    total_users: int
    total_points_in_system: int
    total_points_purchased: int
    total_points_spent: int
    total_revenue: Decimal
    
    # إحصائيات الفترة
    period_start: datetime
    period_end: datetime
    period_purchases: int
    period_revenue: Decimal
    period_points_spent: int
    
    # الخدمات الأكثر استخداماً
    top_services: List[Dict[str, Any]]
    
    # المستخدمين الأكثر نشاطاً
    top_users: List[Dict[str, Any]]