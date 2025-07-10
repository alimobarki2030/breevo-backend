# app/services/points_service.py
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from app.models.points import (
    UserPoints, PointTransaction, PointPackage, 
    ServicePricing, PointPurchase, PromoCode,
    UserSubscription, TransactionType, PaymentStatus, ServiceType
)
from app.models.user import User
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

class PointsService:
    """خدمة إدارة نظام النقاط"""
    
    def __init__(self, db: Session = None):
        self.db = db
        # تكاليف الخدمات الافتراضية
        self.service_costs = {
            ServiceType.SEO_ANALYSIS: 20,
            ServiceType.SEO_OPTIMIZATION: 50,
            ServiceType.AI_DESCRIPTION: 10,
            ServiceType.AI_DESCRIPTION_ADVANCED: 30,
            ServiceType.KEYWORD_RESEARCH: 30,
            ServiceType.COMPETITOR_ANALYSIS: 75,
            ServiceType.BULK_OPTIMIZATION: 100,
            ServiceType.AI_IMAGE_GENERATION: 150,
            ServiceType.STORE_SYNC: 50,
            ServiceType.MONTHLY_REPORT: 100,
        }
    
    def set_db(self, db: Session):
        """تعيين جلسة قاعدة البيانات"""
        self.db = db
    
    def get_or_create_user_points(self, db: Session, user_id: int) -> UserPoints:
        """الحصول على رصيد المستخدم أو إنشاؤه"""
        user_points = db.query(UserPoints).filter(UserPoints.user_id == user_id).first()
        
        if not user_points:
            user_points = UserPoints(
                user_id=user_id,
                balance=0,
                monthly_points=0,
                monthly_points_used=0,
                total_purchased=0,
                total_spent=0,
                total_refunded=0,
                total_bonus=0
            )
            db.add(user_points)
            db.commit()
            db.refresh(user_points)
            logger.info(f"Created new points balance for user {user_id}")
        
        return user_points
    
    def get_user_balance(self, db: Session, user_id: int) -> Dict[str, Any]:
        """الحصول على رصيد المستخدم"""
        user_points = self.get_or_create_user_points(db, user_id)
        
        # التحقق من تجديد النقاط الشهرية
        self._check_monthly_points_reset(db, user_points)
        
        return {
            "balance": user_points.balance,
            "monthly_points": user_points.monthly_points,
            "monthly_points_used": user_points.monthly_points_used,
            "available_monthly_points": user_points.available_monthly_points,
            "total_purchased": user_points.total_purchased,
            "total_spent": user_points.total_spent,
            "total_refunded": user_points.total_refunded,
            "monthly_reset_date": user_points.monthly_reset_date.isoformat() if user_points.monthly_reset_date else None
        }
    
    def get_service_cost(self, db: Session, service_type: ServiceType) -> int:
        """الحصول على تكلفة الخدمة بالنقاط"""
        # البحث في قاعدة البيانات أولاً
        pricing = db.query(ServicePricing).filter(
            ServicePricing.service_type == service_type,
            ServicePricing.is_active == True
        ).first()
        
        if pricing:
            return pricing.point_cost
        
        # استخدام القيم الافتراضية
        return self.service_costs.get(service_type, 50)
    
    def _check_monthly_points_reset(self, db: Session, user_points: UserPoints):
        """التحقق من تجديد النقاط الشهرية"""
        if user_points.monthly_reset_date and datetime.utcnow() >= user_points.monthly_reset_date:
            # إعادة تعيين النقاط الشهرية
            user_points.monthly_points_used = 0
            
            # حساب تاريخ التجديد التالي
            user_points.monthly_reset_date = user_points.monthly_reset_date + timedelta(days=30)
            
            # إضافة النقاط الشهرية للرصيد إذا كان لديه اشتراك نشط
            subscription = db.query(UserSubscription).filter(
                UserSubscription.user_id == user_points.user_id,
                UserSubscription.status == "active"
            ).first()
            
            if subscription:
                balance_before = user_points.balance
                user_points.balance += subscription.monthly_points
                
                # إنشاء معاملة
                transaction = PointTransaction(
                    user_id=user_points.user_id,
                    user_points_id=user_points.id,
                    transaction_type=TransactionType.BONUS,
                    amount=subscription.monthly_points,
                    balance_before=balance_before,
                    balance_after=user_points.balance,
                    reference_type="subscription",
                    reference_id=str(subscription.id),
                    description="النقاط الشهرية من الاشتراك"
                )
                db.add(transaction)
            
            db.commit()
    
    def _get_service_name(self, service_type: ServiceType) -> str:
        """الحصول على اسم الخدمة"""
        service_names = {
            ServiceType.SEO_ANALYSIS: "تحليل SEO أساسي",
            ServiceType.SEO_OPTIMIZATION: "تحليل SEO عميق",
            ServiceType.AI_DESCRIPTION: "توليد وصف بسيط",
            ServiceType.AI_DESCRIPTION_ADVANCED: "توليد وصف متقدم",
            ServiceType.KEYWORD_RESEARCH: "تحليل الكلمات المفتاحية",
            ServiceType.COMPETITOR_ANALYSIS: "تحليل المنافسين",
            ServiceType.BULK_OPTIMIZATION: "باقة كاملة",
            ServiceType.AI_IMAGE_GENERATION: "توليد صور AI",
            ServiceType.STORE_SYNC: "مزامنة المتجر",
            ServiceType.MONTHLY_REPORT: "تقرير شهري"
        }
        return service_names.get(service_type, service_type.value)
    
    async def _create_payment_link(
        self,
        purchase_id: int,
        amount: Decimal,
        description: str
    ) -> tuple[str, str]:
        """إنشاء رابط دفع Moyasar"""
        # هنا يتم التكامل مع Moyasar API
        # مؤقتاً نرجع قيم تجريبية
        payment_reference = f"PAY-{purchase_id}-{datetime.utcnow().timestamp()}"
        payment_url = f"https://checkout.moyasar.com/pay/{payment_reference}"
        
        return payment_url, payment_reference

# إنشاء instance من الخدمة
points_service = PointsService()