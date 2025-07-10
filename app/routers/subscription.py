# app/routers/subscription.py
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from app.database import get_db
from app.models.user import User
from app.models.points import (
    UserPoints, PointPackage, UserSubscription, PointTransaction,
    TransactionType, PaymentStatus
)
from app.schemas.points import (
    SubscriptionResponse, SubscriptionCreateRequest,
    PointPackageResponse, PackagePurchaseResponse
)
from app.routers.auth import get_current_user
from app.services.points_service import PointsService
from app.services.payment_service import PaymentService
from app.services.email_service import email_service

# إعداد logging
logger = logging.getLogger(__name__)

# إنشاء router
router = APIRouter(prefix="/api/subscription", tags=["subscription"])
points_service = PointsService()
payment_service = PaymentService()

# ===== الاشتراك الحالي =====

@router.get("/current", response_model=Optional[SubscriptionResponse])
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """الحصول على الاشتراك النشط الحالي"""
    
    # حل خاص للمالك
    if current_user.email == "alimobarki.ad@gmail.com":
        return SubscriptionResponse(
            id=99999,
            package_id=3,
            package_name="الاحترافية - مالك الموقع",
            monthly_points=99999,
            billing_cycle="yearly",
            status="active",
            started_at=datetime.utcnow(),
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=3650),  # 10 سنوات
            next_billing_date=None,
            auto_renew=False
        )
    
    try:
        subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == "active"
        ).first()
        
        if not subscription:
            return None
        
        # جلب معلومات الباقة
        package = db.query(PointPackage).filter(
            PointPackage.id == subscription.package_id
        ).first()
        
        return SubscriptionResponse(
            id=subscription.id,
            package_id=subscription.package_id,
            package_name=package.name if package else "باقة غير معروفة",
            monthly_points=subscription.monthly_points,
            billing_cycle=subscription.billing_cycle,
            status=subscription.status,
            started_at=subscription.started_at,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            next_billing_date=subscription.next_billing_date,
            auto_renew=subscription.auto_renew
        )
        
    except Exception as e:
        logger.error(f"Error getting current subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب الاشتراك: {str(e)}")

# ===== باقات الاشتراك =====

@router.get("/packages", response_model=List[PointPackageResponse])
async def get_subscription_packages(
    db: Session = Depends(get_db)
):
    """الحصول على باقات الاشتراك المتاحة"""
    try:
        packages = db.query(PointPackage).filter(
            PointPackage.is_subscription == True,
            PointPackage.is_active == True
        ).order_by(PointPackage.sort_order, PointPackage.points).all()
        
        return packages
        
    except Exception as e:
        logger.error(f"Error getting subscription packages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب الباقات: {str(e)}")

# ===== إنشاء اشتراك جديد =====

@router.post("/create", response_model=PackagePurchaseResponse)
async def create_subscription(
    request: SubscriptionCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """إنشاء اشتراك جديد"""
    try:
        # التحقق من الباقة
        package = db.query(PointPackage).filter(
            PointPackage.id == request.package_id,
            PointPackage.is_subscription == True,
            PointPackage.is_active == True
        ).first()
        
        if not package:
            raise HTTPException(status_code=404, detail="باقة الاشتراك غير موجودة")
        
        # التحقق من وجود اشتراك نشط
        existing_subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == "active"
        ).first()
        
        if existing_subscription:
            raise HTTPException(
                status_code=400, 
                detail="لديك اشتراك نشط بالفعل. يجب إلغاء الاشتراك الحالي أولاً"
            )
        
        # حساب السعر حسب دورة الفوترة
        if request.billing_cycle == "yearly":
            # خصم 20% للاشتراك السنوي
            price = package.price * 12 * Decimal('0.8')
            months = 12
        else:
            price = package.price
            months = 1
        
        # معالجة كود الخصم إن وجد
        discount_amount = Decimal('0')
        if request.promo_code:
            # التحقق من كود الخصم
            pass  # سيتم تنفيذه لاحقاً
        
        # معالجة الدفع
        payment_result = await payment_service.process_payment(
            amount=float(price),
            payment_method=request.payment_method,
            payment_reference=f"SUB-{current_user.id}-{datetime.utcnow().timestamp()}",
            user_id=current_user.id,
            description=f"اشتراك {package.name} - {request.billing_cycle}"
        )
        
        if not payment_result['success']:
            raise HTTPException(status_code=400, detail=payment_result['message'])
        
        # إنشاء الاشتراك
        now = datetime.utcnow()
        if request.billing_cycle == "yearly":
            period_end = now + timedelta(days=365)
        else:
            period_end = now + timedelta(days=30)
        
        subscription = UserSubscription(
            user_id=current_user.id,
            package_id=package.id,
            monthly_points=package.points,
            billing_cycle=request.billing_cycle,
            status="active",
            started_at=now,
            current_period_start=now,
            current_period_end=period_end,
            next_billing_date=period_end if request.auto_renew else None,
            auto_renew=request.auto_renew,
            payment_method=request.payment_method,
            last_payment_date=now,
            last_payment_amount=price
        )
        db.add(subscription)
        
        # تحديث نقاط المستخدم
        user_points = points_service.get_or_create_user_points(db, current_user.id)
        user_points.monthly_points = package.points
        user_points.monthly_points_used = 0
        user_points.monthly_reset_date = period_end
        
        # إضافة النقاط الأولى للرصيد
        balance_before = user_points.balance
        user_points.balance += package.points
        
        # إنشاء معاملة
        transaction = PointTransaction(
            user_id=current_user.id,
            user_points_id=user_points.id,
            transaction_type=TransactionType.PURCHASE,
            amount=package.points,
            balance_before=balance_before,
            balance_after=user_points.balance,
            reference_type="subscription",
            reference_id=str(subscription.id),
            description=f"النقاط الشهرية من اشتراك {package.name}",
            payment_method=request.payment_method,
            payment_reference=payment_result['transaction_id']
        )
        db.add(transaction)
        
        db.commit()
        db.refresh(subscription)
        
        # إرسال إيميل تأكيد في الخلفية
        background_tasks.add_task(
            send_subscription_confirmation_email,
            current_user.email,
            current_user.full_name or current_user.email,
            package.name,
            package.points,
            request.billing_cycle,
            float(price)
        )
        
        return PackagePurchaseResponse(
            purchase_id=subscription.id,
            package_name=package.name,
            points_purchased=package.points * months,
            price_paid=price,
            new_balance=user_points.balance,
            payment_method=request.payment_method,
            status="completed",
            created_at=subscription.started_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating subscription: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في إنشاء الاشتراك: {str(e)}")

# ===== إدارة الاشتراك =====

@router.post("/cancel")
async def cancel_subscription(
    reason: Optional[str] = Query(None, description="سبب الإلغاء"),
    immediate: bool = Query(False, description="إلغاء فوري أم في نهاية الفترة"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """إلغاء الاشتراك الحالي"""
    try:
        subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == "active"
        ).first()
        
        if not subscription:
            raise HTTPException(status_code=404, detail="لا يوجد اشتراك نشط")
        
        if immediate:
            # إلغاء فوري
            subscription.status = "cancelled"
            subscription.cancelled_at = datetime.utcnow()
            subscription.auto_renew = False
            
            # إيقاف النقاط الشهرية
            user_points = db.query(UserPoints).filter(
                UserPoints.user_id == current_user.id
            ).first()
            if user_points:
                user_points.monthly_points = 0
                user_points.monthly_reset_date = None
        else:
            # إلغاء في نهاية الفترة
            subscription.auto_renew = False
            subscription.cancellation_reason = reason
        
        db.commit()
        
        return {
            "success": True,
            "message": "تم إلغاء الاشتراك بنجاح" if immediate else "سيتم إلغاء الاشتراك في نهاية الفترة الحالية",
            "effective_date": datetime.utcnow() if immediate else subscription.current_period_end
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling subscription: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في إلغاء الاشتراك: {str(e)}")

@router.post("/resume")
async def resume_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """استئناف الاشتراك الملغي"""
    try:
        subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == "active",
            UserSubscription.auto_renew == False
        ).first()
        
        if not subscription:
            raise HTTPException(status_code=404, detail="لا يوجد اشتراك ملغي")
        
        subscription.auto_renew = True
        subscription.cancellation_reason = None
        db.commit()
        
        return {
            "success": True,
            "message": "تم استئناف الاشتراك بنجاح",
            "next_billing_date": subscription.next_billing_date
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming subscription: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في استئناف الاشتراك: {str(e)}")

@router.put("/change-plan")
async def change_subscription_plan(
    new_package_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """تغيير خطة الاشتراك"""
    try:
        # التحقق من الاشتراك الحالي
        current_subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == "active"
        ).first()
        
        if not current_subscription:
            raise HTTPException(status_code=404, detail="لا يوجد اشتراك نشط")
        
        # التحقق من الباقة الجديدة
        new_package = db.query(PointPackage).filter(
            PointPackage.id == new_package_id,
            PointPackage.is_subscription == True,
            PointPackage.is_active == True
        ).first()
        
        if not new_package:
            raise HTTPException(status_code=404, detail="الباقة الجديدة غير موجودة")
        
        if new_package.id == current_subscription.package_id:
            raise HTTPException(status_code=400, detail="أنت مشترك في هذه الباقة بالفعل")
        
        # حساب الفرق في السعر (إن وجد)
        current_package = db.query(PointPackage).filter(
            PointPackage.id == current_subscription.package_id
        ).first()
        
        # تحديث الاشتراك
        current_subscription.package_id = new_package.id
        current_subscription.monthly_points = new_package.points
        current_subscription.updated_at = datetime.utcnow()
        
        # تحديث نقاط المستخدم
        user_points = db.query(UserPoints).filter(
            UserPoints.user_id == current_user.id
        ).first()
        
        if user_points:
            # حساب النقاط المتبقية من الباقة الحالية
            remaining_points = user_points.monthly_points - user_points.monthly_points_used
            
            # تحديث للباقة الجديدة
            user_points.monthly_points = new_package.points
            
            # إضافة الفرق إذا كانت الباقة الجديدة أكبر
            if new_package.points > current_package.points:
                points_diff = new_package.points - current_package.points
                user_points.balance += points_diff
                
                # إنشاء معاملة
                transaction = PointTransaction(
                    user_id=current_user.id,
                    user_points_id=user_points.id,
                    transaction_type=TransactionType.BONUS,
                    amount=points_diff,
                    balance_before=user_points.balance - points_diff,
                    balance_after=user_points.balance,
                    reference_type="subscription_upgrade",
                    reference_id=str(current_subscription.id),
                    description=f"ترقية الاشتراك من {current_package.name} إلى {new_package.name}"
                )
                db.add(transaction)
        
        db.commit()
        
        return {
            "success": True,
            "message": f"تم تغيير الاشتراك إلى {new_package.name}",
            "new_monthly_points": new_package.points,
            "effective_immediately": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing subscription plan: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في تغيير الخطة: {str(e)}")

# ===== معلومات الاشتراك =====

@router.get("/history")
async def get_subscription_history(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """الحصول على سجل الاشتراكات"""
    try:
        subscriptions = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id
        ).order_by(UserSubscription.created_at.desc()).limit(limit).all()
        
        history = []
        for sub in subscriptions:
            package = db.query(PointPackage).filter(
                PointPackage.id == sub.package_id
            ).first()
            
            history.append({
                "id": sub.id,
                "package_name": package.name if package else "باقة محذوفة",
                "monthly_points": sub.monthly_points,
                "billing_cycle": sub.billing_cycle,
                "status": sub.status,
                "started_at": sub.started_at,
                "ended_at": sub.cancelled_at,
                "total_months": (
                    (sub.cancelled_at or datetime.utcnow()) - sub.started_at
                ).days // 30 if sub.started_at else 0
            })
        
        return {
            "subscriptions": history,
            "total": len(history)
        }
        
    except Exception as e:
        logger.error(f"Error getting subscription history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب السجل: {str(e)}")

@router.get("/usage-stats")
async def get_subscription_usage_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """إحصائيات استخدام الاشتراك"""
    try:
        subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == "active"
        ).first()
        
        if not subscription:
            raise HTTPException(status_code=404, detail="لا يوجد اشتراك نشط")
        
        user_points = db.query(UserPoints).filter(
            UserPoints.user_id == current_user.id
        ).first()
        
        # حساب الإحصائيات
        days_in_period = (subscription.current_period_end - subscription.current_period_start).days
        days_passed = (datetime.utcnow() - subscription.current_period_start).days
        days_remaining = max(0, (subscription.current_period_end - datetime.utcnow()).days)
        
        # معدل الاستخدام
        if days_passed > 0:
            daily_usage_rate = user_points.monthly_points_used / days_passed
            expected_total_usage = daily_usage_rate * days_in_period
        else:
            daily_usage_rate = 0
            expected_total_usage = 0
        
        return {
            "subscription_id": subscription.id,
            "current_period": {
                "start": subscription.current_period_start,
                "end": subscription.current_period_end,
                "days_total": days_in_period,
                "days_passed": days_passed,
                "days_remaining": days_remaining
            },
            "points_usage": {
                "monthly_allowance": subscription.monthly_points,
                "used": user_points.monthly_points_used,
                "remaining": user_points.available_monthly_points,
                "usage_percentage": round(
                    (user_points.monthly_points_used / subscription.monthly_points * 100) 
                    if subscription.monthly_points > 0 else 0, 
                    2
                )
            },
            "usage_trends": {
                "daily_average": round(daily_usage_rate, 2),
                "expected_total": round(expected_total_usage, 2),
                "on_track": expected_total_usage <= subscription.monthly_points
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting usage stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب الإحصائيات: {str(e)}")

# ===== وظائف مساعدة =====

async def send_subscription_confirmation_email(
    email: str,
    name: str,
    package_name: str,
    monthly_points: int,
    billing_cycle: str,
    amount: float
):
    """إرسال إيميل تأكيد الاشتراك"""
    try:
        # هنا يتم استدعاء خدمة الإيميل
        logger.info(f"Sending subscription confirmation to {email}")
        # await email_service.send_subscription_confirmation(...)
    except Exception as e:
        logger.error(f"Error sending confirmation email: {str(e)}")

@router.get("/upcoming-renewals")
async def get_upcoming_renewals(
    days_ahead: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """الحصول على التجديدات القادمة"""
    try:
        cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)
        
        subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == "active",
            UserSubscription.auto_renew == True,
            UserSubscription.next_billing_date <= cutoff_date
        ).first()
        
        if not subscription:
            return {
                "has_upcoming_renewal": False,
                "message": "لا توجد تجديدات قادمة"
            }
        
        package = db.query(PointPackage).filter(
            PointPackage.id == subscription.package_id
        ).first()
        
        return {
            "has_upcoming_renewal": True,
            "renewal_date": subscription.next_billing_date,
            "days_until_renewal": (subscription.next_billing_date - datetime.utcnow()).days,
            "package_name": package.name if package else "باقة غير معروفة",
            "renewal_amount": package.price if package else 0,
            "billing_cycle": subscription.billing_cycle
        }
        
    except Exception as e:
        logger.error(f"Error getting upcoming renewals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب التجديدات: {str(e)}")