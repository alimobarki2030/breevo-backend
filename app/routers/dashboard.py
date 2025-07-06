# app/routers/dashboard.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

from app.database import get_db
from app.models.user import User
from app.models.salla import SallaStore, SallaProduct
from app.models.pending_store import PendingStore
from app.routers.auth import get_current_user

# إعداد logging
logger = logging.getLogger(__name__)

# إنشاء router
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """إحصائيات عامة للوحة التحكم"""
    try:
        # عدد المتاجر المربوطة
        total_stores = db.query(SallaStore).filter(
            SallaStore.user_id == current_user.id
        ).count()
        
        # عدد المتاجر النشطة
        active_stores = db.query(SallaStore).filter(
            SallaStore.user_id == current_user.id,
            SallaStore.store_status == "active"
        ).count()
        
        # إجمالي المنتجات
        total_products = db.query(SallaProduct).join(SallaStore).filter(
            SallaStore.user_id == current_user.id
        ).count()
        
        # المنتجات المحسّنة (لديها SEO title و description)
        optimized_products = db.query(SallaProduct).join(SallaStore).filter(
            SallaStore.user_id == current_user.id,
            SallaProduct.seo_title.isnot(None),
            SallaProduct.seo_description.isnot(None)
        ).count()
        
        # المنتجات التي تحتاج تحسين
        pending_optimization = total_products - optimized_products
        
        # متوسط نقاط SEO
        avg_seo_score = db.query(func.avg(SallaProduct.seo_score)).join(SallaStore).filter(
            SallaStore.user_id == current_user.id,
            SallaProduct.seo_score.isnot(None)
        ).scalar() or 0
        
        # نسبة التحسين
        optimization_rate = (optimized_products / total_products * 100) if total_products > 0 else 0
        
        # آخر مزامنة
        last_sync = db.query(func.max(SallaProduct.last_synced_at)).join(SallaStore).filter(
            SallaStore.user_id == current_user.id
        ).scalar()
        
        return {
            "stores": {
                "total": total_stores,
                "active": active_stores,
                "inactive": total_stores - active_stores
            },
            "products": {
                "total": total_products,
                "optimized": optimized_products,
                "pending_optimization": pending_optimization,
                "optimization_rate": round(optimization_rate, 2)
            },
            "seo": {
                "average_score": round(avg_seo_score, 2),
                "total_optimized": optimized_products,
                "needs_attention": pending_optimization
            },
            "last_sync": last_sync.isoformat() if last_sync else None,
            "user": {
                "name": current_user.full_name,
                "email": current_user.email,
                "plan": current_user.plan or "free"
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب الإحصائيات: {str(e)}")

@router.get("/recent-activity")
async def get_recent_activity(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """آخر النشاطات والتحديثات"""
    try:
        activities = []
        
        # آخر المنتجات المحدثة
        recent_products = db.query(SallaProduct).join(SallaStore).filter(
            SallaStore.user_id == current_user.id
        ).order_by(SallaProduct.updated_at.desc()).limit(limit).all()
        
        for product in recent_products:
            activity_type = "product_optimized" if product.seo_title else "product_added"
            activities.append({
                "id": f"product_{product.id}",
                "type": activity_type,
                "title": f"تحديث منتج: {product.name}",
                "description": f"في متجر {product.store.store_name}",
                "timestamp": product.updated_at.isoformat(),
                "icon": "📦",
                "link": f"/products/{product.id}"
            })
        
        # آخر المتاجر المربوطة
        recent_stores = db.query(SallaStore).filter(
            SallaStore.user_id == current_user.id
        ).order_by(SallaStore.created_at.desc()).limit(5).all()
        
        for store in recent_stores:
            activities.append({
                "id": f"store_{store.id}",
                "type": "store_connected",
                "title": f"ربط متجر: {store.store_name}",
                "description": f"تم ربط المتجر بنجاح",
                "timestamp": store.created_at.isoformat(),
                "icon": "🏪",
                "link": f"/stores/{store.id}"
            })
        
        # ترتيب حسب الوقت
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return activities[:limit]
        
    except Exception as e:
        logger.error(f"Error fetching recent activity: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب النشاطات: {str(e)}")

@router.get("/performance-metrics")
async def get_performance_metrics(
    period: str = "week",  # week, month, year
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """مقاييس الأداء والتحسن"""
    try:
        # حساب الفترة الزمنية
        end_date = datetime.utcnow()
        if period == "week":
            start_date = end_date - timedelta(days=7)
        elif period == "month":
            start_date = end_date - timedelta(days=30)
        elif period == "year":
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=30)
        
        # المنتجات المحسّنة خلال الفترة
        optimized_in_period = db.query(func.count(SallaProduct.id)).join(SallaStore).filter(
            SallaStore.user_id == current_user.id,
            SallaProduct.updated_at >= start_date,
            SallaProduct.seo_title.isnot(None)
        ).scalar() or 0
        
        # تحسن متوسط النقاط
        score_improvement = db.query(
            func.avg(
                case(
                    (SallaProduct.seo_score.isnot(None), SallaProduct.seo_score),
                    else_=0
                )
            )
        ).join(SallaStore).filter(
            SallaStore.user_id == current_user.id,
            SallaProduct.updated_at >= start_date
        ).scalar() or 0
        
        # الأداء اليومي
        daily_stats = []
        current_date = start_date
        while current_date <= end_date:
            next_date = current_date + timedelta(days=1)
            
            daily_optimized = db.query(func.count(SallaProduct.id)).join(SallaStore).filter(
                SallaStore.user_id == current_user.id,
                SallaProduct.updated_at >= current_date,
                SallaProduct.updated_at < next_date,
                SallaProduct.seo_title.isnot(None)
            ).scalar() or 0
            
            daily_stats.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "optimized": daily_optimized
            })
            
            current_date = next_date
        
        return {
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "metrics": {
                "products_optimized": optimized_in_period,
                "average_score_improvement": round(score_improvement, 2),
                "optimization_rate": round((optimized_in_period / 30) * 100, 2) if period == "month" else 0
            },
            "daily_stats": daily_stats,
            "trends": {
                "improving": score_improvement > 50,
                "message": "أداء ممتاز! استمر في التحسين" if score_improvement > 50 else "يمكن تحسين الأداء أكثر"
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching performance metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب مقاييس الأداء: {str(e)}")

@router.get("/stores-overview")
async def get_stores_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """نظرة عامة على المتاجر"""
    try:
        stores = db.query(SallaStore).filter(
            SallaStore.user_id == current_user.id
        ).all()
        
        stores_data = []
        for store in stores:
            # عدد منتجات كل متجر
            products_count = db.query(func.count(SallaProduct.id)).filter(
                SallaProduct.store_id == store.id
            ).scalar() or 0
            
            # المنتجات المحسّنة
            optimized_count = db.query(func.count(SallaProduct.id)).filter(
                SallaProduct.store_id == store.id,
                SallaProduct.seo_title.isnot(None)
            ).scalar() or 0
            
            # متوسط نقاط SEO للمتجر
            avg_score = db.query(func.avg(SallaProduct.seo_score)).filter(
                SallaProduct.store_id == store.id,
                SallaProduct.seo_score.isnot(None)
            ).scalar() or 0
            
            stores_data.append({
                "id": store.id,
                "name": store.store_name,
                "domain": store.store_domain,
                "status": store.store_status,
                "plan": store.store_plan,
                "connected_at": store.created_at.isoformat(),
                "last_sync": store.last_sync_at.isoformat() if store.last_sync_at else None,
                "stats": {
                    "total_products": products_count,
                    "optimized_products": optimized_count,
                    "optimization_rate": round((optimized_count / products_count * 100) if products_count > 0 else 0, 2),
                    "average_seo_score": round(avg_score, 2)
                }
            })
        
        return {
            "stores": stores_data,
            "summary": {
                "total_stores": len(stores),
                "active_stores": sum(1 for s in stores if s.store_status == "active"),
                "total_products": sum(s["stats"]["total_products"] for s in stores_data),
                "total_optimized": sum(s["stats"]["optimized_products"] for s in stores_data)
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching stores overview: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب نظرة عامة على المتاجر: {str(e)}")

@router.get("/top-products")
async def get_top_products(
    limit: int = 10,
    sort_by: str = "score",  # score, views, updates
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """أفضل المنتجات حسب معايير مختلفة"""
    try:
        query = db.query(SallaProduct).join(SallaStore).filter(
            SallaStore.user_id == current_user.id
        )
        
        if sort_by == "score":
            # أعلى نقاط SEO
            query = query.filter(SallaProduct.seo_score.isnot(None))
            query = query.order_by(SallaProduct.seo_score.desc())
        elif sort_by == "updates":
            # الأكثر تحديثاً
            query = query.order_by(SallaProduct.updated_at.desc())
        else:
            # افتراضياً حسب التحديث
            query = query.order_by(SallaProduct.updated_at.desc())
        
        products = query.limit(limit).all()
        
        products_data = []
        for product in products:
            products_data.append({
                "id": product.id,
                "name": product.name,
                "store_name": product.store.store_name,
                "seo_score": product.seo_score or 0,
                "status": product.status,
                "last_updated": product.updated_at.isoformat(),
                "has_seo": bool(product.seo_title and product.seo_description),
                "category": product.category_name
            })
        
        return {
            "products": products_data,
            "sort_by": sort_by,
            "count": len(products_data)
        }
        
    except Exception as e:
        logger.error(f"Error fetching top products: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب أفضل المنتجات: {str(e)}")

@router.get("/seo-issues")
async def get_seo_issues(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """المنتجات التي تحتاج لتحسين SEO"""
    try:
        # المنتجات بدون عنوان SEO
        no_seo_title = db.query(SallaProduct).join(SallaStore).filter(
            SallaStore.user_id == current_user.id,
            or_(
                SallaProduct.seo_title.is_(None),
                SallaProduct.seo_title == ""
            )
        ).limit(limit).all()
        
        # المنتجات بدون وصف SEO
        no_seo_desc = db.query(SallaProduct).join(SallaStore).filter(
            SallaStore.user_id == current_user.id,
            or_(
                SallaProduct.seo_description.is_(None),
                SallaProduct.seo_description == ""
            )
        ).limit(limit).all()
        
        # المنتجات بنقاط SEO منخفضة
        low_score = db.query(SallaProduct).join(SallaStore).filter(
            SallaStore.user_id == current_user.id,
            SallaProduct.seo_score < 50,
            SallaProduct.seo_score.isnot(None)
        ).limit(limit).all()
        
        issues = []
        
        # إضافة المشاكل
        for product in no_seo_title:
            issues.append({
                "product_id": product.id,
                "product_name": product.name,
                "store_name": product.store.store_name,
                "issue_type": "missing_seo_title",
                "severity": "high",
                "message": "عنوان SEO مفقود"
            })
        
        for product in no_seo_desc:
            # تجنب التكرار
            if not any(i["product_id"] == product.id for i in issues):
                issues.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "store_name": product.store.store_name,
                    "issue_type": "missing_seo_description",
                    "severity": "high",
                    "message": "وصف SEO مفقود"
                })
        
        for product in low_score:
            if not any(i["product_id"] == product.id for i in issues):
                issues.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "store_name": product.store.store_name,
                    "issue_type": "low_seo_score",
                    "severity": "medium",
                    "message": f"نقاط SEO منخفضة ({product.seo_score})"
                })
        
        # ترتيب حسب الأولوية
        issues.sort(key=lambda x: 0 if x["severity"] == "high" else 1)
        
        return {
            "issues": issues[:limit],
            "total_issues": len(issues),
            "summary": {
                "missing_titles": len(no_seo_title),
                "missing_descriptions": len(no_seo_desc),
                "low_scores": len(low_score)
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching SEO issues: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في جلب مشاكل SEO: {str(e)}")

@router.get("/quick-stats")
async def get_quick_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """إحصائيات سريعة للعرض في الـ Header"""
    try:
        # عدد المتاجر
        stores_count = db.query(func.count(SallaStore.id)).filter(
            SallaStore.user_id == current_user.id
        ).scalar() or 0
        
        # عدد المنتجات
        products_count = db.query(func.count(SallaProduct.id)).join(SallaStore).filter(
            SallaStore.user_id == current_user.id
        ).scalar() or 0
        
        # المنتجات المحسّنة اليوم
        today_optimized = db.query(func.count(SallaProduct.id)).join(SallaStore).filter(
            SallaStore.user_id == current_user.id,
            SallaProduct.updated_at >= datetime.utcnow().date(),
            SallaProduct.seo_title.isnot(None)
        ).scalar() or 0
        
        return {
            "stores": stores_count,
            "products": products_count,
            "optimized_today": today_optimized,
            "user_plan": current_user.plan or "free"
        }
        
    except Exception as e:
        logger.error(f"Error fetching quick stats: {str(e)}")
        return {
            "stores": 0,
            "products": 0,
            "optimized_today": 0,
            "user_plan": "free"
        }