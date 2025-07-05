from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
import uuid
import os
import json
import hmac
import hashlib
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.models.salla import SallaStore, SallaProduct
from app.models.pending_store import PendingStore
from app.services.salla_api import SallaAPIService
from app.services.email_service import email_service
from app.routers.auth import get_current_user

# إعداد logging
logger = logging.getLogger(__name__)

# إنشاء router
router = APIRouter(prefix="/api/salla", tags=["salla"])
salla_service = SallaAPIService()

@router.get("/authorize")
async def get_authorization_url(current_user: User = Depends(get_current_user)):
    """الحصول على رابط ربط سلة"""
    try:
        state = str(uuid.uuid4())
        auth_url = salla_service.get_authorization_url(state)
        
        return {
            "authorization_url": auth_url,
            "state": state,
            "message": "افتح الرابط لربط متجر سلة"
        }
    except Exception as e:
        logger.error(f"خطأ في إنشاء رابط الربط: {str(e)}")
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
        logger.info(f"معالجة OAuth callback للمستخدم: {current_user.email}")
        
        # تبديل code بـ access token
        token_data = await salla_service.exchange_code_for_tokens(code)
        
        if "access_token" not in token_data:
            logger.error(f"خطأ في الحصول على token: {token_data}")
            raise HTTPException(status_code=400, detail="فشل في الحصول على رمز الوصول")
        
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        
        # جلب معلومات المتجر
        store_info = await salla_service.get_store_info(access_token)
        
        if "data" not in store_info:
            logger.error(f"خطأ في جلب معلومات المتجر: {store_info}")
            raise HTTPException(status_code=400, detail="فشل في جلب معلومات المتجر")
        
        store_data = store_info["data"]
        
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
        
        db.commit()
        db.refresh(store)
        
        # إرسال إيميل تأكيد الربط
        try:
            await email_service.send_store_connected_email(
                user_email=current_user.email,
                user_name=current_user.full_name or current_user.email,
                store_name=store.store_name,
                products_synced=0
            )
            logger.info(f"تم إرسال إيميل تأكيد الربط")
        except Exception as email_error:
            logger.warning(f"خطأ في إرسال إيميل الربط: {str(email_error)}")
        
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
        logger.error(f"خطأ عام في callback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في ربط المتجر: {str(e)}")

@router.post("/webhook")
async def handle_salla_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """استقبال ومعالجة webhooks من سلة"""
    try:
        payload = await request.body()
        headers = request.headers
        
        # تحويل البيانات لـ JSON
        try:
            webhook_data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        # استخراج البيانات
        event = webhook_data.get("event")
        merchant_id = webhook_data.get("merchant")
        data = webhook_data.get("data", {})
        
        if not event or not merchant_id:
            logger.error("Missing event or merchant in webhook")
            raise HTTPException(status_code=400, detail="Missing required webhook data")
        
        logger.info(f"Webhook received: {event} for merchant: {merchant_id}")
        
        # معالجة الأحداث المختلفة
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
        
        # جدولة مهام الإيميلات للأحداث المهمة
        if event in ["app.installed", "app.store.authorize"]:
            background_tasks.add_task(schedule_reminder_task, str(merchant_id), delay_hours=25)
        
        return {
            "success": True,
            "message": f"Webhook {event} received and processed",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
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
        logger.error(f"خطأ في جلب المتاجر: {str(e)}")
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
        store = db.query(SallaStore).filter(
            SallaStore.id == store_id,
            SallaStore.user_id == current_user.id
        ).first()
        
        if not store:
            raise HTTPException(status_code=404, detail="المتجر غير موجود")
        
        background_tasks.add_task(sync_products_task, db, store)
        
        return {
            "success": True,
            "message": "بدأت مزامنة المنتجات في الخلفية"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"خطأ في بدء المزامنة: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في بدء المزامنة: {str(e)}")

@router.get("/stores/{store_id}/products")
async def get_store_products(
    store_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """جلب منتجات المتجر المحفوظة في قاعدة البيانات"""
    try:
        store = db.query(SallaStore).filter(
            SallaStore.id == store_id,
            SallaStore.user_id == current_user.id
        ).first()
        
        if not store:
            raise HTTPException(status_code=404, detail="المتجر غير موجود")
        
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
        logger.error(f"خطأ في جلب المنتجات: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب المنتجات: {str(e)}")

# ===== معالجات الأحداث =====

async def handle_app_installed(db: Session, merchant_id: str, data: dict):
    """معالجة تثبيت التطبيق"""
    try:
        logger.info(f"App installed for merchant: {merchant_id}")
        
        store_name = data.get("store_name") or data.get("name", "متجر غير محدد")
        store_domain = data.get("store_domain") or data.get("domain", "")
        store_email = data.get("store_email") or data.get("email", "")
        store_phone = data.get("store_phone") or data.get("phone", "")
        store_plan = data.get("store_plan") or data.get("plan", "basic")
        store_status = data.get("store_status") or data.get("status", "active")
        
        existing_pending = db.query(PendingStore).filter(
            PendingStore.store_id == merchant_id
        ).first()
        
        if existing_pending:
            existing_pending.store_name = store_name
            existing_pending.store_domain = store_domain
            existing_pending.store_email = store_email or existing_pending.store_email
            existing_pending.store_phone = store_phone or existing_pending.store_phone
            existing_pending.store_plan = store_plan
            existing_pending.store_status = store_status
            existing_pending.updated_at = datetime.utcnow()
            
            if existing_pending.is_expired:
                existing_pending.verification_token = str(uuid.uuid4())
                existing_pending.expires_at = datetime.utcnow() + timedelta(days=7)
                existing_pending.welcome_email_sent = False
                existing_pending.reminder_email_sent = False
            
            pending_store = existing_pending
        else:
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
        
        db.commit()
        db.refresh(pending_store)
        
        # إرسال إيميل ترحيب إذا توفر إيميل
        if store_email and not pending_store.welcome_email_sent:
            try:
                products_count = data.get("products_count", 0)
                
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
                    logger.info(f"Welcome email sent to {store_email}")
                    
            except Exception as email_error:
                logger.error(f"Error sending welcome email: {str(email_error)}")
        
        logger.info(f"App installation processed for {store_name}")
        
    except Exception as e:
        logger.error(f"Error handling app installation: {str(e)}")
        db.rollback()

async def handle_app_store_authorize(db: Session, merchant_id: str, data: dict):
    """معالجة ترخيص التطبيق"""
    try:
        logger.info(f"App authorized for merchant: {merchant_id}")
        
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        expires_timestamp = data.get("expires")
        
        if access_token:
            try:
                store_info = await salla_service.get_store_info(access_token)
                
                if "data" in store_info:
                    store_data = store_info["data"]
                    store_name = store_data.get("name", "متجر غير محدد")
                    store_email = store_data.get("email", "")
                    store_domain = store_data.get("domain", "")
                    store_phone = store_data.get("phone", "")
                    store_plan = store_data.get("plan", "basic")
                    store_status = store_data.get("status", "active")
                    
                    existing_pending = db.query(PendingStore).filter(
                        PendingStore.store_id == merchant_id
                    ).first()
                    
                    if existing_pending:
                        existing_pending.store_name = store_name
                        existing_pending.store_domain = store_domain
                        existing_pending.store_email = store_email or existing_pending.store_email
                        existing_pending.store_phone = store_phone or existing_pending.store_phone
                        existing_pending.store_plan = store_plan
                        existing_pending.store_status = store_status
                        existing_pending.access_token = access_token
                        existing_pending.refresh_token = refresh_token
                        if expires_timestamp:
                            existing_pending.token_expires_at = datetime.fromtimestamp(expires_timestamp)
                        existing_pending.updated_at = datetime.utcnow()
                        
                        if existing_pending.is_expired:
                            existing_pending.verification_token = str(uuid.uuid4())
                            existing_pending.expires_at = datetime.utcnow() + timedelta(days=7)
                            existing_pending.welcome_email_sent = False
                            existing_pending.reminder_email_sent = False
                        
                        pending_store = existing_pending
                    else:
                        pending_store = PendingStore(
                            store_id=merchant_id,
                            store_name=store_name,
                            store_domain=store_domain,
                            store_email=store_email,
                            store_phone=store_phone,
                            store_plan=store_plan,
                            store_status=store_status,
                            access_token=access_token,
                            refresh_token=refresh_token,
                            token_expires_at=datetime.fromtimestamp(expires_timestamp) if expires_timestamp else None,
                            verification_token=str(uuid.uuid4()),
                            expires_at=datetime.utcnow() + timedelta(days=7)
                        )
                        db.add(pending_store)
                    
                    db.commit()
                    db.refresh(pending_store)
                    
                    # إرسال إيميل ترحيب إذا توفر إيميل
                    if store_email and not pending_store.welcome_email_sent:
                        try:
                            products_count = 0
                            try:
                                products_data = await salla_service.get_products(access_token, page=1, per_page=1)
                                if products_data and "pagination" in products_data:
                                    products_count = products_data["pagination"].get("total", 0)
                            except:
                                pass
                            
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
                                logger.info(f"Welcome email sent to {store_email}")
                                
                        except Exception as email_error:
                            logger.error(f"Error sending welcome email: {str(email_error)}")
                            
            except Exception as api_error:
                logger.error(f"Error fetching store info: {str(api_error)}")
            
            # تحديث في SallaStore إذا كان موجوداً
            store = db.query(SallaStore).filter(
                SallaStore.store_id == merchant_id
            ).first()
            
            if store:
                store.access_token = access_token
                store.refresh_token = refresh_token
                if expires_timestamp:
                    store.token_expires_at = datetime.fromtimestamp(expires_timestamp)
                store.updated_at = datetime.utcnow()
            
            db.commit()
        
        logger.info(f"App authorization processed for merchant {merchant_id}")
        
    except Exception as e:
        logger.error(f"Error handling app authorization: {str(e)}")
        db.rollback()

async def handle_app_uninstalled(db: Session, merchant_id: str, data: dict):
    """معالجة إلغاء تثبيت التطبيق"""
    try:
        logger.info(f"App uninstalled for merchant: {merchant_id}")
        
        pending_store = db.query(PendingStore).filter(
            PendingStore.store_id == merchant_id
        ).first()
        
        if pending_store:
            pending_store.store_status = "uninstalled"
            pending_store.access_token = None
            pending_store.refresh_token = None
            pending_store.updated_at = datetime.utcnow()
        
        store = db.query(SallaStore).filter(
            SallaStore.store_id == merchant_id
        ).first()
        
        if store:
            store.store_status = "uninstalled"
            store.access_token = None
            store.refresh_token = None
            store.updated_at = datetime.utcnow()
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Error handling app uninstall: {str(e)}")
        db.rollback()

async def handle_product_created(db: Session, merchant_id: str, product_data: dict):
    """معالجة إنشاء منتج جديد"""
    try:
        logger.info(f"New product created for merchant: {merchant_id}")
        
        store = db.query(SallaStore).filter(
            SallaStore.store_id == merchant_id
        ).first()
        
        if not store:
            logger.warning(f"Store not found for merchant: {merchant_id}")
            return
        
        price_data = product_data.get("price", {})
        category_data = product_data.get("category", {})
        metadata = product_data.get("metadata", {})
        
        new_product = SallaProduct(
            store_id=store.id,
            salla_product_id=str(product_data.get("id", "")),
            name=product_data.get("name", ""),
            description=product_data.get("description", ""),
            sku=product_data.get("sku", ""),
            url_slug=product_data.get("url", ""),
            price_amount=str(price_data.get("amount", 0)) if price_data else "0",
            price_currency=price_data.get("currency", "SAR") if price_data else "SAR",
            category_id=str(category_data.get("id", "")) if category_data else "",
            category_name=category_data.get("name", "") if category_data else "",
            images=product_data.get("images", []),
            seo_title=metadata.get("title", "") if metadata else "",
            seo_description=metadata.get("description", "") if metadata else "",
            status=product_data.get("status", "sale"),
            last_synced_at=datetime.utcnow(),
            needs_update=False
        )
        
        db.add(new_product)
        db.commit()
        logger.info(f"Product created: {product_data.get('name')}")
        
    except Exception as e:
        logger.error(f"Error handling product creation: {str(e)}")
        db.rollback()

async def handle_product_updated(db: Session, merchant_id: str, product_data: dict):
    """معالجة تحديث منتج"""
    try:
        logger.info(f"Product updated for merchant: {merchant_id}")
        
        store = db.query(SallaStore).filter(
            SallaStore.store_id == merchant_id
        ).first()
        
        if not store:
            logger.warning(f"Store not found for merchant: {merchant_id}")
            return
        
        product_id = str(product_data.get("id", ""))
        
        product = db.query(SallaProduct).filter(
            SallaProduct.store_id == store.id,
            SallaProduct.salla_product_id == product_id
        ).first()
        
        if product:
            price_data = product_data.get("price", {})
            category_data = product_data.get("category", {})
            metadata = product_data.get("metadata", {})
            
            product.name = product_data.get("name", product.name)
            product.description = product_data.get("description", product.description)
            product.sku = product_data.get("sku", product.sku)
            product.url_slug = product_data.get("url", product.url_slug)
            
            if price_data:
                product.price_amount = str(price_data.get("amount", product.price_amount))
                product.price_currency = price_data.get("currency", product.price_currency)
            
            if category_data:
                product.category_id = str(category_data.get("id", product.category_id))
                product.category_name = category_data.get("name", product.category_name)
            
            if "images" in product_data:
                product.images = product_data["images"]
            
            if metadata:
                product.seo_title = metadata.get("title", product.seo_title)
                product.seo_description = metadata.get("description", product.seo_description)
            
            product.status = product_data.get("status", product.status)
            product.last_synced_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"Product updated: {product.name}")
        else:
            await handle_product_created(db, merchant_id, product_data)
        
    except Exception as e:
        logger.error(f"Error handling product update: {str(e)}")
        db.rollback()

async def handle_product_deleted(db: Session, merchant_id: str, product_data: dict):
    """معالجة حذف منتج"""
    try:
        logger.info(f"Product deleted for merchant: {merchant_id}")
        
        store = db.query(SallaStore).filter(
            SallaStore.store_id == merchant_id
        ).first()
        
        if not store:
            return
        
        product_id = str(product_data.get("id", ""))
        
        product = db.query(SallaProduct).filter(
            SallaProduct.store_id == store.id,
            SallaProduct.salla_product_id == product_id
        ).first()
        
        if product:
            product.status = "deleted"
            product.last_synced_at = datetime.utcnow()
            db.commit()
            logger.info(f"Product marked as deleted: {product.name}")
        
    except Exception as e:
        logger.error(f"Error handling product deletion: {str(e)}")
        db.rollback()

async def handle_order_created(db: Session, merchant_id: str, order_data: dict):
    """معالجة إنشاء طلب جديد"""
    try:
        logger.info(f"New order created for merchant: {merchant_id}")
        order_id = order_data.get("id")
        logger.info(f"Order {order_id} processed successfully")
        
    except Exception as e:
        logger.error(f"Error handling order creation: {str(e)}")

async def handle_order_updated(db: Session, merchant_id: str, order_data: dict):
    """معالجة تحديث طلب"""
    try:
        logger.info(f"Order updated for merchant: {merchant_id}")
        order_id = order_data.get("id")
        status = order_data.get("status", {}).get("name", "unknown")
        logger.info(f"Order {order_id} updated - Status: {status}")
        
    except Exception as e:
        logger.error(f"Error handling order update: {str(e)}")

# ===== مهام مجدولة =====

async def send_pending_reminder_emails(db: Session):
    """إرسال إيميلات التذكير للمتاجر المعلقة"""
    try:
        logger.info("Checking for pending stores needing reminder emails...")
        
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
                        
                except Exception as email_error:
                    logger.error(f"Error sending reminder to {store.store_name}: {str(email_error)}")
                    continue
        
        if reminder_count > 0:
            db.commit()
            logger.info(f"Sent {reminder_count} reminder emails")
        
    except Exception as e:
        logger.error(f"Error in reminder email task: {str(e)}")
        db.rollback()

async def cleanup_expired_pending_stores(db: Session):
    """تنظيف المتاجر المؤقتة المنتهية الصلاحية"""
    try:
        logger.info("Cleaning up expired pending stores...")
        
        expired_stores = db.query(PendingStore).filter(
            PendingStore.is_claimed == False,
            PendingStore.expires_at < datetime.utcnow() - timedelta(days=1)
        ).all()
        
        deleted_count = 0
        for store in expired_stores:
            db.delete(store)
            deleted_count += 1
        
        if deleted_count > 0:
            db.commit()
            logger.info(f"Cleaned up {deleted_count} expired pending stores")
            
    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}")
        db.rollback()

async def schedule_reminder_task(merchant_id: str, delay_hours: int = 25):
    """جدولة مهمة تذكير مؤجلة"""
    await asyncio.sleep(delay_hours * 3600)
    
    try:
        from app.database import get_db
        db = next(get_db())
        await send_pending_reminder_emails(db)
    except Exception as e:
        logger.error(f"Error in scheduled reminder task: {str(e)}")

async def sync_products_task(db: Session, store: SallaStore):
    """مهمة مزامنة المنتجات"""
    try:
        logger.info(f"Starting product sync for store: {store.store_name}")
        
        page = 1
        total_synced = 0
        
        while True:
            products_data = await salla_service.get_products(
                store.access_token, 
                page=page, 
                per_page=20
            )
            
            if not products_data.get("data"):
                break
            
            for product_data in products_data["data"]:
                try:
                    existing_product = db.query(SallaProduct).filter(
                        SallaProduct.store_id == store.id,
                        SallaProduct.salla_product_id == str(product_data["id"])
                    ).first()
                    
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
                        for key, value in product_info.items():
                            if key != "store_id":
                                setattr(existing_product, key, value)
                    else:
                        new_product = SallaProduct(**product_info)
                        db.add(new_product)
                    
                    total_synced += 1
                    
                except Exception as product_error:
                    logger.error(f"Error processing product {product_data.get('id')}: {product_error}")
                    continue
            
            page += 1
            pagination = products_data.get("pagination", {})
            if page > pagination.get("totalPages", 1):
                break
        
        store.last_sync_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Product sync completed - {total_synced} products synced")
        
    except Exception as e:
        logger.error(f"Error in product sync: {str(e)}")
        db.rollback()

def verify_salla_signature(payload: bytes, signature: str) -> bool:
    """التحقق من صحة webhook signature"""
    try:
        webhook_secret = os.getenv("SALLA_WEBHOOK_SECRET")
        
        if not webhook_secret:
            logger.warning("SALLA_WEBHOOK_SECRET not configured")
            return True
        
        calculated_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        signature_to_compare = signature.replace("sha256=", "")
        
        is_valid = hmac.compare_digest(calculated_signature, signature_to_compare)
        
        if not is_valid:
            logger.warning("Webhook signature mismatch")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {str(e)}")
        return False