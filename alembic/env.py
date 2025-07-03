import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# تحميل متغيرات البيئة
from dotenv import load_dotenv
load_dotenv()

# ✅ إصلاح مسار Python للتعامل مع مجلد app
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

# إضافة مسار المشروع الرئيسي
sys.path.insert(0, project_root)
# ✅ إضافة مسار مجلد app 
app_path = os.path.join(project_root, 'app')
sys.path.insert(0, app_path)

print(f"🔍 Alembic directory: {current_dir}")
print(f"🔍 Project root: {project_root}")
print(f"🔍 App path: {app_path}")
print(f"🔍 Python path first 3: {sys.path[:3]}")

# فحص محتويات مجلد app
if os.path.exists(app_path):
    print(f"📁 محتويات مجلد app: {os.listdir(app_path)}")
else:
    print("❌ مجلد app غير موجود!")

# محاولة استيراد النماذج مع معالجة شاملة للأخطاء
try:
    print("🔄 محاولة استيراد النماذج من مجلد app...")
    
    # ✅ استيراد من مجلد app
    from app.database import Base
    print("✅ تم استيراد Base من app.database")
    
    # استيراد النماذج من app
    from app.models.user import User
    print("✅ تم استيراد User من app.models")
    
    from app.models.salla import SallaStore, SallaProduct  
    print("✅ تم استيراد SallaStore و SallaProduct من app.models")
    
    print("🎉 تم تحميل جميع النماذج بنجاح!")
    
except ImportError as e:
    print(f"❌ خطأ في استيراد النماذج من app: {e}")
    
    # محاولة بديلة - بدون مجلد app
    try:
        print("🔄 محاولة استيراد بدون مجلد app...")
        from database import Base
        from models.user import User
        from models.salla import SallaStore, SallaProduct
        print("✅ تم الاستيراد بدون مجلد app")
    except ImportError as e2:
        print(f"❌ خطأ في الاستيراد البديل أيضاً: {e2}")
        
        # إنشاء Base مؤقت كحل أخير
        from sqlalchemy.ext.declarative import declarative_base
        Base = declarative_base()
        print("⚠️ تم إنشاء Base مؤقت - تحقق من مسار ملفات النماذج")

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    if url is None:
        url = os.getenv("DATABASE_URL")
        if url is None:
            url = "sqlite:///./breevo.db"  # ✅ استخدام اسم قاعدة البيانات الصحيح
    
    print(f"🔗 Database URL: {url}")
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    config_section = config.get_section(config.config_ini_section, {})
    
    # إضافة DATABASE_URL إذا لم يكن موجود
    if "sqlalchemy.url" not in config_section or not config_section["sqlalchemy.url"]:
        database_url = os.getenv("DATABASE_URL", "sqlite:///./breevo.db")
        config_section["sqlalchemy.url"] = database_url
        print(f"🔗 Using DATABASE_URL: {database_url}")
    
    connectable = engine_from_config(
        config_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()