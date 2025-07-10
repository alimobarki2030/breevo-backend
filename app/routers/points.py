# app/routers/points.py
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from app.database import get_db
from app.models.user import User
from app.models.points import (
    UserPoints, PointPackage, PointTransaction, ServicePricing,
    PointPurchase, TransactionType, ServiceType
)
from app.schemas.points import (
    PointsBalanceResponse,
    PointPackageResponse, PointPackagesListResponse,
    TransactionResponse, TransactionsListRequest, TransactionsListResponse,
    ServicePricingResponse, ServicesListResponse,
    PackagePurchaseRequest, PackagePurchaseResponse,
    ServiceUsageRequest,
    PointsAnalyticsRequest, PointsAnalyticsResponse,
    CheckBalanceRequest, CheckBalanceResponse,
    BulkServiceRequest, BulkServiceResponse
)
from app.routers.auth import get_current_user
from app.services.points_service import PointsService
from app.services.payment_service import PaymentService

# إعداد logging
logger = logging.getLogger(__name__)

# إنشاء router
router = APIRouter(prefix="/api/points", tags=["points"])

# ===== رصيد النقاط =====

@router.get("/balance", response_model=PointsBalanceResponse)
async def get_points_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """الحصول على رصيد النقاط للمستخدم"""
    
    # حل خاص للمالك
    if current_user.email == "alimobarki.ad@gmail.com":
        return PointsBalanceResponse(
            balance=99999,
            total_purchased=99999,
            total_spent=0,
            total_refunded=0,
            monthly_points=99999,
            monthly_points_used=0,
            available_monthly_points=99999,
            monthly_reset_date=datetime.utcnow() + timedelta(days=3650)  # 10 سنوات
        )
    
    points_service = PointsService(db)
    
    try:
        # الحصول على حساب النقاط أو إنشاؤه
        user_points = points_service.get_or_create_user_points(current_user.id)
        
        return PointsBalanceResponse(
            balance=user_points.balance,
            total_purchased=user_points.total_purchased,
            total_spent=user_points.total_spent,
            total_refunded=user_points.total_refunded,
            monthly_points=user_points.monthly_points,
            monthly_points_used=user_points.monthly_points_used,
            available_monthly_points=user_points.available_monthly_points,
            monthly_reset_date=user_points.monthly_reset_date
        )
        
    except Exception as e:
        logger.error(f"Error getting points balance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب رصيد النقاط: {str(e)}")

@router.get("/check-balance", response_model=CheckBalanceResponse)
async def check_balance_for_service(
    service_type: ServiceType = Query(..., description="نوع الخدمة"),
    quantity: int = Query(1, ge=1, description="الكمية"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """التحقق من توفر رصيد كافي لخدمة معينة"""
    points_service = PointsService(db)
    
    try:
        # الحصول على تسعير الخدمة
        service_pricing = db.query(ServicePricing).filter(
            ServicePricing.service_type == service_type,
            ServicePricing.is_active == True
        ).first()
        
        if not service_pricing:
            raise HTTPException(status_code=404, detail="الخدمة غير موجودة")
        
        user_points = points_service.get_or_create_user_points(current_user.id)
        required_points = service_pricing.point_cost * quantity
        has_sufficient = user_points.balance >= required_points
        shortage = max(0, required_points - user_points.balance) if not has_sufficient else None
        
        # اقتراح باقة مناسبة إذا كان الرصيد غير كافي
        suggested_package = None
        if shortage:
            suggested_package = db.query(PointPackage).filter(
                PointPackage.points >= shortage,
                PointPackage.is_active == True
            ).order_by(PointPackage.points.asc()).first()
        
        return CheckBalanceResponse(
            current_balance=user_points.balance,
            required_points=required_points,
            has_sufficient_balance=has_sufficient,
            shortage=shortage,
            suggested_package=suggested_package
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking balance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في التحقق من الرصيد: {str(e)}")

# ===== باقات النقاط =====

@router.get("/packages", response_model=PointPackagesListResponse)
async def get_point_packages(
    only_active: bool = Query(True, description="عرض الباقات النشطة فقط"),
    db: Session = Depends(get_db)
):
    """الحصول على قائمة باقات النقاط المتاحة"""
    try:
        query = db.query(PointPackage)
        
        if only_active:
            query = query.filter(PointPackage.is_active == True)
        
        packages = query.order_by(PointPackage.sort_order, PointPackage.points).all()
        
        return PointPackagesListResponse(
            packages=packages,
            count=len(packages)
        )
        
    except Exception as e:
        logger.error(f"Error getting packages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب الباقات: {str(e)}")

@router.post("/packages/purchase", response_model=PackagePurchaseResponse)
async def purchase_point_package(
    request: PackagePurchaseRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """شراء باقة نقاط"""
    points_service = PointsService(db)
    payment_service = PaymentService()
    
    try:
        # التحقق من الباقة
        package = db.query(PointPackage).filter(
            PointPackage.id == request.package_id,
            PointPackage.is_active == True
        ).first()
        
        if not package:
            raise HTTPException(status_code=404, detail="الباقة غير موجودة")
        
        # معالجة الدفع
        payment_result = await payment_service.process_payment(
            amount=float(package.price),
            payment_method=request.payment_method,
            payment_reference=request.payment_reference,
            user_id=current_user.id,
            description=f"شراء باقة {package.name} - {package.points} نقطة"
        )
        
        if not payment_result['success']:
            raise HTTPException(status_code=400, detail=payment_result['message'])
        
        # إضافة النقاط
        user_points = points_service.get_or_create_user_points(current_user.id)
        balance_before = user_points.balance
        user_points.balance += package.points
        user_points.total_purchased += package.points
        
        # إنشاء معاملة
        transaction = PointTransaction(
            user_id=current_user.id,
            user_points_id=user_points.id,
            transaction_type=TransactionType.PURCHASE,
            amount=package.points,
            balance_before=balance_before,
            balance_after=user_points.balance,
            description=f"شراء باقة {package.name}",
            reference_type="package",
            reference_id=str(package.id),
            payment_method=request.payment_method,
            payment_reference=payment_result['transaction_id']
        )
        db.add(transaction)
        
        # تسجيل عملية الشراء
        purchase = PointPurchase(
            user_id=current_user.id,
            package_id=package.id,
            points=package.points,
            price=package.price,
            vat_amount=package.price * Decimal('0.15'),
            total_amount=package.price * Decimal('1.15'),
            payment_method=request.payment_method,
            payment_reference=payment_result['transaction_id'],
            payment_status="completed",
            paid_at=datetime.utcnow()
        )
        db.add(purchase)
        db.commit()
        
        # إرسال إيميل تأكيد (في الخلفية)
        background_tasks.add_task(
            send_purchase_confirmation_email,
            current_user.email,
            package.name,
            package.points,
            float(package.price)
        )
        
        return PackagePurchaseResponse(
            purchase_id=purchase.id,
            package_name=package.name,
            points_purchased=package.points,
            price_paid=package.price,
            new_balance=user_points.balance,
            payment_method=request.payment_method,
            status="completed",
            created_at=purchase.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error purchasing package: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في شراء الباقة: {str(e)}")

# ===== المعاملات =====

@router.get("/transactions", response_model=TransactionsListResponse)
async def get_transactions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    type: Optional[TransactionType] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """الحصول على سجل معاملات النقاط"""
    try:
        query = db.query(PointTransaction).filter(
            PointTransaction.user_id == current_user.id
        )
        
        # تطبيق الفلاتر
        if type:
            query = query.filter(PointTransaction.transaction_type == type)
        
        if start_date:
            query = query.filter(PointTransaction.created_at >= start_date)
        
        if end_date:
            query = query.filter(PointTransaction.created_at <= end_date)
        
        # العد الإجمالي
        total = query.count()
        
        # التقسيم
        transactions = query.order_by(PointTransaction.created_at.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        
        return TransactionsListResponse(
            transactions=transactions,
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page
        )
        
    except Exception as e:
        logger.error(f"Error getting transactions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب المعاملات: {str(e)}")

# ===== الخدمات =====

@router.get("/services", response_model=ServicesListResponse)
async def get_services_pricing(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """الحصول على قائمة أسعار الخدمات"""
    try:
        query = db.query(ServicePricing).filter(
            ServicePricing.is_active == True
        )
        
        if category:
            query = query.filter(ServicePricing.category == category)
        
        services = query.order_by(ServicePricing.point_cost).all()
        
        # جمع الفئات الفريدة
        categories = db.query(ServicePricing.category).filter(
            ServicePricing.is_active == True,
            ServicePricing.category.isnot(None)
        ).distinct().all()
        
        return ServicesListResponse(
            services=services,
            categories=[cat[0] for cat in categories if cat[0]]
        )
        
    except Exception as e:
        logger.error(f"Error getting services: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب الخدمات: {str(e)}")

@router.post("/services/use")
async def use_service(
    request: ServiceUsageRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """استخدام خدمة (خصم نقاط)"""
    points_service = PointsService(db)
    
    try:
        # التحقق من الخدمة
        service = db.query(ServicePricing).filter(
            ServicePricing.service_type == request.service_type,
            ServicePricing.is_active == True
        ).first()
        
        if not service:
            raise HTTPException(status_code=404, detail="الخدمة غير موجودة")
        
        # التحقق من الرصيد
        user_points = points_service.get_or_create_user_points(current_user.id)
        
        if user_points.balance < service.point_cost:
            raise HTTPException(
                status_code=400, 
                detail=f"رصيد غير كافي. المطلوب: {service.point_cost} نقطة، المتوفر: {user_points.balance} نقطة"
            )
        
        # خصم النقاط
        balance_before = user_points.balance
        user_points.balance -= service.point_cost
        user_points.total_spent += service.point_cost
        
        # إنشاء معاملة
        transaction = PointTransaction(
            user_id=current_user.id,
            user_points_id=user_points.id,
            transaction_type=TransactionType.DEDUCT,
            amount=-service.point_cost,
            balance_before=balance_before,
            balance_after=user_points.balance,
            description=f"استخدام خدمة: {service.name}",
            reference_type="service",
            reference_id=str(service.id),
            meta_data={
                "service_type": request.service_type.value,
                "product_id": request.product_id,
                "store_id": request.store_id,
                "options": request.options
            }
        )
        db.add(transaction)
        db.commit()
        
        # تنفيذ الخدمة في الخلفية
        background_tasks.add_task(
            execute_service_task,
            current_user.id,
            request.service_type,
            request.options,
            transaction.id
        )
        
        return {
            "success": True,
            "transaction_id": transaction.id,
            "service_type": request.service_type,
            "service_name": service.name,
            "points_spent": service.point_cost,
            "new_balance": user_points.balance,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error using service: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في استخدام الخدمة: {str(e)}")

# ===== التحليلات =====

@router.get("/analytics")
async def get_points_analytics(
    period: str = Query("month", regex="^(week|month|year|all)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """الحصول على تحليلات استخدام النقاط"""
    try:
        user_points = db.query(UserPoints).filter(
            UserPoints.user_id == current_user.id
        ).first()
        
        if not user_points:
            # إرجاع تحليلات فارغة
            return {
                "total_purchased": 0,
                "total_spent": 0,
                "total_refunded": 0,
                "current_balance": 0,
                "usage_by_service": {},
                "usage_by_month": [],
                "top_services": [],
                "average_daily_usage": 0,
                "average_monthly_usage": 0,
                "period": period
            }
        
        # تحديد الفترة الزمنية
        if not end_date:
            end_date = datetime.utcnow()
        
        if not start_date:
            if period == "week":
                start_date = end_date - timedelta(days=7)
            elif period == "month":
                start_date = end_date - timedelta(days=30)
            elif period == "year":
                start_date = end_date - timedelta(days=365)
            else:  # all
                start_date = user_points.created_at
        
        # جلب المعاملات في الفترة
        transactions = db.query(PointTransaction).filter(
            PointTransaction.user_id == current_user.id,
            PointTransaction.created_at >= start_date,
            PointTransaction.created_at <= end_date
        ).all()
        
        # حساب الإحصائيات
        usage_by_service = {}
        for transaction in transactions:
            if transaction.transaction_type == TransactionType.DEDUCT and transaction.reference_type == "service":
                service_name = transaction.description.replace("استخدام خدمة: ", "")
                if service_name not in usage_by_service:
                    usage_by_service[service_name] = {
                        "count": 0,
                        "total_points": 0
                    }
                usage_by_service[service_name]["count"] += 1
                usage_by_service[service_name]["total_points"] += abs(transaction.amount)
        
        # أكثر الخدمات استخداماً
        top_services = sorted(
            [{"service": k, "count": v["count"], "points": v["total_points"]} 
             for k, v in usage_by_service.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:5]
        
        # معدل الاستخدام
        days = max(1, (end_date - start_date).days)
        total_spent_period = sum(abs(t.amount) for t in transactions if t.amount < 0)
        
        return {
            "total_purchased": user_points.total_purchased,
            "total_spent": user_points.total_spent,
            "total_refunded": user_points.total_refunded,
            "current_balance": user_points.balance,
            "usage_by_service": usage_by_service,
            "top_services": top_services,
            "average_daily_usage": round(total_spent_period / days, 2),
            "average_monthly_usage": round(total_spent_period / days * 30, 2),
            "period": period,
            "start_date": start_date,
            "end_date": end_date
        }
        
    except Exception as e:
        logger.error(f"Error getting analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب التحليلات: {str(e)}")

# ===== العمليات الجماعية =====

@router.post("/services/bulk")
async def use_service_bulk(
    request: BulkServiceRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """استخدام خدمة على عدة منتجات"""
    points_service = PointsService(db)
    
    try:
        # التحقق من الخدمة
        service = db.query(ServicePricing).filter(
            ServicePricing.service_type == request.service_type,
            ServicePricing.is_active == True
        ).first()
        
        if not service:
            raise HTTPException(status_code=404, detail="الخدمة غير موجودة")
        
        # حساب التكلفة الإجمالية
        total_products = len(request.product_ids)
        total_cost = service.point_cost * total_products
        
        # التحقق من الرصيد
        user_points = points_service.get_or_create_user_points(current_user.id)
        
        if user_points.balance < total_cost:
            raise HTTPException(
                status_code=400,
                detail=f"رصيد غير كافي. المطلوب: {total_cost} نقطة، المتوفر: {user_points.balance} نقطة"
            )
        
        # خصم النقاط
        balance_before = user_points.balance
        user_points.balance -= total_cost
        user_points.total_spent += total_cost
        
        # إنشاء معاملة
        transaction = PointTransaction(
            user_id=current_user.id,
            user_points_id=user_points.id,
            transaction_type=TransactionType.DEDUCT,
            amount=-total_cost,
            balance_before=balance_before,
            balance_after=user_points.balance,
            description=f"استخدام خدمة {service.name} على {total_products} منتج",
            reference_type="bulk_service",
            reference_id=str(service.id),
            meta_data={
                "product_ids": request.product_ids,
                "total_products": total_products
            }
        )
        db.add(transaction)
        db.commit()
        
        # تنفيذ الخدمات في الخلفية
        results = []
        for product_id in request.product_ids:
            results.append({
                "product_id": product_id,
                "status": "pending"
            })
        
        background_tasks.add_task(
            execute_bulk_service_task,
            current_user.id,
            request.service_type,
            request.product_ids,
            request.options,
            transaction.id
        )
        
        return {
            "success": True,
            "total_products": total_products,
            "total_points": total_cost,
            "processed": 0,
            "failed": 0,
            "results": results,
            "new_balance": user_points.balance
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk service: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في الخدمة الجماعية: {str(e)}")

# ===== نقاط المكافأة =====

@router.post("/bonus")
async def add_bonus_points(
    amount: int = Query(..., gt=0, description="عدد النقاط"),
    reason: str = Query(..., description="سبب المكافأة"),
    user_id: Optional[int] = Query(None, description="معرف المستخدم (للأدمن فقط)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """إضافة نقاط مكافأة (للأدمن فقط)"""
    # التحقق من صلاحيات الأدمن
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="غير مصرح بهذه العملية")
    
    points_service = PointsService(db)
    
    try:
        # تحديد المستخدم المستهدف
        target_user_id = user_id or current_user.id
        
        # إضافة النقاط
        user_points = points_service.get_or_create_user_points(target_user_id)
        balance_before = user_points.balance
        user_points.balance += amount
        user_points.total_bonus = (user_points.total_bonus or 0) + amount
        
        # إنشاء معاملة
        transaction = PointTransaction(
            user_id=target_user_id,
            user_points_id=user_points.id,
            transaction_type=TransactionType.BONUS,
            amount=amount,
            balance_before=balance_before,
            balance_after=user_points.balance,
            description=f"مكافأة: {reason}",
            reference_type="admin_bonus"
        )
        db.add(transaction)
        db.commit()
        
        return {
            "success": True,
            "message": f"تم إضافة {amount} نقطة بنجاح",
            "new_balance": user_points.balance
        }
        
    except Exception as e:
        logger.error(f"Error adding bonus points: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في إضافة النقاط: {str(e)}")

# ===== مهام الخلفية =====

async def send_purchase_confirmation_email(email: str, package_name: str, points: int, price: float):
    """إرسال إيميل تأكيد الشراء"""
    try:
        # هنا يتم إرسال الإيميل
        logger.info(f"Sending purchase confirmation to {email}")
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")

async def execute_service_task(user_id: int, service_type: ServiceType, options: dict, transaction_id: int):
    """تنفيذ الخدمة في الخلفية"""
    try:
        # هنا يتم تنفيذ الخدمة الفعلية
        logger.info(f"Executing service {service_type} for user {user_id}")
    except Exception as e:
        logger.error(f"Error executing service: {str(e)}")

async def execute_bulk_service_task(user_id: int, service_type: ServiceType, product_ids: List[int], options: dict, transaction_id: int):
    """تنفيذ خدمة جماعية في الخلفية"""
    try:
        for product_id in product_ids:
            # تنفيذ الخدمة لكل منتج
            logger.info(f"Executing service {service_type} for product {product_id}")
    except Exception as e:
        logger.error(f"Error executing bulk service: {str(e)}")