# app/routers/payments.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import uuid
import hmac
import hashlib
import os

from app.database import get_db
from app.models.user import User
from app.models.points import (
    PointPackage, PointPurchase, UserPoints, PointTransaction,
    TransactionType, PaymentStatus, UserSubscription
)
from app.routers.auth import get_current_user
from app.services.payment_service import PaymentService
from app.services.moyasar_service import MoyasarService

# إعداد logging
logger = logging.getLogger(__name__)

# إنشاء router
router = APIRouter(prefix="/api/payments", tags=["payments"])

# خدمات الدفع
payment_service = PaymentService()
moyasar_service = MoyasarService()

# ===== إنشاء طلب دفع =====

@router.post("/create")
async def create_payment(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """إنشاء طلب دفع جديد"""
    try:
        # استخراج البيانات
        plan_id = request.get('planId')
        billing_cycle = request.get('billingCycle', 'monthly')
        amount = Decimal(str(request.get('amount', 0)))
        billing_info = request.get('billingInfo', {})
        promo_code = request.get('promoCode')
        
        # التحقق من الخطة
        if plan_id == 'points':
            # شراء نقاط
            package_id = request.get('packageId')
            package = db.query(PointPackage).filter(
                PointPackage.id == package_id,
                PointPackage.is_active == True
            ).first()
            
            if not package:
                raise HTTPException(status_code=404, detail="الباقة غير موجودة")
            
            description = f"شراء {package.points} نقطة - {package.name}"
            metadata = {
                "type": "points",
                "package_id": package_id,
                "points": package.points
            }
        else:
            # اشتراك في خطة
            # هنا يمكن إضافة منطق الخطط الشهرية
            description = f"اشتراك {plan_id} - {billing_cycle}"
            metadata = {
                "type": "subscription",
                "plan_id": plan_id,
                "billing_cycle": billing_cycle
            }
        
        # إنشاء معرف فريد للدفعة
        payment_id = str(uuid.uuid4())
        
        # حفظ طلب الدفع في قاعدة البيانات
        purchase = PointPurchase(
            user_id=current_user.id,
            package_id=package_id if plan_id == 'points' else None,
            points=package.points if plan_id == 'points' else 0,
            price=Decimal(str(amount / 1.15)),  # السعر بدون ضريبة
            vat_amount=Decimal(str(amount * 0.15 / 1.15)),
            total_amount=amount,
            payment_status=PaymentStatus.PENDING,
            payment_method='moyasar',
            payment_reference=payment_id,
            promo_code=promo_code,
            payment_data={
                "billing_info": billing_info,
                "metadata": metadata,
                "created_at": datetime.utcnow().isoformat()
            }
        )
        db.add(purchase)
        db.commit()
        db.refresh(purchase)
        
        # إعداد بيانات Moyasar
        moyasar_data = {
            "amount": int(amount * 100),  # تحويل لهللات
            "currency": "SAR",
            "description": description,
            "callback_url": f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/payment/result",
            "metadata": {
                "payment_id": payment_id,
                "purchase_id": str(purchase.id),
                "user_id": str(current_user.id),
                **metadata
            }
        }
        
        logger.info(f"Payment created: {payment_id} for user {current_user.id}")
        
        return {
            "success": True,
            "paymentId": payment_id,
            "purchaseId": purchase.id,
            "amount": float(amount),
            "description": description,
            "moyasarData": moyasar_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating payment: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في إنشاء طلب الدفع: {str(e)}")

# ===== تأكيد الدفع =====

@router.post("/{payment_id}/confirm")
async def confirm_payment(
    payment_id: str,
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """تأكيد نجاح أو فشل الدفع"""
    try:
        # البحث عن طلب الدفع
        purchase = db.query(PointPurchase).filter(
            PointPurchase.payment_reference == payment_id,
            PointPurchase.user_id == current_user.id
        ).first()
        
        if not purchase:
            raise HTTPException(status_code=404, detail="طلب الدفع غير موجود")
        
        status = request.get('status')
        moyasar_payment_id = request.get('moyasarPaymentId')
        error_message = request.get('error')
        
        if status == 'completed':
            # التحقق من الدفعة مع Moyasar (في الإنتاج)
            if os.getenv('MOYASAR_SECRET_KEY'):
                try:
                    payment_verified = await moyasar_service.verify_payment(moyasar_payment_id)
                    if not payment_verified:
                        raise HTTPException(status_code=400, detail="فشل التحقق من الدفعة")
                except Exception as e:
                    logger.error(f"Moyasar verification error: {str(e)}")
                    # في حالة فشل التحقق، نكمل في وضع التطوير فقط
                    if os.getenv('ENVIRONMENT') != 'development':
                        raise
            
            # تحديث حالة الدفع
            purchase.payment_status = PaymentStatus.COMPLETED
            purchase.paid_at = datetime.utcnow()
            
            if moyasar_payment_id:
                purchase.payment_data = purchase.payment_data or {}
                purchase.payment_data['moyasar_id'] = moyasar_payment_id
            
            # إضافة النقاط أو تفعيل الاشتراك
            if purchase.package_id:
                # شراء نقاط
                user_points = db.query(UserPoints).filter(
                    UserPoints.user_id == current_user.id
                ).first()
                
                if not user_points:
                    user_points = UserPoints(
                        user_id=current_user.id,
                        balance=0,
                        total_purchased=0,
                        total_spent=0
                    )
                    db.add(user_points)
                    db.flush()
                
                # إضافة النقاط
                balance_before = user_points.balance
                user_points.balance += purchase.points
                user_points.total_purchased += purchase.points
                
                # إنشاء معاملة
                transaction = PointTransaction(
                    user_id=current_user.id,
                    user_points_id=user_points.id,
                    transaction_type=TransactionType.PURCHASE,
                    amount=purchase.points,
                    balance_before=balance_before,
                    balance_after=user_points.balance,
                    description=f"شراء {purchase.points} نقطة",
                    reference_type="purchase",
                    reference_id=str(purchase.id),
                    payment_method=purchase.payment_method,
                    payment_reference=purchase.payment_reference
                )
                db.add(transaction)
                
                # إرسال إيميل تأكيد
                background_tasks.add_task(
                    send_purchase_confirmation,
                    current_user.email,
                    purchase.points,
                    float(purchase.total_amount)
                )
            else:
                # تفعيل اشتراك
                metadata = purchase.payment_data.get('metadata', {})
                if metadata.get('type') == 'subscription':
                    # إنشاء اشتراك جديد
                    subscription = UserSubscription(
                        user_id=current_user.id,
                        package_id=1,  # يجب تحديد الباقة المناسبة
                        monthly_points=1000,  # حسب الخطة
                        billing_cycle=metadata.get('billing_cycle', 'monthly'),
                        status='active',
                        started_at=datetime.utcnow(),
                        current_period_start=datetime.utcnow(),
                        current_period_end=datetime.utcnow() + timedelta(days=30),
                        auto_renew=True
                    )
                    db.add(subscription)
            
            db.commit()
            
            logger.info(f"Payment confirmed: {payment_id}")
            
            return {
                "success": True,
                "message": "تم تأكيد الدفع بنجاح",
                "paymentId": payment_id,
                "status": "completed"
            }
            
        else:
            # فشل الدفع
            purchase.payment_status = PaymentStatus.FAILED
            
            if error_message:
                purchase.payment_data = purchase.payment_data or {}
                purchase.payment_data['error'] = error_message
            
            db.commit()
            
            logger.warning(f"Payment failed: {payment_id} - {error_message}")
            
            return {
                "success": False,
                "message": "فشل الدفع",
                "paymentId": payment_id,
                "status": "failed",
                "error": error_message
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming payment: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في تأكيد الدفع: {str(e)}")

# ===== التحقق من حالة الدفع =====

@router.get("/{payment_id}/status")
async def get_payment_status(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """الحصول على حالة طلب الدفع"""
    try:
        purchase = db.query(PointPurchase).filter(
            PointPurchase.payment_reference == payment_id,
            PointPurchase.user_id == current_user.id
        ).first()
        
        if not purchase:
            raise HTTPException(status_code=404, detail="طلب الدفع غير موجود")
        
        return {
            "paymentId": payment_id,
            "status": purchase.payment_status.value,
            "amount": float(purchase.total_amount),
            "points": purchase.points,
            "createdAt": purchase.created_at,
            "paidAt": purchase.paid_at,
            "metadata": purchase.payment_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting payment status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب حالة الدفع: {str(e)}")

# ===== Webhook من Moyasar =====

@router.post("/webhook/moyasar")
async def moyasar_webhook(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """استقبال تحديثات من Moyasar"""
    try:
        # التحقق من التوقيع (Signature)
        # يجب إضافة التحقق من webhook signature هنا
        
        event_type = request.get('type')
        data = request.get('data', {})
        
        logger.info(f"Moyasar webhook received: {event_type}")
        
        if event_type == 'payment_authorized':
            # الدفعة تمت الموافقة عليها
            payment_id = data.get('metadata', {}).get('payment_id')
            if payment_id:
                # تحديث حالة الدفع
                purchase = db.query(PointPurchase).filter(
                    PointPurchase.payment_reference == payment_id
                ).first()
                
                if purchase and purchase.payment_status == PaymentStatus.PENDING:
                    purchase.payment_status = PaymentStatus.COMPLETED
                    purchase.paid_at = datetime.utcnow()
                    purchase.payment_data = purchase.payment_data or {}
                    purchase.payment_data['moyasar_webhook'] = data
                    
                    # إضافة النقاط للمستخدم
                    # نفس منطق confirm_payment
                    
                    db.commit()
                    logger.info(f"Payment updated via webhook: {payment_id}")
        
        elif event_type == 'payment_failed':
            # فشل الدفع
            payment_id = data.get('metadata', {}).get('payment_id')
            if payment_id:
                purchase = db.query(PointPurchase).filter(
                    PointPurchase.payment_reference == payment_id
                ).first()
                
                if purchase:
                    purchase.payment_status = PaymentStatus.FAILED
                    db.commit()
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        # لا نرمي خطأ حتى لا يعيد Moyasar المحاولة
        return {"status": "error", "message": str(e)}

# ===== دوال مساعدة =====

async def send_purchase_confirmation(email: str, points: int, amount: float):
    """إرسال إيميل تأكيد الشراء"""
    try:
        # هنا يتم إرسال الإيميل
        logger.info(f"Sending purchase confirmation to {email}")
        # يمكن استخدام خدمة البريد الإلكتروني
    except Exception as e:
        logger.error(f"Error sending confirmation email: {str(e)}")

# ===== استرجاع المبلغ =====

@router.post("/{payment_id}/refund")
async def refund_payment(
    payment_id: str,
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """طلب استرجاع المبلغ"""
    try:
        # البحث عن الدفعة
        purchase = db.query(PointPurchase).filter(
            PointPurchase.payment_reference == payment_id,
            PointPurchase.user_id == current_user.id,
            PointPurchase.payment_status == PaymentStatus.COMPLETED
        ).first()
        
        if not purchase:
            raise HTTPException(status_code=404, detail="الدفعة غير موجودة أو غير مكتملة")
        
        # التحقق من مدة الاسترجاع (30 يوم)
        if datetime.utcnow() - purchase.paid_at > timedelta(days=30):
            raise HTTPException(status_code=400, detail="انتهت مدة الاسترجاع المسموحة")
        
        reason = request.get('reason', '')
        amount = request.get('amount', float(purchase.total_amount))
        
        # معالجة الاسترجاع
        refund_result = await payment_service.refund_payment(
            transaction_id=payment_id,
            amount=amount,
            reason=reason
        )
        
        if refund_result['success']:
            # تحديث حالة الدفعة
            purchase.payment_status = PaymentStatus.REFUNDED
            purchase.refunded_at = datetime.utcnow()
            
            # خصم النقاط إذا كانت لم تُستخدم
            if purchase.package_id:
                user_points = db.query(UserPoints).filter(
                    UserPoints.user_id == current_user.id
                ).first()
                
                if user_points and user_points.balance >= purchase.points:
                    # خصم النقاط
                    balance_before = user_points.balance
                    user_points.balance -= purchase.points
                    user_points.total_refunded += purchase.points
                    
                    # إنشاء معاملة استرجاع
                    transaction = PointTransaction(
                        user_id=current_user.id,
                        user_points_id=user_points.id,
                        transaction_type=TransactionType.REFUND,
                        amount=-purchase.points,
                        balance_before=balance_before,
                        balance_after=user_points.balance,
                        description=f"استرجاع شراء - {reason}",
                        reference_type="refund",
                        reference_id=str(purchase.id)
                    )
                    db.add(transaction)
            
            db.commit()
            
            return {
                "success": True,
                "message": "تم الاسترجاع بنجاح",
                "refundId": refund_result['refund_id'],
                "amount": amount
            }
        else:
            raise HTTPException(status_code=400, detail=refund_result['message'])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing refund: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في معالجة الاسترجاع: {str(e)}")