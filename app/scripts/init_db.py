# scripts/init_db.py
"""
سكريبت إنشاء وإعداد قاعدة البيانات
"""
import sys
import os
from pathlib import Path

# إضافة مسار المشروع للاستيراد
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def create_tables():
    """إنشاء جداول قاعدة البيانات"""
    try:
        print("⏳ استيراد المكتبات...")
        from database import engine
        from models import Base
        
        print("⏳ إنشاء جداول قاعدة البيانات...")
        Base.metadata.create_all(bind=engine)
        print("✅ تم إنشاء الجداول بنجاح!")
        return True
    except Exception as e:
        print(f"❌ خطأ في إنشاء الجداول: {e}")
        return False

def create_admin_user():
    """إنشاء مستخدم admin افتراضي"""
    try:
        print("⏳ محاولة إنشاء مستخدم admin...")
        from database import SessionLocal
        from app.models.user import User
        from app.services.auth_service import auth_service
        
        db = SessionLocal()
        try:
            # التحقق من وجود مستخدم admin
            admin_email = "admin@example.com"
            existing_admin = db.query(User).filter(User.email == admin_email).first()
            
            if existing_admin:
                print(f"ℹ️ مستخدم المدير موجود بالفعل: {admin_email}")
                return True
            
            # إنشاء مستخدم admin جديد
            admin_data = {
                "full_name": "مدير النظام",
                "email": admin_email,
                "password": "admin123",  # يجب تغييرها لاحقاً
                "phone": "+966500000000",
                "store_url": "https://admin-store.com",
                "plan": "premium"
            }
            
            admin_user = auth_service.create_user(db, admin_data)
            
            print(f"✅ تم إنشاء مستخدم المدير: {admin_email}")
            print(f"🔑 كلمة المرور الافتراضية: admin123 (يرجى تغييرها)")
            return True
            
        except Exception as e:
            print(f"❌ خطأ في إنشاء مستخدم المدير: {e}")
            db.rollback()
            return False
        finally:
            db.close()
            
    except ImportError as e:
        print(f"⚠️ تعذر استيراد خدمة المصادقة: {e}")
        print("ℹ️ سيتم تخطي إنشاء المستخدم الافتراضي")
        return False

def check_database_connection():
    """فحص الاتصال بقاعدة البيانات"""
    try:
        from database import SessionLocal
        
        db = SessionLocal()
        # محاولة استعلام بسيط
        result = db.execute("SELECT 1").fetchone()
        db.close()
        print("✅ الاتصال بقاعدة البيانات يعمل بشكل صحيح")
        return True
    except Exception as e:
        print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
        return False

def display_tables_info():
    """عرض معلومات الجداول المنشأة"""
    try:
        from database import engine
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"\n📊 تم إنشاء {len(tables)} جدول:")
        for table in tables:
            columns = inspector.get_columns(table)
            print(f"  • {table} ({len(columns)} عمود)")
        
        return True
    except Exception as e:
        print(f"❌ خطأ في عرض معلومات الجداول: {e}")
        return False

def main():
    """الدالة الرئيسية"""
    print("🚀 إعداد قاعدة البيانات")
    print("=" * 40)
    
    # 1. فحص الاتصال
    if not check_database_connection():
        print("❌ فشل في الاتصال بقاعدة البيانات")
        return False
    
    # 2. إنشاء الجداول
    if not create_tables():
        print("❌ فشل في إنشاء الجداول")
        return False
    
    # 3. عرض معلومات الجداول
    display_tables_info()
    
    # 4. إنشاء مستخدم admin
    if not create_admin_user():
        print("⚠️ تحذير: فشل في إنشاء مستخدم المدير")
    
    print("\n" + "=" * 40)
    print("✅ تم إعداد قاعدة البيانات بنجاح!")
    print("\n📋 الخطوات التالية:")
    print("1. تشغيل الخادم: uvicorn main:app --reload")
    print("2. زيارة التوثيق: http://localhost:8000/docs")
    print("3. تسجيل الدخول كمدير أو إنشاء حساب جديد")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)