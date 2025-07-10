# app/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.models.points import UserPoints, PointTransaction, TransactionType
from app.routers.auth import get_current_user
from app.services.points_service import PointsService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# دالة محسنة للتحقق من صلاحيات الأدمن
def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """التحقق من أن المستخدم أدمن"""
    
    # التحقق من حقل is_admin أولاً
    if hasattr(current_user, 'is_admin') and current_user.is_admin:
        return current_user
    
    # قائمة احتياطية للأدمن (للتوافق مع النظام القديم)
    admin_emails = ["alimobarki.ad@gmail.com", "seo@seoraysa.com"]
    
    if current_user.email in admin_emails:
        return current_user
    
    raise HTTPException(
        status_code=403, 
        detail="غير مصرح لك بالوصول لهذه الصفحة - يجب أن تكون مدير النظام"
    )

@router.get("/verify")
async def verify_admin_access(admin: User = Depends(get_admin_user)):
    """التحقق من صلاحيات الأدمن"""
    return {
        "success": True,
        "message": "لديك صلاحيات المدير",
        "user": {
            "id": admin.id,
            "email": admin.email,
            "name": admin.full_name,
            "is_admin": True
        }
    }

@router.get("/users/search")
async def search_users(
    term: str = Query(..., description="البحث بالاسم أو البريد"),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """البحث عن المستخدمين"""
    try:
        # البحث في قاعدة البيانات
        users = db.query(User).filter(
            or_(
                User.email.ilike(f"%{term}%"),
                User.full_name.ilike(f"%{term}%")
            )
        ).limit(20).all()
        
        # إضافة رصيد النقاط لكل مستخدم
        result = []
        for user in users:
            user_points = db.query(UserPoints).filter(
                UserPoints.user_id == user.id
            ).first()
            
            result.append({
                "id": user.id,
                "name": user.full_name,
                "email": user.email,
                "is_admin": getattr(user, 'is_admin', False),
                "plan": user.plan,
                "points_balance": user_points.balance if user_points else 0,
                "created_at": user.created_at
            })
        
        return {"users": result}
        
    except Exception as e:
        logger.error(f"Error searching users: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في البحث: {str(e)}")

@router.post("/points/add")
async def add_points_to_user(
    user_id: int,
    amount: int = Query(..., gt=0, description="عدد النقاط"),
    reason: str = Query(..., description="سبب الإضافة"),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """إضافة نقاط لمستخدم معين"""
    points_service = PointsService()
    
    try:
        # التحقق من وجود المستخدم
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")
        
        # إضافة النقاط
        user_points = points_service.get_or_create_user_points(db, user_id)
        balance_before = user_points.balance
        user_points.balance += amount
        
        # إنشاء معاملة
        transaction = PointTransaction(
            user_id=user_id,
            user_points_id=user_points.id,
            transaction_type=TransactionType.BONUS,
            amount=amount,
            balance_before=balance_before,
            balance_after=user_points.balance,
            description=f"مكافأة من الإدارة: {reason}",
            reference_type="admin_bonus",
            meta_data={
                "admin_id": admin.id,
                "admin_email": admin.email,
                "reason": reason
            }
        )
        db.add(transaction)
        db.commit()
        
        logger.info(f"Admin {admin.email} added {amount} points to user {target_user.email}")
        
        return {
            "success": True,
            "message": f"تم إضافة {amount} نقطة للمستخدم {target_user.full_name}",
            "user": {
                "id": target_user.id,
                "name": target_user.full_name,
                "email": target_user.email,
                "new_balance": user_points.balance
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding points: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في إضافة النقاط: {str(e)}")

@router.get("/stats/overview")
async def get_admin_dashboard_stats(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """إحصائيات لوحة تحكم المدير"""
    try:
        from sqlalchemy import func
        
        # إجمالي المستخدمين
        total_users = db.query(User).count()
        admin_users = db.query(User).filter(User.is_admin == True).count()
        
        # إجمالي النقاط في النظام
        total_points_stats = db.query(
            func.sum(UserPoints.balance).label('total_balance'),
            func.sum(UserPoints.total_purchased).label('total_purchased'),
            func.sum(UserPoints.total_spent).label('total_spent')
        ).first()
        
        # المستخدمين النشطين (لديهم معاملات في آخر 30 يوم)
        from datetime import timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        active_users = db.query(PointTransaction.user_id).filter(
            PointTransaction.created_at >= thirty_days_ago
        ).distinct().count()
        
        # أكثر المستخدمين استخداماً للنقاط
        top_users = db.query(
            User.full_name,
            User.email,
            UserPoints.total_spent,
            UserPoints.balance
        ).join(
            UserPoints, User.id == UserPoints.user_id
        ).order_by(
            UserPoints.total_spent.desc()
        ).limit(10).all()
        
        return {
            "users": {
                "total": total_users,
                "admins": admin_users,
                "active_last_30_days": active_users
            },
            "points": {
                "total_in_system": total_points_stats.total_balance or 0,
                "total_purchased": total_points_stats.total_purchased or 0,
                "total_spent": total_points_stats.total_spent or 0
            },
            "top_users": [
                {
                    "name": user[0],
                    "email": user[1],
                    "points_spent": user[2],
                    "current_balance": user[3]
                } for user in top_users
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب الإحصائيات: {str(e)}")

@router.post("/points/deduct")
async def deduct_points_from_user(
    user_id: int,
    amount: int = Query(..., gt=0, description="عدد النقاط للخصم"),
    reason: str = Query(..., description="سبب الخصم"),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """خصم نقاط من مستخدم معين"""
    points_service = PointsService()
    
    try:
        # التحقق من وجود المستخدم
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")
        
        # التحقق من رصيد المستخدم
        user_points = points_service.get_or_create_user_points(db, user_id)
        
        if user_points.balance < amount:
            raise HTTPException(
                status_code=400, 
                detail=f"رصيد المستخدم ({user_points.balance}) أقل من المبلغ المطلوب خصمه ({amount})"
            )
        
        # خصم النقاط
        balance_before = user_points.balance
        user_points.balance -= amount
        user_points.total_spent += amount
        
        # إنشاء معاملة
        transaction = PointTransaction(
            user_id=user_id,
            user_points_id=user_points.id,
            transaction_type=TransactionType.ADMIN_DEBIT,
            amount=-amount,  # سالب للخصم
            balance_before=balance_before,
            balance_after=user_points.balance,
            description=f"خصم من الإدارة: {reason}",
            reference_type="admin_debit",
            meta_data={
                "admin_id": admin.id,
                "admin_email": admin.email,
                "reason": reason
            }
        )
        db.add(transaction)
        db.commit()
        
        logger.info(f"Admin {admin.email} deducted {amount} points from user {target_user.email}")
        
        return {
            "success": True,
            "message": f"تم خصم {amount} نقطة من المستخدم {target_user.full_name}",
            "user": {
                "id": target_user.id,
                "name": target_user.full_name,
                "email": target_user.email,
                "new_balance": user_points.balance
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deducting points: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في خصم النقاط: {str(e)}")

@router.get("/users/list")
async def list_all_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """عرض قائمة جميع المستخدمين"""
    try:
        # العدد الإجمالي
        total = db.query(User).count()
        
        # جلب المستخدمين مع التقسيم
        users = db.query(User).offset((page - 1) * per_page).limit(per_page).all()
        
        # إضافة معلومات النقاط
        result = []
        for user in users:
            user_points = db.query(UserPoints).filter(
                UserPoints.user_id == user.id
            ).first()
            
            result.append({
                "id": user.id,
                "name": user.full_name,
                "email": user.email,
                "phone": user.phone,
                "plan": user.plan,
                "is_admin": getattr(user, 'is_admin', False),
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "points_balance": user_points.balance if user_points else 0,
                "created_at": user.created_at,
                "last_login": user.last_login_at
            })
        
        return {
            "users": result,
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page
            }
        }
        
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب المستخدمين: {str(e)}")