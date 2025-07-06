# app/scripts/run_migration.py
from sqlalchemy import create_engine, text
from app.database import DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_seo_fields():
    """إضافة حقول SEO الجديدة لجدول المنتجات"""
    engine = create_engine(DATABASE_URL)
    
    with engine.begin() as conn:  # تغيير مهم: begin() بدلاً من connect()
        try:
            # التحقق من وجود الحقول أولاً
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='salla_products' 
                AND column_name IN ('seo_score', 'optimization_status', 'keywords', 'meta_tags')
            """))
            
            existing_columns = [row[0] for row in result]
            
            # إضافة الحقول غير الموجودة
            if 'seo_score' not in existing_columns:
                conn.execute(text("ALTER TABLE salla_products ADD COLUMN seo_score INTEGER DEFAULT 0"))
                logger.info("✅ Added seo_score column")
            else:
                logger.info("ℹ️ seo_score column already exists")
            
            if 'optimization_status' not in existing_columns:
                conn.execute(text("ALTER TABLE salla_products ADD COLUMN optimization_status VARCHAR DEFAULT 'pending'"))
                logger.info("✅ Added optimization_status column")
            else:
                logger.info("ℹ️ optimization_status column already exists")
            
            if 'keywords' not in existing_columns:
                conn.execute(text("ALTER TABLE salla_products ADD COLUMN keywords JSON"))
                logger.info("✅ Added keywords column")
            else:
                logger.info("ℹ️ keywords column already exists")
            
            if 'meta_tags' not in existing_columns:
                conn.execute(text("ALTER TABLE salla_products ADD COLUMN meta_tags JSON"))
                logger.info("✅ Added meta_tags column")
            else:
                logger.info("ℹ️ meta_tags column already exists")
            
            logger.info("✅ Migration completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Error during migration: {str(e)}")
            raise

def check_columns():
    """التحقق من الحقول الموجودة"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            # جلب جميع الأعمدة
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name='salla_products'
                ORDER BY ordinal_position
            """))
            
            logger.info("\n📊 Current columns in salla_products table:")
            for col_name, data_type in result:
                logger.info(f"   - {col_name} ({data_type})")
                
        except Exception as e:
            logger.error(f"Error checking columns: {str(e)}")

if __name__ == "__main__":
    logger.info("🔧 Starting migration...")
    add_seo_fields()
    logger.info("\n📋 Verifying migration...")
    check_columns()