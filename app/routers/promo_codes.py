# app/routers/promo_codes.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
import logging

from app.database import get_db
from app.models.user import User
from app.models.points import PromoCode, PointPackage
from app.routers.auth import get_current_user

# إعداد logging
logger = logging.getLogger(__name__)

# إنشاء router
router = APIRouter(prefix="/api/promo-codes", tags=["promo_codes"])

# ===== التحقق من كود الخصم =====

@router.post("/validate")
async def validate_promo_code(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """التحقق من صحة كود الخصم"""
    try:
        code = request.get('code', '').upper().strip()
        plan_id = request.get('planId')
        package_id = request.get('packageId')
        billing_cycle = request.get('billingCycle', 'monthly')
        
        if not code:
            raise HTTPException(status_code=400, detail="يرجى إدخال كود الخصم")
        
        # البحث عن الكود
        promo = db.query(PromoCode).filter(
            PromoCode.code == code,
            PromoCode.is_active == True
        ).first()
        
        if not promo:
            raise HTTPException(status_code=404, detail="كود الخصم غير موجود")
        
        # التحقق من الصلاحية
        if not promo.is_valid():
            if promo.valid_until and datetime.utcnow() > promo.valid_until:
                raise HTTPException(status_code=400, detail="كود الخصم منتهي الصلاحية")
            elif promo.max_uses and promo.times_used >= promo.max_uses:
                raise HTTPException(status_code=400, detail="تم استخدام الكود بالحد الأقصى")
            else:
                raise HTTPException(status_code=400, detail="كود الخصم غير صالح")
        
        # التحقق من الباقات المسموحة
        if promo.allowed_packages and package_id:
            if package_id not in promo.allowed_packages:
                raise HTTPException(
                    status_code=400, 
                    detail="كود الخصم غير صالح لهذه الباقة"
                )
        
        # حساب قيمة الخصم
        discount_amount = Decimal('0')
        base_price = Decimal('0')
        
        if package_id:
            # للنقاط
            package = db.query(PointPackage).filter(
                PointPackage.id == package_id
            ).first()
            
            if package:
                base_price = package.price
                if billing_cycle == 'yearly':
                    base_price = base_price * 12 * Decimal('0.8')
        elif plan_id:
            # للخطط الشهرية
            # يمكن إضافة منطق الخطط هنا
            plan_prices = {
                'pro': Decimal('99'),
                'business': Decimal('299')
            }
            base_price = plan_prices.get(plan_id, Decimal('0'))
            if billing_cycle == 'yearly':
                base_price = base_price * 12 * Decimal('0.8')
        
        # حساب الخصم
        if base_price > 0:
            if promo.discount_type == 'percentage':
                discount_amount = base_price * (promo.discount_value / 100)
                if promo.max_discount:
                    discount_amount = min(discount_amount, promo.max_discount)
            else:
                discount_amount = min(promo.discount_value, base_price)
        
        return {
            "success": True,
            "promoCode": {
                "id": promo.id,
                "code": promo.code,
                "description": promo.description,
                "discountType": promo.discount_type,
                "discountValue": float(promo.discount_value),
                "discountAmount": float(discount_amount),
                "validUntil": promo.valid_until.isoformat() if promo.valid_until else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating promo code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في التحقق من الكود: {str(e)}")

# ===== إنشاء كود خصم (للأدمن) =====

@router.post("/create")
async def create_promo_code(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """إنشاء كود خصم جديد (للأدمن فقط)"""
    # التحقق من صلاحيات الأدمن
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="غير مصرح بهذه العملية")
    
    try:
        # إنشاء الكود
        promo = PromoCode(
            code=request.get('code', '').upper().strip(),
            description=request.get('description', ''),
            discount_type=request.get('discountType', 'percentage'),
            discount_value=Decimal(str(request.get('discountValue', 0))),
            max_discount=Decimal(str(request.get('maxDiscount', 0))) if request.get('maxDiscount') else None,
            min_purchase=Decimal(str(request.get('minPurchase', 0))) if request.get('minPurchase') else None,
            max_uses=request.get('maxUses'),
            max_uses_per_user=request.get('maxUsesPerUser'),
            allowed_packages=request.get('allowedPackages'),
            valid_from=datetime.fromisoformat(request.get('validFrom')) if request.get('validFrom') else datetime.utcnow(),
            valid_until=datetime.fromisoformat(request.get('validUntil')) if request.get('validUntil') else None,
            is_active=request.get('isActive', True)
        )
        
        # التحقق من عدم تكرار الكود
        existing = db.query(PromoCode).filter(
            PromoCode.code == promo.code
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="كود الخصم موجود مسبقاً")
        
        db.add(promo)
        db.commit()
        db.refresh(promo)
        
        logger.info(f"Promo code created: {promo.code} by admin {current_user.id}")
        
        return {
            "success": True,
            "message": "تم إنشاء كود الخصم بنجاح",
            "promoCode": {
                "id": promo.id,
                "code": promo.code,
                "description": promo.description,
                "discountType": promo.discount_type,
                "discountValue": float(promo.discount_value),
                "isActive": promo.is_active
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating promo code: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في إنشاء الكود: {str(e)}")

# ===== قائمة أكواد الخصم (للأدمن) =====

@router.get("/list")
async def list_promo_codes(
    active_only: bool = Query(True, description="عرض الأكواد النشطة فقط"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """الحصول على قائمة أكواد الخصم (للأدمن فقط)"""
    # التحقق من صلاحيات الأدمن
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="غير مصرح بهذه العملية")
    
    try:
        query = db.query(PromoCode)
        
        if active_only:
            query = query.filter(PromoCode.is_active == True)
        
        promos = query.order_by(PromoCode.created_at.desc()).all()
        
        return {
            "promoCodes": [
                {
                    "id": promo.id,
                    "code": promo.code,
                    "description": promo.description,
                    "discountType": promo.discount_type,
                    "discountValue": float(promo.discount_value),
                    "maxDiscount": float(promo.max_discount) if promo.max_discount else None,
                    "timesUsed": promo.times_used,
                    "maxUses": promo.max_uses,
                    "validUntil": promo.valid_until.isoformat() if promo.valid_until else None,
                    "isActive": promo.is_active,
                    "isValid": promo.is_valid(),
                    "createdAt": promo.created_at.isoformat()
                }
                for promo in promos
            ],
            "total": len(promos)
        }
        
    except Exception as e:
        logger.error(f"Error listing promo codes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب الأكواد: {str(e)}")

# ===== تحديث كود الخصم (للأدمن) =====

@router.put("/{promo_id}")
async def update_promo_code(
    promo_id: int,
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """تحديث كود خصم (للأدمن فقط)"""
    # التحقق من صلاحيات الأدمن
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="غير مصرح بهذه العملية")
    
    try:
        promo = db.query(PromoCode).filter(
            PromoCode.id == promo_id
        ).first()
        
        if not promo:
            raise HTTPException(status_code=404, detail="كود الخصم غير موجود")
        
        # تحديث البيانات
        if 'description' in request:
            promo.description = request['description']
        if 'discountValue' in request:
            promo.discount_value = Decimal(str(request['discountValue']))
        if 'maxDiscount' in request:
            promo.max_discount = Decimal(str(request['maxDiscount'])) if request['maxDiscount'] else None
        if 'maxUses' in request:
            promo.max_uses = request['maxUses']
        if 'validUntil' in request:
            promo.valid_until = datetime.fromisoformat(request['validUntil']) if request['validUntil'] else None
        if 'isActive' in request:
            promo.is_active = request['isActive']
        if 'allowedPackages' in request:
            promo.allowed_packages = request['allowedPackages']
        
        promo.updated_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"Promo code updated: {promo.code} by admin {current_user.id}")
        
        return {
            "success": True,
            "message": "تم تحديث كود الخصم بنجاح",
            "promoCode": {
                "id": promo.id,
                "code": promo.code,
                "description": promo.description,
                "isActive": promo.is_active
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating promo code: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في تحديث الكود: {str(e)}")

# ===== حذف كود الخصم (للأدمن) =====

@router.delete("/{promo_id}")
async def delete_promo_code(
    promo_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """حذف كود خصم (للأدمن فقط)"""
    # التحقق من صلاحيات الأدمن
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="غير مصرح بهذه العملية")
    
    try:
        promo = db.query(PromoCode).filter(
            PromoCode.id == promo_id
        ).first()
        
        if not promo:
            raise HTTPException(status_code=404, detail="كود الخصم غير موجود")
        
        # لا نحذف فعلياً، فقط نعطل
        promo.is_active = False
        promo.updated_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"Promo code deactivated: {promo.code} by admin {current_user.id}")
        
        return {
            "success": True,
            "message": "تم إلغاء تفعيل كود الخصم"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting promo code: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في حذف الكود: {str(e)}")

# ===== إحصائيات استخدام الأكواد (للأدمن) =====

@router.get("/statistics")
async def get_promo_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """إحصائيات استخدام أكواد الخصم (للأدمن فقط)"""
    # التحقق من صلاحيات الأدمن
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="غير مصرح بهذه العملية")
    
    try:
        # إجمالي الأكواد
        total_codes = db.query(PromoCode).count()
        active_codes = db.query(PromoCode).filter(
            PromoCode.is_active == True
        ).count()
        
        # الأكواد الأكثر استخداماً
        top_codes = db.query(PromoCode).filter(
            PromoCode.times_used > 0
        ).order_by(PromoCode.times_used.desc()).limit(10).all()
        
        # إجمالي الخصومات
        # يمكن حسابها من جدول المشتريات
        
        return {
            "statistics": {
                "totalCodes": total_codes,
                "activeCodes": active_codes,
                "topCodes": [
                    {
                        "code": code.code,
                        "timesUsed": code.times_used,
                        "discountType": code.discount_type,
                        "discountValue": float(code.discount_value)
                    }
                    for code in top_codes
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting promo statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب الإحصائيات: {str(e)}")