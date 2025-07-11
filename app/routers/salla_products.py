# app/routers/salla_products.py
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, Float  # أضفنا Float هنا
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.salla import SallaStore, SallaProduct
from app.routers.auth import get_current_user
from app.services.salla_api import SallaAPIService
from app.services.ai_service import AIService

# إعداد logging
logger = logging.getLogger(__name__)

# إنشاء router
router = APIRouter(prefix="/api/products", tags=["products"])
salla_service = SallaAPIService()
ai_service = AIService()

# ===== Pydantic Models =====

class ProductResponse(BaseModel):
    id: int
    salla_product_id: str
    name: str
    description: Optional[str]
    price: Dict[str, Any]
    sku: Optional[str]
    category_name: Optional[str]
    images: List[str]
    seo_title: Optional[str]
    seo_description: Optional[str]
    status: str
    seo_score: Optional[int] = None
    optimization_status: Optional[str] = "pending"
    store: Dict[str, Any]
    last_synced_at: datetime
    
    class Config:
        orm_mode = True = True  # ✅ محدث

class SEOUpdateRequest(BaseModel):
    seo_title: str
    seo_description: str
    keywords: Optional[List[str]] = []
    meta_tags: Optional[Dict[str, str]] = {}

class ProductsListResponse(BaseModel):
    products: List[ProductResponse]
    pagination: Dict[str, int]
    filters_applied: Dict[str, Any]

class SEOAnalysisResponse(BaseModel):
    product_id: int
    current_score: int
    issues: List[Dict[str, Any]]
    suggestions: List[Dict[str, Any]]
    competitor_analysis: Optional[Dict[str, Any]]
    keywords_analysis: Optional[Dict[str, Any]]

class BulkOperationRequest(BaseModel):
    product_ids: List[int]
    operation: str  # "analyze", "optimize", "sync"

# ===== Endpoints =====

@router.get("/", response_model=ProductsListResponse)
async def get_user_products(
    store_id: Optional[int] = Query(None, description="فلترة حسب المتجر"),
    search: Optional[str] = Query(None, description="البحث في الاسم والوصف"),
    status: Optional[str] = Query(None, description="حالة المنتج"),
    optimization_status: Optional[str] = Query(None, description="حالة التحسين"),
    category: Optional[str] = Query(None, description="التصنيف"),
    min_price: Optional[float] = Query(None, description="السعر الأدنى"),
    max_price: Optional[float] = Query(None, description="السعر الأعلى"),
    sort_by: Optional[str] = Query("updated_at", description="ترتيب حسب"),
    sort_order: Optional[str] = Query("desc", description="اتجاه الترتيب"),
    page: int = Query(1, ge=1, description="رقم الصفحة"),
    per_page: int = Query(20, ge=1, le=100, description="عدد العناصر"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """جلب منتجات المستخدم من جميع متاجره مع خيارات متقدمة للفلترة والترتيب"""
    try:
        # بناء الاستعلام الأساسي
        query = db.query(SallaProduct).join(SallaStore).filter(
            SallaStore.user_id == current_user.id
        )
        
        # تطبيق الفلاتر
        filters_applied = {}
        
        if store_id:
            query = query.filter(SallaProduct.store_id == store_id)
            filters_applied["store_id"] = store_id
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    SallaProduct.name.ilike(search_pattern),
                    SallaProduct.description.ilike(search_pattern),
                    SallaProduct.sku.ilike(search_pattern)
                )
            )
            filters_applied["search"] = search
        
        if status:
            query = query.filter(SallaProduct.status == status)
            filters_applied["status"] = status
        
        if category:
            query = query.filter(SallaProduct.category_name.ilike(f"%{category}%"))
            filters_applied["category"] = category
        
        if min_price is not None:
            query = query.filter(func.cast(SallaProduct.price_amount, Float) >= min_price)
            filters_applied["min_price"] = min_price
        
        if max_price is not None:
            query = query.filter(func.cast(SallaProduct.price_amount, Float) <= max_price)
            filters_applied["max_price"] = max_price
        
        # حساب الإجمالي قبل التقسيم
        total = query.count()
        
        # تطبيق الترتيب
        if sort_by == "name":
            order_column = SallaProduct.name
        elif sort_by == "price":
            order_column = func.cast(SallaProduct.price_amount, Float)
        elif sort_by == "status":
            order_column = SallaProduct.status
        elif sort_by == "seo_score":
            order_column = SallaProduct.seo_score
        else:
            order_column = SallaProduct.updated_at
        
        if sort_order == "asc":
            query = query.order_by(order_column.asc())
        else:
            query = query.order_by(order_column.desc())
        
        # تطبيق التقسيم
        products = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # تحضير النتائج
        products_list = []
        for product in products:
            product_dict = {
                "id": product.id,
                "salla_product_id": product.salla_product_id,
                "name": product.name,
                "description": product.description,
                "price": {
                    "amount": product.price_amount,
                    "currency": product.price_currency
                },
                "sku": product.sku,
                "category_name": product.category_name,
                "images": product.images or [],
                "seo_title": product.seo_title,
                "seo_description": product.seo_description,
                "status": product.status,
                "seo_score": getattr(product, 'seo_score', None),
                "optimization_status": getattr(product, 'optimization_status', 'pending'),
                "store": {
                    "id": product.store.id,
                    "name": product.store.store_name,
                    "domain": product.store.store_domain
                },
                "last_synced_at": product.last_synced_at
            }
            products_list.append(ProductResponse(**product_dict))
        
        return ProductsListResponse(
            products=products_list,
            pagination={
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page,
                "has_next": page * per_page < total,
                "has_prev": page > 1
            },
            filters_applied=filters_applied
        )
        
    except Exception as e:
        logger.error(f"Error fetching products: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب المنتجات: {str(e)}")

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product_details(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """جلب تفاصيل منتج واحد"""
    product = db.query(SallaProduct).join(SallaStore).filter(
        SallaProduct.id == product_id,
        SallaStore.user_id == current_user.id
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="المنتج غير موجود")
    
    return ProductResponse(
        id=product.id,
        salla_product_id=product.salla_product_id,
        name=product.name,
        description=product.description,
        price={
            "amount": product.price_amount,
            "currency": product.price_currency
        },
        sku=product.sku,
        category_name=product.category_name,
        images=product.images or [],
        seo_title=product.seo_title,
        seo_description=product.seo_description,
        status=product.status,
        seo_score=getattr(product, 'seo_score', None),
        optimization_status=getattr(product, 'optimization_status', 'pending'),
        store={
            "id": product.store.id,
            "name": product.store.store_name,
            "domain": product.store.store_domain
        },
        last_synced_at=product.last_synced_at
    )

@router.get("/{product_id}/seo-analysis", response_model=SEOAnalysisResponse)
async def analyze_product_seo(
    product_id: int,
    include_competitors: bool = Query(False, description="تضمين تحليل المنافسين"),
    include_keywords: bool = Query(False, description="تضمين تحليل الكلمات المفتاحية"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """تحليل SEO للمنتج"""
    # التحقق من ملكية المنتج
    product = db.query(SallaProduct).join(SallaStore).filter(
        SallaProduct.id == product_id,
        SallaStore.user_id == current_user.id
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="المنتج غير موجود")
    
    try:
        # تحليل SEO الأساسي
        analysis = ai_service.analyze_product_seo(product)
        
        # تحليل المنافسين (اختياري)
        competitor_analysis = None
        if include_competitors and product.category_name:
            # هنا يمكن استخدام DataForSEO API
            competitor_analysis = {
                "message": "تحليل المنافسين سيكون متاحاً قريباً"
            }
        
        # تحليل الكلمات المفتاحية (اختياري)
        keywords_analysis = None
        if include_keywords:
            # هنا يمكن استخدام DataForSEO API
            keywords_analysis = {
                "message": "تحليل الكلمات المفتاحية سيكون متاحاً قريباً"
            }
        
        return SEOAnalysisResponse(
            product_id=product_id,
            current_score=analysis["score"],
            issues=analysis["issues"],
            suggestions=analysis["suggestions"],
            competitor_analysis=competitor_analysis,
            keywords_analysis=keywords_analysis
        )
        
    except Exception as e:
        logger.error(f"Error analyzing product SEO: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في تحليل SEO: {str(e)}")

@router.put("/{product_id}/seo")
async def update_product_seo(
    product_id: int,
    seo_data: SEOUpdateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """تحديث بيانات SEO للمنتج"""
    # التحقق من ملكية المنتج
    product = db.query(SallaProduct).join(SallaStore).filter(
        SallaProduct.id == product_id,
        SallaStore.user_id == current_user.id
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="المنتج غير موجود")
    
    try:
        # تحديث في قاعدة البيانات المحلية
        product.seo_title = seo_data.seo_title
        product.seo_description = seo_data.seo_description
        product.needs_update = True
        product.updated_at = datetime.utcnow()
        
        db.commit()
        
        # جدولة تحديث في سلة (في الخلفية)
        background_tasks.add_task(
            update_product_in_salla,
            product.store.access_token,
            product.salla_product_id,
            seo_data.dict()
        )
        
        return {
            "success": True,
            "message": "تم تحديث بيانات SEO بنجاح",
            "product_id": product_id
        }
        
    except Exception as e:
        logger.error(f"Error updating product SEO: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في تحديث SEO: {str(e)}")

@router.post("/bulk-operation")
async def bulk_product_operation(
    request: BulkOperationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """عمليات جماعية على المنتجات"""
    # التحقق من ملكية المنتجات
    products = db.query(SallaProduct).join(SallaStore).filter(
        SallaProduct.id.in_(request.product_ids),
        SallaStore.user_id == current_user.id
    ).all()
    
    if len(products) != len(request.product_ids):
        raise HTTPException(status_code=400, detail="بعض المنتجات غير موجودة أو لا تملك صلاحية الوصول إليها")
    
    if request.operation == "analyze":
        # جدولة تحليل SEO للمنتجات
        background_tasks.add_task(bulk_analyze_products, products, db)
        message = f"بدأ تحليل SEO لـ {len(products)} منتج"
        
    elif request.operation == "optimize":
        # جدولة تحسين SEO بالذكاء الاصطناعي
        background_tasks.add_task(bulk_optimize_products, products, db)
        message = f"بدأ تحسين SEO لـ {len(products)} منتج"
        
    elif request.operation == "sync":
        # جدولة مزامنة مع سلة
        background_tasks.add_task(bulk_sync_products, products, db)
        message = f"بدأت مزامنة {len(products)} منتج مع سلة"
        
    else:
        raise HTTPException(status_code=400, detail="عملية غير مدعومة")
    
    return {
        "success": True,
        "message": message,
        "products_count": len(products)
    }

@router.get("/stats/overview")
async def get_products_stats(
    store_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """إحصائيات المنتجات"""
    query = db.query(SallaProduct).join(SallaStore).filter(
        SallaStore.user_id == current_user.id
    )
    
    if store_id:
        query = query.filter(SallaProduct.store_id == store_id)
    
    total_products = query.count()
    
    # إحصائيات حسب الحالة
    status_stats = {}
    for status in ["sale", "out", "hidden", "deleted"]:
        count = query.filter(SallaProduct.status == status).count()
        status_stats[status] = count
    
    # إحصائيات SEO
    optimized_count = query.filter(SallaProduct.seo_title.isnot(None)).count()
    needs_optimization = total_products - optimized_count
    
    # متوسط نقاط SEO (إذا كان متاحاً)
    avg_seo_score = db.query(func.avg(SallaProduct.seo_score)).filter(
        SallaProduct.store_id.in_(
            db.query(SallaStore.id).filter(SallaStore.user_id == current_user.id)
        ),
        SallaProduct.seo_score.isnot(None)
    ).scalar() or 0
    
    return {
        "total_products": total_products,
        "status_breakdown": status_stats,
        "seo_stats": {
            "optimized": optimized_count,
            "needs_optimization": needs_optimization,
            "average_score": round(avg_seo_score, 2)
        },
        "last_sync": query.order_by(SallaProduct.last_synced_at.desc()).first().last_synced_at if total_products > 0 else None
    }

# ===== مهام الخلفية =====

async def update_product_in_salla(access_token: str, product_id: str, seo_data: dict):
    """تحديث المنتج في سلة"""
    try:
        # إعداد البيانات للتحديث في سلة
        update_data = {
            "metadata": {
                "title": seo_data.get("seo_title"),
                "description": seo_data.get("seo_description")
            }
        }
        
        # إضافة الكلمات المفتاحية إذا وجدت
        if seo_data.get("keywords"):
            update_data["tags"] = seo_data["keywords"]
        
        # استدعاء API سلة
        result = await salla_service.update_product(access_token, product_id, update_data)
        
        if result.get("status") == 200:
            logger.info(f"Product {product_id} updated successfully in Salla")
        else:
            logger.error(f"Failed to update product {product_id} in Salla: {result}")
            
    except Exception as e:
        logger.error(f"Error updating product in Salla: {str(e)}")

async def bulk_analyze_products(products: List[SallaProduct], db: Session):
    """تحليل SEO لمجموعة منتجات"""
    try:
        for product in products:
            analysis = ai_service.analyze_product_seo(product)
            product.seo_score = analysis["score"]
            product.optimization_status = "analyzed"
        
        db.commit()
        logger.info(f"Analyzed SEO for {len(products)} products")
        
    except Exception as e:
        logger.error(f"Error in bulk analysis: {str(e)}")
        db.rollback()

async def bulk_optimize_products(products: List[SallaProduct], db: Session):
    """تحسين SEO لمجموعة منتجات بالذكاء الاصطناعي"""
    try:
        for product in products:
            optimized_data = await ai_service.optimize_product_seo(product)
            
            product.seo_title = optimized_data["seo_title"]
            product.seo_description = optimized_data["seo_description"]
            product.optimization_status = "optimized"
            product.needs_update = True
        
        db.commit()
        logger.info(f"Optimized SEO for {len(products)} products")
        
    except Exception as e:
        logger.error(f"Error in bulk optimization: {str(e)}")
        db.rollback()

async def bulk_sync_products(products: List[SallaProduct], db: Session):
    """مزامنة مجموعة منتجات مع سلة"""
    try:
        # تجميع المنتجات حسب المتجر
        stores_products = {}
        for product in products:
            if product.store_id not in stores_products:
                stores_products[product.store_id] = []
            stores_products[product.store_id].append(product)
        
        # مزامنة كل متجر
        for store_id, store_products in stores_products.items():
            store = db.query(SallaStore).filter(SallaStore.id == store_id).first()
            if store and store.access_token:
                for product in store_products:
                    if product.needs_update:
                        await update_product_in_salla(
                            store.access_token,
                            product.salla_product_id,
                            {
                                "seo_title": product.seo_title,
                                "seo_description": product.seo_description
                            }
                        )
                        product.needs_update = False
                        product.last_synced_at = datetime.utcnow()
        
        db.commit()
        logger.info(f"Synced {len(products)} products with Salla")
        
    except Exception as e:
        logger.error(f"Error in bulk sync: {str(e)}")
        db.rollback()