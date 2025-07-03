
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import uuid
import os
from datetime import datetime, timedelta

from app.database import get_db
from models.user import User
from models.salla import SallaStore, SallaProduct
from services.salla_api import SallaAPIService
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
                    product_info = {
                        "store_id": store.id,
                        "salla_product_id": str(product_data["id"]),
                        "name": product_data.get("name", ""),
                        "description": product_data.get("description", ""),
                        "sku": product_data.get("sku", ""),
                        "url_slug": product_data.get("url", ""),
                        "price_amount": str(product_data.get("price", {}).get("amount", 0)),
                        "price_currency": product_data.get("price", {}).get("currency", "SAR"),
                        "category_id": str(product_data.get("category", {}).get("id", "")),
                        "category_name": product_data.get("category", {}).get("name", ""),
                        "images": product_data.get("images", []),
                        "seo_title": product_data.get("metadata", {}).get("title", ""),
                        "seo_description": product_data.get("metadata", {}).get("description", ""),
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