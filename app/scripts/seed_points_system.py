# app/scripts/seed_points_system.py
"""
سكريبت لتهيئة نظام النقاط بالبيانات الأولية
يتم تشغيله مرة واحدة عند تثبيت النظام
"""

from sqlalchemy.orm import Session
from app.database import engine, SessionLocal
from app.models.points import (
    PointPackage, ServicePricing, ServiceType
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_point_packages(db: Session):
    """إضافة باقات النقاط الأساسية"""
    packages = [
        {
            "name": "حزمة صغيرة",
            "points": 500,
            "price": 29,
            "original_price": 35,
            "is_popular": False,
            "discount_percentage": 17,
            "promo_text": "وفر 17%",
            "sort_order": 1
        },
        {
            "name": "حزمة متوسطة",
            "points": 1000,
            "price": 49,
            "original_price": 60,
            "is_popular": False,
            "discount_percentage": 18,
            "promo_text": "وفر 18%",
            "sort_order": 2
        },
        {
            "name": "حزمة كبيرة",
            "points": 3000,
            "price": 99,
            "original_price": 150,
            "is_popular": True,
            "discount_percentage": 34,
            "promo_text": "الأكثر توفيراً - وفر 34%",
            "sort_order": 3
        },
        {
            "name": "حزمة ضخمة",
            "points": 10000,
            "price": 299,
            "original_price": 500,
            "is_popular": False,
            "discount_percentage": 40,
            "promo_text": "وفر 40%",
            "sort_order": 4
        }
    ]
    
    for package_data in packages:
        # التحقق من عدم وجود الباقة
        existing = db.query(PointPackage).filter(
            PointPackage.name == package_data["name"]
        ).first()
        
        if not existing:
            package = PointPackage(**package_data)
            db.add(package)
            logger.info(f"Added package: {package_data['name']}")
        else:
            logger.info(f"Package already exists: {package_data['name']}")
    
    db.commit()

def seed_service_pricing(db: Session):
    """إضافة أسعار الخدمات بالنقاط"""
    services = [
        {
            "service_type": ServiceType.SEO_ANALYSIS,
            "name": "تحليل SEO أساسي",
            "description": "تحليل شامل لحالة SEO للمنتج مع تقرير مفصل",
            "points_cost": 20,
            "category": "تحليل",
            "icon": "📊",
            "estimated_time": "فوري",
            "min_plan": "free"
        },
        {
            "service_type": ServiceType.SEO_OPTIMIZATION,
            "name": "تحليل SEO عميق",
            "description": "تحليل متقدم مع مقترحات تحسين مفصلة",
            "points_cost": 50,
            "category": "تحليل",
            "icon": "🔍",
            "estimated_time": "2-3 دقائق",
            "min_plan": "free"
        },
        {
            "service_type": ServiceType.AI_DESCRIPTION,
            "name": "توليد وصف بسيط",
            "description": "وصف احترافي للمنتج بالذكاء الاصطناعي",
            "points_cost": 10,
            "category": "محتوى",
            "icon": "✍️",
            "estimated_time": "30 ثانية",
            "min_plan": "free"
        },
        {
            "service_type": ServiceType.KEYWORD_RESEARCH,
            "name": "بحث كلمات مفتاحية",
            "description": "اكتشاف أفضل الكلمات المفتاحية للمنتج",
            "points_cost": 30,
            "category": "بحث",
            "icon": "🔑",
            "estimated_time": "1-2 دقيقة",
            "min_plan": "free"
        },
        {
            "service_type": ServiceType.COMPETITOR_ANALYSIS,
            "name": "تحليل المنافسين",
            "description": "دراسة استراتيجيات المنافسين وكلماتهم المفتاحية",
            "points_cost": 75,
            "category": "تحليل متقدم",
            "icon": "🎯",
            "estimated_time": "3-5 دقائق",
            "min_plan": "pro"
        },
        {
            "service_type": ServiceType.BULK_OPTIMIZATION,
            "name": "باقة كاملة (وصف + SEO + كلمات)",
            "description": "حزمة شاملة لتحسين المنتج بالكامل",
            "points_cost": 100,
            "category": "حزم",
            "icon": "📦",
            "estimated_time": "5-7 دقائق",
            "min_plan": "free"
        },
        {
            "service_type": ServiceType.STORE_SYNC,
            "name": "مزامنة متجر كامل",
            "description": "مزامنة وتحليل جميع منتجات المتجر",
            "points_cost": 200,
            "category": "متجر",
            "icon": "🏪",
            "estimated_time": "10-15 دقيقة",
            "min_plan": "business"
        },
        {
            "service_type": ServiceType.MONTHLY_REPORT,
            "name": "تقرير شهري مفصل",
            "description": "تقرير شامل عن أداء SEO لجميع المنتجات",
            "points_cost": 150,
            "category": "تقارير",
            "icon": "📈",
            "estimated_time": "24 ساعة",
            "min_plan": "pro"
        }
    ]
    
    for service_data in services:
        # التحقق من عدم وجود الخدمة
        existing = db.query(ServicePricing).filter(
            ServicePricing.service_type == service_data["service_type"]
        ).first()
        
        if not existing:
            service = ServicePricing(**service_data)
            db.add(service)
            logger.info(f"Added service: {service_data['name']}")
        else:
            # تحديث السعر إذا تغير
            existing.points_cost = service_data["points_cost"]
            existing.description = service_data["description"]
            existing.estimated_time = service_data["estimated_time"]
            logger.info(f"Updated service: {service_data['name']}")
    
    db.commit()

def update_user_model():
    """تحديث نموذج المستخدم لإضافة العلاقة مع نظام النقاط"""
    update_code = """
# في ملف app/models/user.py، أضف هذا السطر في class User:
points_account = relationship("UserPoints", back_populates="user", uselist=False)
"""
    logger.info("User model update required:")
    logger.info(update_code)

def main():
    """تشغيل جميع عمليات التهيئة"""
    logger.info("Starting points system initialization...")
    
    # إنشاء جلسة قاعدة البيانات
    db = SessionLocal()
    
    try:
        # إضافة باقات النقاط
        logger.info("Seeding point packages...")
        seed_point_packages(db)
        
        # إضافة أسعار الخدمات
        logger.info("Seeding service pricing...")
        seed_service_pricing(db)
        
        # تذكير بتحديث نموذج المستخدم
        update_user_model()
        
        logger.info("Points system initialization completed successfully!")
        
        # عرض ملخص
        packages_count = db.query(PointPackage).count()
        services_count = db.query(ServicePricing).count()
        
        logger.info(f"\nSummary:")
        logger.info(f"- Point packages: {packages_count}")
        logger.info(f"- Service types: {services_count}")
        
    except Exception as e:
        logger.error(f"Error during initialization: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()