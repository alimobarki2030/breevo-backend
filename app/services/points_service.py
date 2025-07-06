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
from app.schemas.points import (
    UsePointsRequest, UsePointsResponse,
    PurchasePointsRequest, PurchasePointsResponse,
    PromoCodeValidateRequest, PromoCodeValidateResponse,
    PointsBalanceResponse, PointTransactionResponse,
    ServiceUsageRequest
)
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

class PointsService:
    """خدمة إدارة نظام النقاط"""
    
    def __init__(self):
        # تكاليف الخدمات الافتراضية (يمكن تحديثها من قاعدة البيانات)
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
    
    # ==================== الوظائف الأساسية ====================
    
    def get_or_create_user_points(self, db: Session, user_id: int) -> UserPoints:
        """الحصول على رصيد المستخدم أو إنشاؤه"""
        user_points = db.query(UserPoints).filter(UserPoints.user_id == user_id).first()
        
        if not user_points:
            user_points = UserPoints(
                user_id=user_id,
                balance=0,
                monthly_points=0,
                monthly_points_used=0
            )
            db.add(user_points)
            db.commit()
            db.refresh(user_points)
            logger.info(f"Created new points balance for user {user_id}")
        
        return user_points
    
    def get_user_balance(self, db: Session, user_id: int) -> PointsBalanceResponse:
        """الحصول على رصيد المستخدم"""
        user_points = self.get_or_create_user_points(db, user_id)
        
        # التحقق من تجديد النقاط الشهرية
        self._check_monthly_points_reset(db, user_points)
        
        return PointsBalanceResponse(
            balance=user_points.balance,
            monthly_points=user_points.monthly_points,
            monthly_points_used=user_points.monthly_points_used,
            available_monthly_points=user_points.available_monthly_points,
            total_purchased=user_points.total_purchased,
            total_spent=user_points.total_spent,
            monthly_reset_date=user_points.monthly_reset_date
        )
    
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
    
    # ==================== استخدام النقاط ====================
    
    async def use_points(
        self, 
        db: Session, 
        user_id: int, 
        request: UsePointsRequest
    ) -> UsePointsResponse:
        """استخدام النقاط لخدمة معينة"""
        try:
            # الحصول على رصيد المستخدم
            user_points = self.get_or_create_user_points(db, user_id)
            
            # الحصول على تكلفة الخدمة
            point_cost = self.get_service_cost(db, request.service_type)
            
            # التحقق من توفر الرصيد
            if not user_points.has_sufficient_points(point_cost):
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=f"رصيد النقاط غير كافي. مطلوب {point_cost} نقطة، متوفر {user_points.balance} نقطة"
                )
            
            # خصم النقاط
            balance_before = user_points.balance
            user_points.balance -= point_cost
            user_points.total_spent += point_cost
            
            # خصم من النقاط الشهرية أولاً إن وجدت
            monthly_available = user_points.available_monthly_points
            if monthly_available > 0:
                monthly_deduction = min(point_cost, monthly_available)
                user_points.monthly_points_used += monthly_deduction
            
            # إنشاء معاملة
            transaction = PointTransaction(
                user_id=user_id,
                user_points_id=user_points.id,
                transaction_type=TransactionType.DEDUCT,
                amount=-point_cost,  # سالب للخصم
                balance_before=balance_before,
                balance_after=user_points.balance,
                reference_type="service",
                reference_id=request.service_type.value,
                description=f"استخدام خدمة: {self._get_service_name(request.service_type)}",
                metadata={
                    "service_type": request.service_type.value,
                    "product_id": request.product_id,
                    "store_id": request.store_id,
                    **request.metadata
                }
            )
            db.add(transaction)
            
            # تنفيذ الخدمة
            service_result = await self._execute_service(db, user_id, request)
            
            db.commit()
            
            logger.info(f"User {user_id} used {point_cost} points for {request.service_type.value}")
            
            return UsePointsResponse(
                success=True,
                transaction_id=transaction.id,
                points_deducted=point_cost,
                new_balance=user_points.balance,
                service_details=service_result
            )
            
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error using points: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"خطأ في استخدام النقاط: {str(e)}"
            )
    
    # ==================== شراء النقاط ====================
    
    async def purchase_points(
        self,
        db: Session,
        user_id: int,
        request: PurchasePointsRequest
    ) -> PurchasePointsResponse:
        """شراء باقة نقاط"""
        try:
            # الحصول على الباقة
            package = db.query(PointPackage).filter(
                PointPackage.id == request.package_id,
                PointPackage.is_active == True
            ).first()
            
            if not package:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="الباقة غير موجودة"
                )
            
            # التحقق من كود الخصم
            discount_amount = Decimal('0')
            if request.promo_code:
                promo_result = await self.validate_promo_code(
                    db,
                    PromoCodeValidateRequest(
                        code=request.promo_code,
                        package_id=package.id
                    )
                )
                if promo_result.valid:
                    discount_amount = promo_result.discount_amount or Decimal('0')
            
            # حساب المبالغ
            price = package.price
            discounted_price = price - discount_amount
            vat_amount = discounted_price * Decimal('0.15')  # 15% VAT
            total_amount = discounted_price + vat_amount
            
            # إنشاء طلب الشراء
            purchase = PointPurchase(
                user_id=user_id,
                package_id=package.id,
                points=package.points,
                price=price,
                vat_amount=vat_amount,
                total_amount=total_amount,
                discount_amount=discount_amount,
                payment_method=request.payment_method,
                promo_code=request.promo_code,
                payment_status=PaymentStatus.PENDING
            )
            db.add(purchase)
            db.commit()
            db.refresh(purchase)
            
            # إنشاء رابط الدفع (Moyasar)
            payment_url, payment_reference = await self._create_payment_link(
                purchase_id=purchase.id,
                amount=total_amount,
                description=f"شراء {package.points} نقطة - {package.name}"
            )
            
            # تحديث مرجع الدفع
            purchase.payment_reference = payment_reference
            db.commit()
            
            return PurchasePointsResponse(
                purchase_id=purchase.id,
                points=package.points,
                price=price,
                vat_amount=vat_amount,
                total_amount=total_amount,
                discount_amount=discount_amount,
                payment_url=payment_url,
                payment_reference=payment_reference,
                status=PaymentStatus.PENDING
            )
            
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error purchasing points: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"خطأ في شراء النقاط: {str(e)}"
            )
    
    async def confirm_purchase(
        self,
        db: Session,
        purchase_id: int,
        payment_status: str,
        payment_data: Optional[Dict] = None
    ) -> bool:
        """تأكيد عملية الشراء بعد الدفع"""
        try:
            purchase = db.query(PointPurchase).filter(
                PointPurchase.id == purchase_id
            ).first()
            
            if not purchase:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="عملية الشراء غير موجودة"
                )
            
            # تحديث حالة الدفع
            if payment_status == "paid":
                purchase.payment_status = PaymentStatus.COMPLETED
                purchase.paid_at = datetime.utcnow()
                
                if payment_data:
                    purchase.payment_data = payment_data
                
                # إضافة النقاط للمستخدم
                user_points = self.get_or_create_user_points(db, purchase.user_id)
                balance_before = user_points.balance
                user_points.balance += purchase.points
                user_points.total_purchased += purchase.points
                
                # إنشاء معاملة
                transaction = PointTransaction(
                    user_id=purchase.user_id,
                    user_points_id=user_points.id,
                    transaction_type=TransactionType.PURCHASE,
                    amount=purchase.points,
                    balance_before=balance_before,
                    balance_after=user_points.balance,
                    reference_type="purchase",
                    reference_id=str(purchase.id),
                    description=f"شراء {purchase.points} نقطة",
                    payment_method=purchase.payment_method,
                    payment_reference=purchase.payment_reference,
                    metadata={
                        "package_id": purchase.package_id,
                        "price": str(purchase.price),
                        "total_amount": str(purchase.total_amount)
                    }
                )
                db.add(transaction)
                
                # تحديث استخدام كود الخصم
                if purchase.promo_code:
                    promo = db.query(PromoCode).filter(
                        PromoCode.code == purchase.promo_code
                    ).first()
                    if promo:
                        promo.times_used += 1
                
                db.commit()
                logger.info(f"Purchase {purchase_id} confirmed, added {purchase.points} points to user {purchase.user_id}")
                return True
                
            else:
                purchase.payment_status = PaymentStatus.FAILED
                db.commit()
                return False
                
        except Exception as e:
            db.rollback()
            logger.error(f"Error confirming purchase: {str(e)}")
            raise
    
    # ==================== الاشتراكات ====================
    
    async def create_subscription(
        self,
        db: Session,
        user_id: int,
        package_id: int,
        billing_cycle: str = "monthly"
    ) -> UserSubscription:
        """إنشاء اشتراك شهري/سنوي"""
        try:
            # الحصول على الباقة
            package = db.query(PointPackage).filter(
                PointPackage.id == package_id,
                PointPackage.is_subscription == True,
                PointPackage.is_active == True
            ).first()
            
            if not package:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="باقة الاشتراك غير موجودة"
                )
            
            # إلغاء أي اشتراك سابق
            existing = db.query(UserSubscription).filter(
                UserSubscription.user_id == user_id,
                UserSubscription.status == "active"
            ).first()
            
            if existing:
                existing.status = "cancelled"
                existing.cancelled_at = datetime.utcnow()
            
            # حساب فترة الاشتراك
            now = datetime.utcnow()
            if billing_cycle == "yearly":
                period_end = now + timedelta(days=365)
                next_billing = period_end
            else:
                period_end = now + timedelta(days=30)
                next_billing = period_end
            
            # إنشاء الاشتراك
            subscription = UserSubscription(
                user_id=user_id,
                package_id=package_id,
                monthly_points=package.points,
                billing_cycle=billing_cycle,
                status="active",
                started_at=now,
                current_period_start=now,
                current_period_end=period_end,
                next_billing_date=next_billing,
                auto_renew=True
            )
            db.add(subscription)
            
            # تحديث النقاط الشهرية للمستخدم
            user_points = self.get_or_create_user_points(db, user_id)
            user_points.monthly_points = package.points
            user_points.monthly_points_used = 0
            user_points.monthly_reset_date = period_end
            
            db.commit()
            db.refresh(subscription)
            
            logger.info(f"Created {billing_cycle} subscription for user {user_id}")
            return subscription
            
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating subscription: {str(e)}")
            raise
    
    # ==================== أكواد الخصم ====================
    
    async def validate_promo_code(
        self,
        db: Session,
        request: PromoCodeValidateRequest
    ) -> PromoCodeValidateResponse:
        """التحقق من صحة كود الخصم"""
        try:
            promo = db.query(PromoCode).filter(
                PromoCode.code == request.code.upper()
            ).first()
            
            if not promo:
                return PromoCodeValidateResponse(
                    valid=False,
                    message="كود الخصم غير موجود"
                )
            
            # التحقق من الصلاحية
            if not promo.is_valid():
                return PromoCodeValidateResponse(
                    valid=False,
                    message="كود الخصم منتهي الصلاحية أو تم استخدامه بالحد الأقصى"
                )
            
            # التحقق من الباقة المسموحة
            if request.package_id and promo.allowed_packages:
                if request.package_id not in promo.allowed_packages:
                    return PromoCodeValidateResponse(
                        valid=False,
                        message="كود الخصم غير صالح لهذه الباقة"
                    )
            
            # حساب قيمة الخصم
            if request.package_id:
                package = db.query(PointPackage).filter(
                    PointPackage.id == request.package_id
                ).first()
                
                if package:
                    if promo.discount_type == "percentage":
                        discount_amount = package.price * (promo.discount_value / 100)
                        if promo.max_discount:
                            discount_amount = min(discount_amount, promo.max_discount)
                    else:
                        discount_amount = min(promo.discount_value, package.price)
                else:
                    discount_amount = None
            else:
                discount_amount = None
            
            return PromoCodeValidateResponse(
                valid=True,
                discount_type=promo.discount_type,
                discount_value=promo.discount_value,
                discount_amount=discount_amount,
                message="كود الخصم صالح"
            )
            
        except Exception as e:
            logger.error(f"Error validating promo code: {str(e)}")
            return PromoCodeValidateResponse(
                valid=False,
                message="خطأ في التحقق من كود الخصم"
            )
    
    # ==================== التقارير والإحصائيات ====================
    
    def get_user_transactions(
        self,
        db: Session,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        transaction_type: Optional[TransactionType] = None
    ) -> List[PointTransactionResponse]:
        """الحصول على سجل معاملات المستخدم"""
        query = db.query(PointTransaction).filter(
            PointTransaction.user_id == user_id
        )
        
        if transaction_type:
            query = query.filter(PointTransaction.transaction_type == transaction_type)
        
        transactions = query.order_by(
            PointTransaction.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        return [
            PointTransactionResponse.from_orm(t) for t in transactions
        ]
    
    def get_user_statistics(
        self,
        db: Session,
        user_id: int
    ) -> Dict[str, Any]:
        """إحصائيات استخدام النقاط للمستخدم"""
        user_points = self.get_or_create_user_points(db, user_id)
        
        # إحصائيات الشهر الحالي
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        
        month_transactions = db.query(PointTransaction).filter(
            PointTransaction.user_id == user_id,
            PointTransaction.created_at >= month_start
        ).all()
        
        month_earned = sum(t.amount for t in month_transactions if t.amount > 0)
        month_spent = abs(sum(t.amount for t in month_transactions if t.amount < 0))
        
        # الخدمات الأكثر استخداماً
        service_usage = db.query(
            PointTransaction.reference_id,
            func.count(PointTransaction.id).label('count'),
            func.sum(func.abs(PointTransaction.amount)).label('total_points')
        ).filter(
            PointTransaction.user_id == user_id,
            PointTransaction.transaction_type == TransactionType.DEDUCT,
            PointTransaction.reference_type == "service"
        ).group_by(
            PointTransaction.reference_id
        ).order_by(
            func.count(PointTransaction.id).desc()
        ).limit(5).all()
        
        # معدل الاستهلاك اليومي
        days_active = (datetime.utcnow() - user_points.created_at).days or 1
        avg_daily_usage = user_points.total_spent / days_active
        
        # توقع نفاد النقاط
        if avg_daily_usage > 0 and user_points.balance > 0:
            days_until_depletion = user_points.balance / avg_daily_usage
            expected_depletion = datetime.utcnow() + timedelta(days=int(days_until_depletion))
        else:
            expected_depletion = None
        
        return {
            "current_balance": user_points.balance,
            "monthly_points_remaining": user_points.available_monthly_points,
            "total_earned": user_points.total_purchased + user_points.total_bonus,
            "total_spent": user_points.total_spent,
            "this_month_earned": month_earned,
            "this_month_spent": month_spent,
            "top_services": [
                {
                    "service": s.reference_id,
                    "usage_count": s.count,
                    "total_points": s.total_points
                }
                for s in service_usage
            ],
            "average_daily_usage": round(avg_daily_usage, 2),
            "expected_depletion_date": expected_depletion
        }
    
    # ==================== وظائف مساعدة خاصة ====================
    
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
    
    async def _execute_service(
        self,
        db: Session,
        user_id: int,
        request: ServiceUsageRequest
    ) -> Dict[str, Any]:
        """تنفيذ الخدمة المطلوبة"""
        # هنا يتم استدعاء الخدمات الفعلية
        # مثل: AI Service, SEO Analysis, etc.
        
        service_type = request.service_type
        result = {"service": service_type.value}
        
        if service_type == ServiceType.AI_DESCRIPTION:
            # استدعاء خدمة توليد الوصف
            result["status"] = "completed"
            result["message"] = "تم توليد الوصف بنجاح"
            
        elif service_type == ServiceType.SEO_ANALYSIS:
            # استدعاء خدمة تحليل SEO
            result["status"] = "completed"
            result["message"] = "تم تحليل SEO بنجاح"
            
        # ... باقي الخدمات
        
        return result
    
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