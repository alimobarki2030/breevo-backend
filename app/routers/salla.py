from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
import uuid
import os
import json
import hmac
import hashlib
from datetime import datetime, timedelta
import httpx

from app.database import get_db
from app.models.user import User
from app.models.salla import SallaStore, SallaProduct
from app.services.salla_api import SallaAPIService
from app.routers.auth import get_current_user

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
    """استقبال ومعالجة webhooks من سلة - مُصحح"""
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
                "merchant_id": store.store_id,  # إضافة merchant_id للتوافق
                "name": store.store_name,
                "domain": store.store_domain,
                "plan": store.store_plan,
                "status": store.store_status,
                "connected_at": store.created_at,
                "last_synced": store.last_sync_at,
                "products_count": len(store.products) if store.products else 0,
                "webhook_status": "active"
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

# ===== معالجات الأحداث (Background Tasks) - مُصححة =====

async def handle_app_installed(db: Session, merchant_id: str, data: dict):
    """معالجة تثبيت التطبيق"""
    try:
        print(f"🎉 App installed for merchant: {merchant_id}")
        print(f"📄 Installation data: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        app_name = data.get("app_name", "Unknown App")
        installation_date = data.get("installation_date")
        store_type = data.get("store_type", "production")
        
        print(f"✅ App '{app_name}' installed for merchant {merchant_id} on {installation_date}")
        
    except Exception as e:
        print(f"❌ Error handling app installation: {str(e)}")

async def handle_app_store_authorize(db: Session, merchant_id: str, data: dict):
    """🔥 معالجة ترخيص التطبيق - محدث ومُصحح"""
    try:
        print(f"🔐 App authorized for merchant: {merchant_id}")
        print(f"📄 Authorization data: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        expires = data.get("expires")
        scope = data.get("scope")
        app_name = data.get("app_name", "SEO Ray")
        app_description = data.get("app_description", "")
        
        if not access_token:
            print("❌ No access token in authorization data")
            return
        
        # 🔍 جلب معلومات المتجر من سلة API
        store_info = await fetch_store_info_from_salla(access_token, merchant_id)
        
        # 💾 البحث عن المتجر الموجود أو إنشاء جديد
        existing_store = db.query(SallaStore).filter(
            SallaStore.store_id == merchant_id
        ).first()
        
        if existing_store:
            # تحديث المتجر الموجود
            existing_store.access_token = access_token
            existing_store.refresh_token = refresh_token
            if expires:
                existing_store.token_expires_at = datetime.fromtimestamp(expires)
            existing_store.store_name = store_info.get('name', existing_store.store_name)
            existing_store.store_domain = store_info.get('domain', existing_store.store_domain)
            existing_store.store_status = "active"
            existing_store.updated_at = datetime.utcnow()
            
            print(f"✅ Updated existing store: {existing_store.store_name}")
        else:
            # إنشاء متجر جديد (بدون user_id في البداية)
            new_store = SallaStore(
                user_id=None,  # سيتم ربطه لاحقاً
                store_id=merchant_id,
                store_name=store_info.get('name', f'Store {merchant_id}'),
                store_domain=store_info.get('domain', ''),
                store_plan=store_info.get('plan', 'unknown'),
                store_status="active",
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=datetime.fromtimestamp(expires) if expires else None,
                webhook_secret=str(uuid.uuid4()),
                auto_sync_enabled=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(new_store)
            print(f"✅ Created new store: {new_store.store_name}")
        
        db.commit()
        
        # 🔄 بدء التزامن الأولي للمنتجات
        if existing_store:
            await sync_products_initial(db, existing_store, access_token)
        else:
            # إعادة جلب المتجر المحفوظ
            saved_store = db.query(SallaStore).filter(
                SallaStore.store_id == merchant_id
            ).first()
            if saved_store:
                await sync_products_initial(db, saved_store, access_token)
        
    except Exception as e:
        print(f"❌ Error handling app authorization: {str(e)}")
        db.rollback()

async def fetch_store_info_from_salla(access_token: str, merchant_id: str) -> dict:
    """جلب معلومات المتجر من سلة API"""
    try:
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        async with httpx.AsyncClient() as client:
            # جرب endpoint معلومات المتجر
            response = await client.get(
                'https://api.salla.dev/admin/v2/store', 
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                store_data = result.get('data', {})
                
                print(f"✅ Fetched store info from Salla: {store_data.get('name')}")
                return {
                    'name': store_data.get('name', f'Salla Store {merchant_id}'),
                    'domain': store_data.get('domain', f'https://store-{merchant_id}.salla.sa'),
                    'plan': store_data.get('plan', 'unknown'),
                    'status': store_data.get('status', 'active'),
                    'id': merchant_id
                }
            else:
                print(f"❌ Failed to fetch store info from Salla: {response.status_code}")
                return default_store_info(merchant_id)
                
    except Exception as e:
        print(f"❌ Error fetching store info from Salla: {e}")
        return default_store_info(merchant_id)

def default_store_info(merchant_id: str) -> dict:
    """معلومات افتراضية للمتجر"""
    return {
        'name': f'Salla Store {merchant_id}',
        'domain': f'https://store-{merchant_id}.salla.sa',
        'plan': 'unknown',
        'status': 'active',
        'id': merchant_id
    }

async def sync_products_initial(db: Session, store: SallaStore, access_token: str):
    """تزامن أولي للمنتجات"""
    try:
        print(f"🔄 Starting initial product sync for store: {store.store_name}")
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        # جلب الصفحة الأولى من المنتجات
        async with httpx.AsyncClient() as client:
            response = await client.get(
                'https://api.salla.dev/admin/v2/products?per_page=50', 
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                products = result.get('data', [])
                
                # حفظ المنتجات
                saved_count = 0
                for product in products:
                    try:
                        await save_product_to_database(db, product, store.id)
                        saved_count += 1
                    except Exception as product_error:
                        print(f"❌ Error saving product {product.get('id')}: {product_error}")
                        continue
                
                # تحديث وقت آخر تزامن
                store.last_sync_at = datetime.utcnow()
                db.commit()
                
                print(f"✅ Initial sync completed: {saved_count} products synced for {store.store_name}")
            else:
                print(f"❌ Failed to sync products: {response.status_code}")
                
    except Exception as e:
        print(f"❌ Error in initial product sync: {e}")

async def save_product_to_database(db: Session, product_data: dict, store_id: int):
    """حفظ منتج في قاعدة البيانات"""
    try:
        # معالجة السعر
        price_data = product_data.get("price", {})
        price_amount = str(price_data.get("amount", 0)) if price_data else "0"
        price_currency = price_data.get("currency", "SAR") if price_data else "SAR"
        
        # معالجة التصنيف
        categories = product_data.get("categories", [])
        category_name = categories[0].get("name", "") if categories else ""
        category_id = str(categories[0].get("id", "")) if categories else ""
        
        # معالجة الصور
        images = product_data.get("images", [])
        
        # التحقق من وجود المنتج
        existing_product = db.query(SallaProduct).filter(
            SallaProduct.store_id == store_id,
            SallaProduct.salla_product_id == str(product_data.get("id"))
        ).first()
        
        product_info = {
            "store_id": store_id,
            "salla_product_id": str(product_data.get("id")),
            "name": product_data.get("name", ""),
            "description": product_data.get("description", ""),
            "sku": product_data.get("sku", ""),
            "url_slug": product_data.get("url", ""),
            "price_amount": price_amount,
            "price_currency": price_currency,
            "category_id": category_id,
            "category_name": category_name,
            "images": images,
            "seo_title": product_data.get("seo_title", ""),
            "seo_description": product_data.get("seo_description", ""),
            "status": product_data.get("status", "sale"),
            "last_synced_at": datetime.utcnow(),
            "needs_update": False
        }
        
        if existing_product:
            # تحديث المنتج الموجود
            for key, value in product_info.items():
                if key != "store_id":
                    setattr(existing_product, key, value)
        else:
            # إنشاء منتج جديد
            new_product = SallaProduct(**product_info)
            db.add(new_product)
        
        db.commit()
        
    except Exception as e:
        print(f"❌ Failed to save product: {e}")
        db.rollback()

async def handle_app_uninstalled(db: Session, merchant_id: str, data: dict):
    """معالجة إلغاء تثبيت التطبيق"""
    try:
        print(f"😢 App uninstalled for merchant: {merchant_id}")
        
        # البحث عن المتجر وتعطيله
        store = db.query(SallaStore).filter(
            SallaStore.store_id == merchant_id
        ).first()
        
        if store:
            store.store_status = "uninstalled"
            store.access_token = None
            store.refresh_token = None
            store.updated_at = datetime.utcnow()
            db.commit()
            print(f"✅ Store marked as uninstalled: {store.store_name}")
        else:
            print(f"⚠️ Store not found for merchant: {merchant_id}")
        
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
        
        # حفظ المنتج الجديد
        await save_product_to_database(db, product_data, store.id)
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
            return
        
        # حفظ أو تحديث المنتج
        await save_product_to_database(db, product_data, store.id)
        print(f"✅ Product updated successfully: {product_data.get('name')}")
        
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
            # تمييزه كمحذوف
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
                    await save_product_to_database(db, product_data, store.id)
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