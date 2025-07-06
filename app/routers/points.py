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
    PointPackagePurchase, ServiceUsage, TransactionType, ServiceType
)
from app.schemas.points import (
    PointsBalanceResponse, PointsBalanceUpdate,
    PointPackageResponse, PointPackagesListResponse,
    TransactionResponse, TransactionsListRequest, TransactionsListResponse,
    ServicePricingResponse, ServicesListResponse,
    PackagePurchaseRequest, PackagePurchaseResponse,
    ServiceUsageRequest, ServiceUsageResponse,
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
    points_service = PointsService(db)
    
    try:
        # الحصول على حساب النقاط أو إنشاؤه
        user_points = points_service.get_or_create_user_points(current_user.id)
        
        # التحقق من إعادة تعيين الحد اليومي
        points_service.check_daily_reset(user_points)
        
        return PointsBalanceResponse(
            balance=user_points.balance,
            total_purchased=user_points.total_purchased,
            total_spent=user_points.total_spent,
            total_refunded=user_points.total_refunded,
            daily_limit=user_points.daily_limit,
            daily_used=user_points.daily_used,
            daily_remaining=max(0, user_points.daily_limit - user_points.daily_used),
            last_reset_date=user_points.last_reset_date
        )
        
    except Exception as e:
        logger.error(f"Error getting points balance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب رصيد النقاط: {str(e)}")

@router.get("/check-balance", response_model=CheckBalanceResponse)
async def check_balance_for_service(
    request: CheckBalanceRequest = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """التحقق من توفر رصيد كافي لخدمة معينة"""
    points_service = PointsService(db)
    
    try:
        # الحصول على تسعير الخدمة
        service_pricing = db.query(ServicePricing).filter(
            ServicePricing.service_type == request.service_type,
            ServicePricing.is_active == True
        ).first()
        
        if not service_pricing:
            raise HTTPException(status_code=404, detail="الخدمة غير موجودة")
        
        user_points = points_service.get_or_create_user_points(current_user.id)
        required_points = service_pricing.points_cost * request.quantity
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
        new_balance = points_service.add_points(
            user_points=user_points,
            amount=package.points,
            transaction_type=TransactionType.PURCHASE,
            description=f"شراء باقة {package.name}",
            reference_type="package",
            reference_id=package.id,
            payment_method=request.payment_method,
            payment_reference=payment_result['transaction_id']
        )
        
        # تسجيل عملية الشراء
        purchase = PointPackagePurchase(
            user_id=user_points.id,
            package_id=package.id,
            points_purchased=package.points,
            price_paid=package.price,
            payment_method=request.payment_method,
            payment_reference=payment_result['transaction_id'],
            status="completed"
        )
        db.add(purchase)
        db.commit()
        
        # إرسال إيميل تأكيد (في الخلفية)
        background_tasks.add_task(
            points_service.send_purchase_confirmation,
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
            new_balance=new_balance,
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
    request: TransactionsListRequest = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """الحصول على سجل معاملات النقاط"""
    try:
        user_points = db.query(UserPoints).filter(
            UserPoints.user_id == current_user.id
        ).first()
        
        if not user_points:
            return TransactionsListResponse(
                transactions=[],
                total=0,
                page=request.page,
                per_page=request.per_page,
                pages=0
            )
        
        query = db.query(PointTransaction).filter(
            PointTransaction.user_id == user_points.id
        )
        
        # تطبيق الفلاتر
        if request.type:
            query = query.filter(PointTransaction.type == request.type)
        
        if request.start_date:
            query = query.filter(PointTransaction.created_at >= request.start_date)
        
        if request.end_date:
            query = query.filter(PointTransaction.created_at <= request.end_date)
        
        # العد الإجمالي
        total = query.count()
        
        # التقسيم
        transactions = query.order_by(PointTransaction.created_at.desc()).offset(
            (request.page - 1) * request.per_page
        ).limit(request.per_page).all()
        
        return TransactionsListResponse(
            transactions=transactions,
            total=total,
            page=request.page,
            per_page=request.per_page,
            pages=(total + request.per_page - 1) // request.per_page
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
        
        services = query.order_by(ServicePricing.points_cost).all()
        
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

@router.post("/services/use", response_model=ServiceUsageResponse)
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
        
        if user_points.balance < service.points_cost:
            raise HTTPException(
                status_code=400, 
                detail=f"رصيد غير كافي. المطلوب: {service.points_cost} نقطة، المتوفر: {user_points.balance} نقطة"
            )
        
        # خصم النقاط
        new_balance = points_service.deduct_points(
            user_points=user_points,
            amount=service.points_cost,
            transaction_type=TransactionType.DEDUCT,
            description=f"استخدام خدمة: {service.name}",
            reference_type="service",
            reference_id=service.id
        )
        
        # تسجيل الاستخدام
        usage = ServiceUsage(
            user_id=current_user.id,
            service_type=request.service_type,
            points_spent=service.points_cost,
            transaction_id=user_points.transactions[-1].id,  # آخر معاملة
            product_id=request.product_id,
            store_id=request.store_id,
            status="processing"
        )
        db.add(usage)
        db.commit()
        
        # تنفيذ الخدمة في الخلفية
        background_tasks.add_task(
            points_service.execute_service,
            usage.id,
            request.service_type,
            request.options
        )
        
        return ServiceUsageResponse(
            usage_id=usage.id,
            service_type=request.service_type,
            service_name=service.name,
            points_spent=service.points_cost,
            new_balance=new_balance,
            status="processing",
            created_at=usage.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error using service: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في استخدام الخدمة: {str(e)}")

# ===== التحليلات =====

@router.get("/analytics", response_model=PointsAnalyticsResponse)
async def get_points_analytics(
    request: PointsAnalyticsRequest = Depends(),
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
            return PointsAnalyticsResponse(
                total_purchased=0,
                total_spent=0,
                total_refunded=0,
                current_balance=0,
                usage_by_service={},
                usage_by_month=[],
                top_services=[],
                average_daily_usage=0,
                average_monthly_usage=0,
                period=request.period,
                start_date=datetime.utcnow() - timedelta(days=30),
                end_date=datetime.utcnow()
            )
        
        # تحديد الفترة الزمنية
        end_date = request.end_date or datetime.utcnow()
        if request.start_date:
            start_date = request.start_date
        else:
            if request.period == "week":
                start_date = end_date - timedelta(days=7)
            elif request.period == "month":
                start_date = end_date - timedelta(days=30)
            elif request.period == "year":
                start_date = end_date - timedelta(days=365)
            else:  # all
                start_date = user_points.created_at
        
        # جلب الإحصائيات
        analytics = points_service.get_analytics(
            user_points_id=user_points.id,
            start_date=start_date,
            end_date=end_date
        )
        
        return PointsAnalyticsResponse(
            **analytics,
            period=request.period,
            start_date=start_date,
            end_date=end_date
        )
        
    except Exception as e:
        logger.error(f"Error getting analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب التحليلات: {str(e)}")

# ===== العمليات الجماعية =====

@router.post("/services/bulk", response_model=BulkServiceResponse)
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
        total_cost = service.points_cost * total_products
        
        # التحقق من الرصيد
        user_points = points_service.get_or_create_user_points(current_user.id)
        
        if user_points.balance < total_cost:
            raise HTTPException(
                status_code=400,
                detail=f"رصيد غير كافي. المطلوب: {total_cost} نقطة، المتوفر: {user_points.balance} نقطة"
            )
        
        # خصم النقاط
        new_balance = points_service.deduct_points(
            user_points=user_points,
            amount=total_cost,
            transaction_type=TransactionType.DEDUCT,
            description=f"استخدام خدمة {service.name} على {total_products} منتج",
            reference_type="bulk_service",
            reference_id=service.id,
            metadata={
                "product_ids": request.product_ids,
                "total_products": total_products
            }
        )
        
        # إنشاء مهام لكل منتج
        results = []
        for product_id in request.product_ids:
            usage = ServiceUsage(
                user_id=current_user.id,
                service_type=request.service_type,
                points_spent=service.points_cost,
                product_id=product_id,
                status="pending"
            )
            db.add(usage)
            results.append({
                "product_id": product_id,
                "usage_id": usage.id,
                "status": "pending"
            })
        
        db.commit()
        
        # تنفيذ الخدمات في الخلفية
        background_tasks.add_task(
            points_service.execute_bulk_service,
            [r["usage_id"] for r in results],
            request.service_type,
            request.options
        )
        
        return BulkServiceResponse(
            total_products=total_products,
            total_points=total_cost,
            processed=0,
            failed=0,
            results=results,
            new_balance=new_balance
        )
        
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
        new_balance = points_service.add_points(
            user_points=user_points,
            amount=amount,
            transaction_type=TransactionType.BONUS,
            description=f"مكافأة: {reason}",
            reference_type="admin_bonus"
        )
        
        return {
            "success": True,
            "message": f"تم إضافة {amount} نقطة بنجاح",
            "new_balance": new_balance
        }
        
    except Exception as e:
        logger.error(f"Error adding bonus points: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في إضافة النقاط: {str(e)}")