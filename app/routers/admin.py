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

# دالة للتحقق من صلاحيات الأدمن
def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """التحقق من أن المستخدم أدمن"""
    # يمكنك تخصيص هذا حسب نظامك
    admin_emails = ["alimobarki.ad@gmail.com", "admin@seoraysa.com"]
    
    if current_user.email not in admin_emails and not getattr(current_user, 'is_admin', False):
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذه الصفحة")
    
    return current_user

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
                User.name.ilike(f"%{term}%")
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
                "name": user.name,
                "email": user.email,
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
    amount: int,
    reason: str,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """إضافة نقاط لمستخدم معين"""
    points_service = PointsService(db)
    
    try:
        # التحقق من وجود المستخدم
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")
        
        # إضافة النقاط
        user_points = points_service.get_or_create_user_points(user_id)
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
        
        # إرسال إشعار للمستخدم (اختياري)
        # await send_notification(target_user.email, f"تم إضافة {amount} نقطة لحسابك")
        
        return {
            "success": True,
            "message": f"تم إضافة {amount} نقطة للمستخدم {target_user.name}",
            "user": {
                "id": target_user.id,
                "name": target_user.name,
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

@router.get("/stats/points")
async def get_points_statistics(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """إحصائيات النقاط"""
    try:
        # إجمالي المستخدمين
        total_users = db.query(User).count()
        
        # إجمالي النقاط الموزعة
        total_points = db.query(UserPoints.balance).scalar() or 0
        
        # المستخدمين النشطين (لديهم معاملات في آخر 30 يوم)
        active_users = db.query(PointTransaction.user_id).distinct().count()
        
        # أكثر المستخدمين استخداماً للنقاط
        top_users = db.query(
            User.name,
            User.email,
            UserPoints.total_spent
        ).join(
            UserPoints, User.id == UserPoints.user_id
        ).order_by(
            UserPoints.total_spent.desc()
        ).limit(10).all()
        
        return {
            "total_users": total_users,
            "total_points_distributed": total_points,
            "active_users": active_users,
            "top_users": [
                {
                    "name": user[0],
                    "email": user[1],
                    "points_spent": user[2]
                } for user in top_users
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب الإحصائيات: {str(e)}")

@router.post("/test-accounts/create")
async def create_test_accounts(
    count: int = Query(5, ge=1, le=20, description="عدد الحسابات التجريبية"),
    points_per_account: int = Query(100, ge=50, le=1000, description="النقاط لكل حساب"),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """إنشاء حسابات تجريبية مع نقاط"""
    from app.services.auth_service import auth_service
    points_service = PointsService(db)
    
    created_accounts = []
    
    try:
        for i in range(count):
            # إنشاء حساب تجريبي
            test_email = f"tester{i+1}_{datetime.now().timestamp():.0f}@test.com"
            test_user_data = {
                "email": test_email,
                "name": f"مختبر {i+1}",
                "password": "Test@123"  # كلمة مرور موحدة للحسابات التجريبية
            }
            
            # إنشاء المستخدم
            user = auth_service.create_user(db, test_user_data)
            
            # إضافة النقاط
            user_points = points_service.get_or_create_user_points(user.id)
            user_points.balance = points_per_account
            
            # إنشاء معاملة
            transaction = PointTransaction(
                user_id=user.id,
                user_points_id=user_points.id,
                transaction_type=TransactionType.BONUS,
                amount=points_per_account,
                balance_before=0,
                balance_after=points_per_account,
                description="نقاط تجريبية للاختبار",
                reference_type="test_account_bonus"
            )
            db.add(transaction)
            
            created_accounts.append({
                "email": test_email,
                "password": "Test@123",
                "name": test_user_data["name"],
                "points": points_per_account
            })
        
        db.commit()
        
        return {
            "success": True,
            "message": f"تم إنشاء {count} حساب تجريبي",
            "accounts": created_accounts
        }
        
    except Exception as e:
        logger.error(f"Error creating test accounts: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في إنشاء الحسابات: {str(e)}")