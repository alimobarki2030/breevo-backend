# simple_make_admin.py - سكريبت مبسط لترقية المستخدم
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()

# الحصول على رابط قاعدة البيانات
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL غير موجود في ملف .env")
    exit(1)

def make_admin_direct(email: str):
    """ترقية المستخدم مباشرة عبر SQL"""
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # التحقق من وجود المستخدم
            result = conn.execute(
                text("SELECT id, email, full_name, is_admin FROM users WHERE email = :email"),
                {"email": email}
            ).fetchone()
            
            if not result:
                print(f"❌ المستخدم {email} غير موجود!")
                return False
            
            user_id = result[0]
            print(f"✅ تم العثور على المستخدم:")
            print(f"   - ID: {user_id}")
            print(f"   - Email: {result[1]}")
            print(f"   - Name: {result[2] or 'غير محدد'}")
            print(f"   - Is Admin: {result[3]}")
            
            # ترقية المستخدم
            conn.execute(
                text("""
                    UPDATE users 
                    SET is_admin = true,
                        is_subscribed = true,
                        subscription_tier = 'premium',
                        is_verified = true
                    WHERE email = :email
                """),
                {"email": email}
            )
            conn.commit()
            
            # التحقق من وجود سجل النقاط
            points_result = conn.execute(
                text("SELECT id, balance FROM user_points WHERE user_id = :user_id"),
                {"user_id": user_id}
            ).fetchone()
            
            if points_result:
                # تحديث النقاط الموجودة
                conn.execute(
                    text("""
                        UPDATE user_points 
                        SET balance = 1000000,
                            monthly_points = 100000,
                            monthly_points_used = 0,
                            total_purchased = 1000000,
                            total_bonus = 1000000
                        WHERE user_id = :user_id
                    """),
                    {"user_id": user_id}
                )
                print(f"✅ تم تحديث رصيد النقاط")
            else:
                # إنشاء سجل نقاط جديد
                conn.execute(
                    text("""
                        INSERT INTO user_points 
                        (user_id, balance, monthly_points, monthly_points_used, 
                         total_purchased, total_spent, total_refunded, total_bonus)
                        VALUES 
                        (:user_id, 1000000, 100000, 0, 1000000, 0, 0, 1000000)
                    """),
                    {"user_id": user_id}
                )
                print(f"✅ تم إنشاء رصيد نقاط جديد")
            
            conn.commit()
            
            print(f"\n🎉 تمت الترقية بنجاح!")
            print(f"   - Admin: ✓")
            print(f"   - Premium Subscription: ✓")
            print(f"   - Points: 1,000,000")
            print(f"   - Monthly Points: 100,000")
            
            return True
            
    except Exception as e:
        print(f"❌ خطأ: {str(e)}")
        return False
    finally:
        engine.dispose()

def check_database_tables():
    """فحص الجداول الموجودة"""
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # فحص جدول المستخدمين
            result = conn.execute(
                text("SELECT COUNT(*) FROM users")
            ).fetchone()
            print(f"✅ جدول users موجود - عدد المستخدمين: {result[0]}")
            
            # فحص جدول النقاط
            try:
                result = conn.execute(
                    text("SELECT COUNT(*) FROM user_points")
                ).fetchone()
                print(f"✅ جدول user_points موجود - عدد السجلات: {result[0]}")
            except:
                print(f"⚠️  جدول user_points غير موجود")
                
    except Exception as e:
        print(f"❌ خطأ في الاتصال بقاعدة البيانات: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 سكريبت ترقية المستخدم لـ Admin (مبسط)")
    print("=" * 50)
    
    # فحص قاعدة البيانات
    if not check_database_tables():
        exit(1)
    
    print("\n" + "=" * 50)
    
    # الإيميل المطلوب
    admin_email = "alimobarki.ad@gmail.com"
    
    # السؤال عن الترقية
    response = input(f"\nهل تريد ترقية {admin_email} إلى Admin؟ (y/n): ")
    
    if response.lower() == 'y':
        make_admin_direct(admin_email)
    else:
        print("❌ تم الإلغاء")