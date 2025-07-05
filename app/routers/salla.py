from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
import uuid
import os
import json
import hmac
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import Optional

# ✅ إضافة pydantic للتعامل مع البيانات
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.salla import SallaStore, SallaProduct
from app.models.pending_store import PendingStore
from app.services.salla_api import SallaAPIService
from app.services.email_service import email_service
from app.routers.auth import get_current_user

# ✅ نموذج البيانات للاختبار
class EmailTestRequest(BaseModel):
    email_type: str  # welcome, reminder, connected
    test_email: str
    store_name: str = "متجر تجريبي"
    store_id: str = "TEST123"

# إنشاء router جديد لسلة
router = APIRouter(prefix="/api/salla", tags=["salla"])
salla_service = SallaAPIService()

@router.get("/authorize")
async def get_authorization_url(current_user: User = Depends(get_current_user)):
    """الحصول على رابط ربط سلة"""
    try:
        state = str(uuid.uuid4())  # رمز حماية عشوائي
        auth_url = salla_service.get_authorization_url(state)
        
        return {
            "authorization_url": auth_url,
            "state": state,
            "message": "افتح الرابط لربط متجر سلة"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في إنشاء رابط الربط: {str(e)}")

@router.post("/oauth/callback")
async def handle_oauth_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """معالجة callback من سلة بعد الموافقة"""
    try:
        print(f"🔄 معالجة OAuth callback للمستخدم: {current_user.email}")
        
        # تبديل code بـ access token
        token_data = await salla_service.exchange_code_for_tokens(code)
        
        if "access_token" not in token_data:
            print(f"❌ خطأ في الحصول على token: {token_data}")
            raise HTTPException(status_code=400, detail="فشل في الحصول على رمز الوصول")
        
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        
        print(f"✅ تم الحصول على access token بنجاح")
        
        # جلب معلومات المتجر
        store_info = await salla_service.get_store_info(access_token)
        
        if "data" not in store_info:
            print(f"❌ خطأ في جلب معلومات المتجر: {store_info}")
            raise HTTPException(status_code=400, detail="فشل في جلب معلومات المتجر")
        
        store_data = store_info["data"]
        print(f"✅ تم جلب معلومات المتجر: {store_data.get('name')}")
        
        # التحقق من وجود المتجر مسبقاً
        existing_store = db.query(SallaStore).filter(
            SallaStore.user_id == current_user.id,
            SallaStore.store_id == str(store_data.get("id"))
        ).first()
        
        if existing_store:
            # تحديث المتجر الموجود
            existing_store.access_token = access_token
            existing_store.refresh_token = refresh_token
            existing_store.token_expires_at = datetime.utcnow() + timedelta(days=14)
            existing_store.store_name = store_data.get("name")
            existing_store.store_domain = store_data.get("domain")
            existing_store.store_plan = store_data.get("plan")
            existing_store.store_status = store_data.get("status")
            existing_store.updated_at = datetime.utcnow()
            store = existing_store
            print(f"✅ تم تحديث المتجر الموجود")
        else:
            # إنشاء متجر جديد
            store = SallaStore(
                user_id=current_user.id,
                store_id=str(store_data.get("id")),
                store_name=store_data.get("name"),
                store_domain=store_data.get("domain"),
                store_plan=store_data.get("plan"),
                store_status=store_data.get("status"),
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=datetime.utcnow() + timedelta(days=14),
                webhook_secret=str(uuid.uuid4())
            )
            db.add(store)
            print(f"✅ تم إنشاء متجر جديد")
        
        db.commit()
        db.refresh(store)
        
        # 🔥 إرسال إيميل تأكيد الربط
        try:
            await email_service.send_store_connected_email(
                user_email=current_user.email,
                user_name=current_user.full_name or current_user.email,
                store_name=store.store_name,
                products_synced=0  # سيتم تحديثه بعد المزامنة
            )
            print(f"✅ تم إرسال إيميل تأكيد الربط")
        except Exception as email_error:
            print(f"⚠️ خطأ في إرسال إيميل الربط: {str(email_error)}")
        
        return {
            "success": True,
            "message": "تم ربط المتجر بنجاح!",
            "store": {
                "id": store.id,
                "store_id": store.store_id,
                "name": store.store_name,
                "domain": store.store_domain,
                "plan": store.store_plan,
                "status": store.store_status
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ خطأ عام في callback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في ربط المتجر: {str(e)}")

# 🔥 Webhook Endpoint محسن ومُصحح
@router.post("/webhook")
async def handle_salla_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """استقبال ومعالجة webhooks من سلة - مُصحح مع نظام الإيميلات"""
    try:
        # قراءة البيانات
        payload = await request.body()
        headers = request.headers
        
        print(f"📡 Webhook received from Salla")
        print(f"📋 Headers: {dict(headers)}")
        
        # تحويل البيانات لـ JSON
        try:
            webhook_data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        print(f"📄 Webhook Data: {json.dumps(webhook_data, indent=2, ensure_ascii=False)}")
        
        # استخراج البيانات - التنسيق الصحيح
        event = webhook_data.get("event")
        merchant_id = webhook_data.get("merchant")  # على المستوى الأعلى
        created_at = webhook_data.get("created_at")
        data = webhook_data.get("data", {})  # بيانات المنتج/الطلب/إلخ مباشرة
        
        # Debug logging
        print(f"🔍 Event: {event}")
        print(f"🔍 Merchant ID: {merchant_id} (type: {type(merchant_id)})")
        print(f"🔍 Data keys: {list(data.keys()) if data else 'No data'}")
        
        if not event:
            print(f"❌ Missing event in webhook")
            raise HTTPException(status_code=400, detail="Missing event in webhook")
        
        if not merchant_id:
            print(f"❌ Missing merchant in webhook")
            raise HTTPException(status_code=400, detail="Missing merchant in webhook")
        
        print(f"🎯 Processing event: {event} for merchant: {merchant_id}")
        
        # معالجة الأحداث المختلفة - تمرير merchant_id و data منفصلين
        if event == "app.installed":
            background_tasks.add_task(handle_app_installed, db, str(merchant_id), data)
            
        elif event == "app.store.authorize":
            background_tasks.add_task(handle_app_store_authorize, db, str(merchant_id), data)
            
        elif event == "app.uninstalled":
            background_tasks.add_task(handle_app_uninstalled, db, str(merchant_id), data)
            
        elif event == "product.created":
            background_tasks.add_task(handle_product_created, db, str(merchant_id), data)
            
        elif event == "product.updated":
            background_tasks.add_task(handle_product_updated, db, str(merchant_id), data)
            
        elif event == "product.deleted":
            background_tasks.add_task(handle_product_deleted, db, str(merchant_id), data)
            
        elif event == "order.created":
            background_tasks.add_task(handle_order_created, db, str(merchant_id), data)
            
        elif event == "order.updated":
            background_tasks.add_task(handle_order_updated, db, str(merchant_id), data)
            
        elif event == "customer.created":
            background_tasks.add_task(handle_customer_created, db, str(merchant_id), data)
            
        elif event == "customer.updated":
            background_tasks.add_task(handle_customer_updated, db, str(merchant_id), data)
            
        else:
            print(f"⚠️ Unhandled webhook event: {event}")
        
        # جدولة مهام الإيميلات في الخلفية عند الأحداث المهمة
        if event in ["app.installed", "app.store.authorize"]:
            try:
                # جدولة مهمة تذكير بعد 25 ساعة
                background_tasks.add_task(
                    schedule_reminder_task, 
                    str(merchant_id), 
                    delay_hours=25
                )
                print(f"📅 Scheduled reminder task for merchant {merchant_id}")
            except Exception as task_error:
                print(f"⚠️ Failed to schedule background tasks: {str(task_error)}")
        
        # استجابة سريعة لسلة (مهم: سلة تتوقع 200 OK خلال 30 ثانية)
        return {
            "success": True,
            "message": f"Webhook {event} received and queued for processing",
            "timestamp": datetime.utcnow().isoformat(),
            "merchant": merchant_id,
            "event": event
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

@router.get("/stores")
async def get_connected_stores(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """جلب المتاجر المربوطة للمستخدم"""
    try:
        stores = db.query(SallaStore).filter(
            SallaStore.user_id == current_user.id
        ).all()
        
        return [
            {
                "id": store.id,
                "store_id": store.store_id,
                "name": store.store_name,
                "domain": store.store_domain,
                "plan": store.store_plan,
                "status": store.store_status,
                "connected_at": store.created_at,
                "last_sync": store.last_sync_at,
                "products_count": len(store.products) if store.products else 0
            }
            for store in stores
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في جلب المتاجر: {str(e)}")

@router.post("/stores/{store_id}/sync")
async def sync_store_products(
    store_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """مزامنة منتجات المتجر من سلة"""
    try:
        # التحقق من وجود المتجر
        store = db.query(SallaStore).filter(
            SallaStore.id == store_id,
            SallaStore.user_id == current_user.id
        ).first()
        
        if not store:
            raise HTTPException(status_code=404, detail="المتجر غير موجود")
        
        # إضافة مهمة المزامنة في الخلفية
        background_tasks.add_task(sync_products_task, db, store)
        
        return {
            "success": True,
            "message": "بدأت مزامنة المنتجات في الخلفية"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في بدء المزامنة: {str(e)}")

@router.get("/stores/{store_id}/products")
async def get_store_products(
    store_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """جلب منتجات المتجر المحفوظة في قاعدة البيانات"""
    try:
        # التحقق من وجود المتجر
        store = db.query(SallaStore).filter(
            SallaStore.id == store_id,
            SallaStore.user_id == current_user.id
        ).first()
        
        if not store:
            raise HTTPException(status_code=404, detail="المتجر غير موجود")
        
        # جلب المنتجات
        products = db.query(SallaProduct).filter(
            SallaProduct.store_id == store_id
        ).all()
        
        return {
            "store": {
                "id": store.id,
                "name": store.store_name,
                "domain": store.store_domain
            },
            "products": [
                {
                    "id": product.id,
                    "salla_product_id": product.salla_product_id,
                    "name": product.name,
                    "description": product.description,
                    "price": {
                        "amount": product.price_amount,
                        "currency": product.price_currency
                    },
                    "sku": product.sku,
                    "category": product.category_name,
                    "images": product.images,
                    "seo_title": product.seo_title,
                    "seo_description": product.seo_description,
                    "status": product.status,
                    "last_synced": product.last_synced_at,
                    "needs_update": product.needs_update
                }
                for product in products
            ],
            "total_products": len(products)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في جلب المنتجات: {str(e)}")

# ===== API Endpoints جديدة للإيميلات =====

@router.get("/pending-stores")
async def get_pending_stores(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """عرض المتاجر المؤقتة (للمطورين)"""
    try:
        # التحقق من صلاحيات المطور
        if current_user.email not in ["alimobarki.ad@gmail.com", "owner@breevo.com"]:
            raise HTTPException(status_code=403, detail="غير مخول")
        
        pending_stores = db.query(PendingStore).filter(
            PendingStore.is_claimed == False,
            PendingStore.expires_at > datetime.utcnow()
        ).order_by(PendingStore.created_at.desc()).all()
        
        return {
            "success": True,
            "count": len(pending_stores),
            "stores": [store.to_dict() for store in pending_stores]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في جلب المتاجر المؤقتة: {str(e)}")

# ✅ endpoint اختبار الإيميل المُصحح
@router.post("/test-email")
async def test_email_system(
    request: EmailTestRequest,
    db: Session = Depends(get_db)
):
    """اختبار نظام الإيميلات - مُصحح"""
    try:
        print(f"🧪 Testing email system...")
        print(f"📧 Email type: {request.email_type}")
        print(f"📧 Test email: {request.test_email}")
        
        # اختبار الاتصال أولاً
        connection_test = await email_service.test_connection()
        print(f"🔗 Connection test: {'✅ Success' if connection_test else '❌ Failed'}")
        
        success = False
        
        if request.email_type == "welcome":
            success = await email_service.send_store_welcome_email(
                store_email=request.test_email,
                store_name=request.store_name,
                store_id=request.store_id,
                verification_token="test-token-123",
                products_count=25
            )
        elif request.email_type == "reminder":
            success = await email_service.send_store_reminder_email(
                store_email=request.test_email,
                store_name=request.store_name,
                store_id=request.store_id,
                verification_token="test-token-123",
                days_remaining=5
            )
        elif request.email_type == "connected":
            success = await email_service.send_store_connected_email(
                user_email=request.test_email,
                user_name="مستخدم تجريبي",
                store_name=request.store_name,
                products_synced=25
            )
        else:
            raise HTTPException(status_code=400, detail="نوع إيميل غير مدعوم")
        
        return {
            "success": success,
            "message": f"تم إرسال إيميل {request.email_type} إلى {request.test_email}" if success else "فشل في الإرسال",
            "email_type": request.email_type,
            "test_email": request.test_email,
            "connection_test": connection_test
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في اختبار الإيميل: {str(e)}")

@router.post("/run-email-tasks")
async def run_email_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """تشغيل مهام الإيميلات يدوياً (للمطورين)"""
    try:
        # التحقق من صلاحيات المطور
        if current_user.email not in ["alimobarki.ad@gmail.com", "owner@breevo.com"]:
            raise HTTPException(status_code=403, detail="غير مخول")
        
        # تشغيل مهام التذكير
        await send_pending_reminder_emails(db)
        
        # تشغيل مهام التنظيف
        await cleanup_expired_pending_stores(db)
        
        return {
            "success": True,
            "message": "تم تشغيل جميع مهام الإيميلات بنجاح"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في تشغيل مهام الإيميلات: {str(e)}")

# ===== معالجات الأحداث (Background Tasks) - مُصححة مع نظام الإيميلات =====

async def handle_app_installed(db: Session, merchant_id: str, data: dict):
    """معالجة تثبيت التطبيق - محدث مع نظام الإيميلات"""
    try:
        print(f"🎉 App installed for merchant: {merchant_id}")
        print(f"📄 Installation data: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # استخراج بيانات المتجر من webhook
        store_name = data.get("store_name") or data.get("name", "متجر غير محدد")
        store_domain = data.get("store_domain") or data.get("domain", "")
        store_email = data.get("store_email") or data.get("email", "")
        store_phone = data.get("store_phone") or data.get("phone", "")
        store_plan = data.get("store_plan") or data.get("plan", "basic")
        store_status = data.get("store_status") or data.get("status", "active")
        
        # التحقق من وجود المتجر في pending_stores
        existing_pending = db.query(PendingStore).filter(
            PendingStore.store_id == merchant_id
        ).first()
        
        if existing_pending:
            # تحديث البيانات الموجودة
            existing_pending.store_name = store_name
            existing_pending.store_domain = store_domain
            existing_pending.store_email = store_email or existing_pending.store_email
            existing_pending.store_phone = store_phone or existing_pending.store_phone
            existing_pending.store_plan = store_plan
            existing_pending.store_status = store_status
            existing_pending.updated_at = datetime.utcnow()
            
            # إعادة تعيين إذا كان منتهي الصلاحية
            if existing_pending.is_expired:
                existing_pending.verification_token = str(uuid.uuid4())
                existing_pending.expires_at = datetime.utcnow() + timedelta(days=7)
                existing_pending.welcome_email_sent = False
                existing_pending.reminder_email_sent = False
            
            pending_store = existing_pending
            print(f"✅ Updated existing pending store")
        else:
            # إنشاء متجر مؤقت جديد
            pending_store = PendingStore(
                store_id=merchant_id,
                store_name=store_name,
                store_domain=store_domain,
                store_email=store_email,
                store_phone=store_phone,
                store_plan=store_plan,
                store_status=store_status,
                verification_token=str(uuid.uuid4()),
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            db.add(pending_store)
            print(f"✅ Created new pending store")
        
        db.commit()
        db.refresh(pending_store)
        
        # 🔥 إرسال إيميل ترحيب فوري (إذا توفر إيميل)
        if store_email and not pending_store.welcome_email_sent:
            try:
                print(f"📧 Sending welcome email to: {store_email}")
                
                # محاولة الحصول على عدد المنتجات (اختياري)
                products_count = 0
                try:
                    # يمكن إضافة استدعاء API هنا لاحقاً
                    products_count = data.get("products_count", 0)
                except:
                    pass
                
                # إرسال الإيميل
                email_sent = await email_service.send_store_welcome_email(
                    store_email=store_email,
                    store_name=store_name,
                    store_id=merchant_id,
                    verification_token=pending_store.verification_token,
                    products_count=products_count
                )
                
                if email_sent:
                    pending_store.welcome_email_sent = True
                    pending_store.last_email_sent_at = datetime.utcnow()
                    pending_store.products_count = products_count
                    db.commit()
                    print(f"✅ Welcome email sent successfully")
                else:
                    print(f"❌ Failed to send welcome email")
                    
            except Exception as email_error:
                print(f"❌ Error sending welcome email: {str(email_error)}")
        else:
            if not store_email:
                print(f"⚠️ No email found for store {store_name}")
            elif pending_store.welcome_email_sent:
                print(f"ℹ️ Welcome email already sent for store {store_name}")
        
        print(f"🎉 App installation processed successfully for {store_name}")
        
    except Exception as e:
        print(f"❌ Error handling app installation: {str(e)}")
        db.rollback()

async def handle_app_store_authorize(db: Session, merchant_id: str, data: dict):
    """معالجة ترخيص التطبيق - محدث"""
    try:
        print(f"🔐 App authorized for merchant: {merchant_id}")
        print(f"📄 Authorization data: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        expires_timestamp = data.get("expires")
        scope = data.get("scope")
        
        if access_token:
            # تحديث في PendingStore أولاً
            pending_store = db.query(PendingStore).filter(
                PendingStore.store_id == merchant_id
            ).first()
            
            if pending_store:
                pending_store.access_token = access_token
                pending_store.refresh_token = refresh_token
                if expires_timestamp:
                    pending_store.token_expires_at = datetime.fromtimestamp(expires_timestamp)
                pending_store.updated_at = datetime.utcnow()
                
                print(f"✅ Updated tokens in pending store: {pending_store.store_name}")
            
            # تحديث في SallaStore إذا كان موجوداً (للمتاجر المربوطة مسبقاً)
            store = db.query(SallaStore).filter(
                SallaStore.store_id == merchant_id
            ).first()
            
            if store:
                store.access_token = access_token
                store.refresh_token = refresh_token
                if expires_timestamp:
                    store.token_expires_at = datetime.fromtimestamp(expires_timestamp)
                store.updated_at = datetime.utcnow()
                
                print(f"✅ Updated tokens in salla store: {store.store_name}")
            
            db.commit()
        
    except Exception as e:
        print(f"❌ Error handling app authorization: {str(e)}")
        db.rollback()

async def handle_app_uninstalled(db: Session, merchant_id: str, data: dict):
    """معالجة إلغاء تثبيت التطبيق - محدث"""
    try:
        print(f"😢 App uninstalled for merchant: {merchant_id}")
        
        # تعطيل في PendingStore
        pending_store = db.query(PendingStore).filter(
            PendingStore.store_id == merchant_id
        ).first()
        
        if pending_store:
            pending_store.store_status = "uninstalled"
            pending_store.access_token = None
            pending_store.refresh_token = None
            pending_store.updated_at = datetime.utcnow()
            print(f"✅ Pending store marked as uninstalled")
        
        # تعطيل في SallaStore
        store = db.query(SallaStore).filter(
            SallaStore.store_id == merchant_id
        ).first()
        
        if store:
            store.store_status = "uninstalled"
            store.access_token = None
            store.refresh_token = None
            store.updated_at = datetime.utcnow()
            print(f"✅ Salla store marked as uninstalled: {store.store_name}")
        
        db.commit()
        
    except Exception as e:
        print(f"❌ Error handling app uninstall: {str(e)}")
        db.rollback()

async def handle_product_created(db: Session, merchant_id: str, product_data: dict):
    """معالجة إنشاء منتج جديد - مُصحح"""
    try:
        print(f"📦 New product created for merchant: {merchant_id}")
        print(f"📦 Product ID: {product_data.get('id')}")
        print(f"📦 Product name: {product_data.get('name')}")
        
        # البحث عن المتجر باستخدام store_id
        store = db.query(SallaStore).filter(
            SallaStore.store_id == merchant_id
        ).first()
        
        if not store:
            print(f"❌ Store not found for merchant: {merchant_id}")
            # طباعة المتاجر المتاحة للتشخيص
            all_stores = db.query(SallaStore).all()
            print(f"🏪 Available stores: {[(s.id, s.store_id, s.store_name) for s in all_stores]}")
            return
        
        print(f"✅ Found store: {store.store_name}")
        
        # معالجة السعر
        price_data = product_data.get("price", {})
        price_amount = str(price_data.get("amount", 0)) if price_data else "0"
        price_currency = price_data.get("currency", "SAR") if price_data else "SAR"
        
        # معالجة التصنيف
        category_data = product_data.get("category", {})
        category_id = str(category_data.get("id", "")) if category_data else ""
        category_name = category_data.get("name", "") if category_data else ""
        
        # معالجة الصور
        images = product_data.get("images", [])
        
        # معالجة SEO metadata
        metadata = product_data.get("metadata", {})
        seo_title = metadata.get("title", "") if metadata else ""
        seo_description = metadata.get("description", "") if metadata else ""
        
        # إنشاء المنتج الجديد
        new_product = SallaProduct(
            store_id=store.id,
            salla_product_id=str(product_data.get("id", "")),
            name=product_data.get("name", ""),
            description=product_data.get("description", ""),
            sku=product_data.get("sku", ""),
            url_slug=product_data.get("url", ""),
            price_amount=price_amount,
            price_currency=price_currency,
            category_id=category_id,
            category_name=category_name,
            images=images,
            seo_title=seo_title,
            seo_description=seo_description,
            status=product_data.get("status", "sale"),
            last_synced_at=datetime.utcnow(),
            needs_update=False
        )
        
        db.add(new_product)
        db.commit()
        print(f"✅ Product created successfully: {product_data.get('name')}")
        
    except Exception as e:
        print(f"❌ Error handling product creation: {str(e)}")
        db.rollback()

async def handle_product_updated(db: Session, merchant_id: str, product_data: dict):
    """معالجة تحديث منتج - مُصحح"""
    try:
        print(f"✏️ Product updated for merchant: {merchant_id}")
        print(f"✏️ Product ID: {product_data.get('id')}")
        print(f"✏️ Product name: {product_data.get('name')}")
        
        # البحث عن المتجر
        store = db.query(SallaStore).filter(
            SallaStore.store_id == merchant_id
        ).first()
        
        if not store:
            print(f"❌ Store not found for merchant: {merchant_id}")
            # طباعة المتاجر المتاحة للتشخيص
            all_stores = db.query(SallaStore).all()
            print(f"🏪 Available stores: {[(s.id, s.store_id, s.store_name) for s in all_stores]}")
            return
        
        print(f"✅ Found store: {store.store_name}")
        
        product_id = str(product_data.get("id", ""))
        
        # البحث عن المنتج وتحديثه
        product = db.query(SallaProduct).filter(
            SallaProduct.store_id == store.id,
            SallaProduct.salla_product_id == product_id
        ).first()
        
        if product:
            # تحديث المنتج الموجود
            product.name = product_data.get("name", product.name)
            product.description = product_data.get("description", product.description)
            product.sku = product_data.get("sku", product.sku)
            product.url_slug = product_data.get("url", product.url_slug)
            
            # تحديث السعر
            price_data = product_data.get("price", {})
            if price_data:
                product.price_amount = str(price_data.get("amount", product.price_amount))
                product.price_currency = price_data.get("currency", product.price_currency)
            
            # تحديث التصنيف
            category_data = product_data.get("category", {})
            if category_data:
                product.category_id = str(category_data.get("id", product.category_id))
                product.category_name = category_data.get("name", product.category_name)
            
            # تحديث الصور
            if "images" in product_data:
                product.images = product_data["images"]
            
            # تحديث SEO
            metadata = product_data.get("metadata", {})
            if metadata:
                product.seo_title = metadata.get("title", product.seo_title)
                product.seo_description = metadata.get("description", product.seo_description)
            
            product.status = product_data.get("status", product.status)
            product.last_synced_at = datetime.utcnow()
            
            db.commit()
            print(f"✅ Product updated successfully: {product.name}")
        else:
            print(f"⚠️ Product not found in database: {product_id}")
            print(f"🔄 Creating new product from update event")
            # إنشاء المنتج إذا لم يكن موجوداً
            await handle_product_created(db, merchant_id, product_data)
        
    except Exception as e:
        print(f"❌ Error handling product update: {str(e)}")
        db.rollback()

async def handle_product_deleted(db: Session, merchant_id: str, product_data: dict):
    """معالجة حذف منتج - مُصحح"""
    try:
        print(f"🗑️ Product deleted for merchant: {merchant_id}")
        print(f"🗑️ Product ID: {product_data.get('id')}")
        
        # البحث عن المتجر
        store = db.query(SallaStore).filter(
            SallaStore.store_id == merchant_id
        ).first()
        
        if not store:
            print(f"❌ Store not found for merchant: {merchant_id}")
            return
        
        product_id = str(product_data.get("id", ""))
        
        # البحث عن المنتج وحذفه أو تمييزه كمحذوف
        product = db.query(SallaProduct).filter(
            SallaProduct.store_id == store.id,
            SallaProduct.salla_product_id == product_id
        ).first()
        
        if product:
            # يمكن حذفه فعلياً أو تمييزه كمحذوف
            product.status = "deleted"
            product.last_synced_at = datetime.utcnow()
            
            db.commit()
            print(f"✅ Product marked as deleted: {product.name}")
        else:
            print(f"⚠️ Product not found: {product_id}")
        
    except Exception as e:
        print(f"❌ Error handling product deletion: {str(e)}")
        db.rollback()

async def handle_order_created(db: Session, merchant_id: str, order_data: dict):
    """معالجة إنشاء طلب جديد"""
    try:
        print(f"🛒 New order created for merchant: {merchant_id}")
        print(f"🛒 Order ID: {order_data.get('id')}")
        
        order_id = order_data.get("id")
        order_total = order_data.get("amounts", {}).get("total", 0)
        
        print(f"✅ Order {order_id} processed successfully (Total: {order_total})")
        
    except Exception as e:
        print(f"❌ Error handling order creation: {str(e)}")

async def handle_order_updated(db: Session, merchant_id: str, order_data: dict):
    """معالجة تحديث طلب"""
    try:
        print(f"📝 Order updated for merchant: {merchant_id}")
        
        order_id = order_data.get("id")
        status = order_data.get("status", {}).get("name", "unknown")
        
        print(f"✅ Order {order_id} updated - Status: {status}")
        
    except Exception as e:
        print(f"❌ Error handling order update: {str(e)}")

async def handle_customer_created(db: Session, merchant_id: str, customer_data: dict):
    """معالجة إنشاء عميل جديد"""
    try:
        print(f"👤 New customer created for merchant: {merchant_id}")
        
        customer_id = customer_data.get("id")
        customer_name = customer_data.get("name", "Unknown")
        
        print(f"✅ Customer {customer_name} ({customer_id}) processed successfully")
        
    except Exception as e:
        print(f"❌ Error handling customer creation: {str(e)}")

async def handle_customer_updated(db: Session, merchant_id: str, customer_data: dict):
    """معالجة تحديث عميل"""
    try:
        print(f"✏️ Customer updated for merchant: {merchant_id}")
        
        customer_id = customer_data.get("id")
        
        print(f"✅ Customer {customer_id} updated successfully")
        
    except Exception as e:
        print(f"❌ Error handling customer update: {str(e)}")

# ===== مهام مجدولة للإيميلات =====

async def send_pending_reminder_emails(db: Session):
    """مهمة مجدولة لإرسال إيميلات التذكير للمتاجر المعلقة"""
    try:
        print("🔄 Checking for pending stores needing reminder emails...")
        
        # العثور على المتاجر التي تحتاج تذكير
        pending_stores = db.query(PendingStore).filter(
            PendingStore.is_claimed == False,
            PendingStore.reminder_email_sent == False,
            PendingStore.welcome_email_sent == True,
            PendingStore.store_email.isnot(None),
            PendingStore.expires_at > datetime.utcnow()
        ).all()
        
        reminder_count = 0
        
        for store in pending_stores:
            if store.should_send_reminder:
                try:
                    print(f"📧 Sending reminder email to: {store.store_email}")
                    
                    email_sent = await email_service.send_store_reminder_email(
                        store_email=store.store_email,
                        store_name=store.store_name,
                        store_id=store.store_id,
                        verification_token=store.verification_token,
                        days_remaining=store.days_remaining
                    )
                    
                    if email_sent:
                        store.reminder_email_sent = True
                        store.last_email_sent_at = datetime.utcnow()
                        reminder_count += 1
                        print(f"✅ Reminder email sent to {store.store_name}")
                    else:
                        print(f"❌ Failed to send reminder email to {store.store_name}")
                        
                except Exception as email_error:
                    print(f"❌ Error sending reminder to {store.store_name}: {str(email_error)}")
                    continue
        
        if reminder_count > 0:
            db.commit()
            print(f"✅ Sent {reminder_count} reminder emails")
        else:
            print("ℹ️ No reminder emails needed at this time")
        
    except Exception as e:
        print(f"❌ Error in reminder email task: {str(e)}")
        db.rollback()

async def cleanup_expired_pending_stores(db: Session):
    """تنظيف المتاجر المؤقتة المنتهية الصلاحية"""
    try:
        print("🧹 Cleaning up expired pending stores...")
        
        # حذف المتاجر المنتهية الصلاحية والغير مربوطة
        expired_stores = db.query(PendingStore).filter(
            PendingStore.is_claimed == False,
            PendingStore.expires_at < datetime.utcnow() - timedelta(days=1)  # انتهت أمس
        ).all()
        
        deleted_count = 0
        for store in expired_stores:
            print(f"🗑️ Deleting expired pending store: {store.store_name}")
            db.delete(store)
            deleted_count += 1
        
        if deleted_count > 0:
            db.commit()
            print(f"✅ Cleaned up {deleted_count} expired pending stores")
        else:
            print("ℹ️ No expired stores to clean up")
            
    except Exception as e:
        print(f"❌ Error in cleanup task: {str(e)}")
        db.rollback()

async def schedule_reminder_task(merchant_id: str, delay_hours: int = 25):
    """جدولة مهمة تذكير مؤجلة"""
    await asyncio.sleep(delay_hours * 3600)  # انتظار المدة المحددة
    
    try:
        from app.database import get_db
        db = next(get_db())
        await send_pending_reminder_emails(db)
    except Exception as e:
        print(f"❌ Error in scheduled reminder task: {str(e)}")

async def sync_products_task(db: Session, store: SallaStore):
    """مهمة مزامنة المنتجات (تعمل في الخلفية)"""
    try:
        print(f"🔄 بدء مزامنة المنتجات للمتجر: {store.store_name}")
        
        page = 1
        total_synced = 0
        
        while True:
            # جلب المنتجات من سلة (صفحة واحدة)
            products_data = await salla_service.get_products(
                store.access_token, 
                page=page, 
                per_page=20
            )
            
            if not products_data.get("data"):
                print(f"📄 انتهاء الصفحات في الصفحة رقم {page}")
                break
            
            print(f"📄 معالجة صفحة {page} - {len(products_data['data'])} منتج")
            
            for product_data in products_data["data"]:
                try:
                    # البحث عن المنتج الموجود
                    existing_product = db.query(SallaProduct).filter(
                        SallaProduct.store_id == store.id,
                        SallaProduct.salla_product_id == str(product_data["id"])
                    ).first()
                    
                    # إعداد بيانات المنتج
                    price_data = product_data.get("price", {})
                    category_data = product_data.get("category", {})
                    metadata = product_data.get("metadata", {})
                    
                    product_info = {
                        "store_id": store.id,
                        "salla_product_id": str(product_data["id"]),
                        "name": product_data.get("name", ""),
                        "description": product_data.get("description", ""),
                        "sku": product_data.get("sku", ""),
                        "url_slug": product_data.get("url", ""),
                        "price_amount": str(price_data.get("amount", 0)) if price_data else "0",
                        "price_currency": price_data.get("currency", "SAR") if price_data else "SAR",
                        "category_id": str(category_data.get("id", "")) if category_data else "",
                        "category_name": category_data.get("name", "") if category_data else "",
                        "images": product_data.get("images", []),
                        "seo_title": metadata.get("title", "") if metadata else "",
                        "seo_description": metadata.get("description", "") if metadata else "",
                        "status": product_data.get("status", "sale"),
                        "last_synced_at": datetime.utcnow(),
                        "needs_update": False
                    }
                    
                    if existing_product:
                        # تحديث المنتج الموجود
                        for key, value in product_info.items():
                            if key != "store_id":  # لا نحدث store_id
                                setattr(existing_product, key, value)
                    else:
                        # إنشاء منتج جديد
                        new_product = SallaProduct(**product_info)
                        db.add(new_product)
                    
                    total_synced += 1
                    
                except Exception as product_error:
                    print(f"❌ خطأ في معالجة المنتج {product_data.get('id')}: {product_error}")
                    continue
            
            # الانتقال للصفحة التالية
            page += 1
            
            # التحقق من وجود صفحات أخرى
            pagination = products_data.get("pagination", {})
            if page > pagination.get("totalPages", 1):
                break
        
        # تحديث وقت آخر مزامنة
        store.last_sync_at = datetime.utcnow()
        db.commit()
        
        print(f"✅ انتهت المزامنة بنجاح - تم مزامنة {total_synced} منتج")
        
    except Exception as e:
        print(f"❌ خطأ في مزامنة المنتجات: {str(e)}")
        db.rollback()

def verify_salla_signature(payload: bytes, signature: str) -> bool:
    """التحقق من صحة webhook signature حسب وثائق سلة"""
    try:
        # الحصول على webhook secret من متغيرات البيئة
        webhook_secret = os.getenv("SALLA_WEBHOOK_SECRET")
        
        if not webhook_secret:
            print("⚠️ SALLA_WEBHOOK_SECRET not configured")
            return True  # السماح بالتمرير إذا لم يكن secret محدد
        
        # حساب SHA256 hash حسب وثائق سلة
        calculated_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # إزالة أي prefix مثل "sha256=" إذا موجود
        signature_to_compare = signature.replace("sha256=", "")
        
        # المقارنة الآمنة
        is_valid = hmac.compare_digest(calculated_signature, signature_to_compare)
        
        if not is_valid:
            print(f"❌ Signature mismatch:")
            print(f"   Expected: {calculated_signature}")
            print(f"   Received: {signature_to_compare}")
        
        return is_valid
        
    except Exception as e:
        print(f"❌ Error verifying webhook signature: {str(e)}")
        return False