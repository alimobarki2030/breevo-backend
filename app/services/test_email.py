# test_email.py - سكريبت اختبار إعدادات الإيميل
import asyncio
import os
from email_service import email_service, test_email_connection

async def test_email_setup():
    """اختبار شامل لإعدادات الإيميل"""
    
    print("🔍 بدء اختبار إعدادات الإيميل...")
    print("=" * 50)
    
    # 1️⃣ فحص متغيرات البيئة
    print("📋 فحص متغيرات البيئة:")
    required_vars = {
        'ZOHO_EMAIL_USERNAME': os.getenv('ZOHO_EMAIL_USERNAME'),
        'ZOHO_EMAIL_PASSWORD': os.getenv('ZOHO_EMAIL_PASSWORD'),
        'FROM_EMAIL': os.getenv('FROM_EMAIL'),
        'FROM_NAME': os.getenv('FROM_NAME')
    }
    
    all_good = True
    for var_name, var_value in required_vars.items():
        if var_value:
            # إخفاء كلمة المرور جزئياً
            if 'PASSWORD' in var_name:
                display_value = f"{var_value[:3]}***{var_value[-3:]}" if len(var_value) > 6 else "***"
            else:
                display_value = var_value
            print(f"   ✅ {var_name}: {display_value}")
        else:
            print(f"   ❌ {var_name}: غير محدد")
            all_good = False
    
    if not all_good:
        print("\n❌ بعض المتغيرات المطلوبة غير محددة!")
        print("💡 تحقق من ملف .env أو متغيرات البيئة")
        return False
    
    # 2️⃣ اختبار الاتصال
    print(f"\n🔌 اختبار الاتصال بخادم SMTP...")
    try:
        connection_success = await test_email_connection()
        if connection_success:
            print("   ✅ الاتصال نجح!")
        else:
            print("   ❌ فشل الاتصال!")
            return False
    except Exception as e:
        print(f"   ❌ خطأ في الاتصال: {str(e)}")
        return False
    
    # 3️⃣ اختبار إرسال إيميل
    print(f"\n📧 اختبار إرسال إيميل...")
    test_email = input("أدخل إيميل الاختبار (أو اتركه فارغ للتخطي): ").strip()
    
    if test_email:
        try:
            success = await email_service.send_email_with_retry(
                to_email=test_email,
                subject="🧪 اختبار إعدادات الإيميل",
                html_content="""
                <div style="font-family: Arial, sans-serif; text-align: center; padding: 20px;">
                    <h2>🎉 نجح الاختبار!</h2>
                    <p>تم إرسال هذا الإيميل لاختبار إعدادات Zoho SMTP</p>
                    <p>إذا وصلك هذا الإيميل، فإن الإعدادات تعمل بشكل صحيح ✅</p>
                    <hr>
                    <small>إيميل تلقائي من نظام اختبار الإيميل</small>
                </div>
                """,
                text_content="نجح اختبار الإيميل! الإعدادات تعمل بشكل صحيح."
            )
            
            if success:
                print("   ✅ تم إرسال إيميل الاختبار بنجاح!")
                print(f"   📩 تحقق من صندوق الوارد لـ {test_email}")
            else:
                print("   ❌ فشل إرسال إيميل الاختبار!")
                return False
                
        except Exception as e:
            print(f"   ❌ خطأ في إرسال الاختبار: {str(e)}")
            return False
    else:
        print("   ⏭️ تم تخطي اختبار الإرسال")
    
    print("\n" + "=" * 50)
    print("✅ اكتمل اختبار الإعدادات بنجاح!")
    print("🚀 يمكنك الآن استخدام خدمة الإيميل في التطبيق")
    
    return True

async def troubleshoot_common_issues():
    """دليل حل المشاكل الشائعة"""
    
    print("\n🔧 دليل حل المشاكل الشائعة:")
    print("=" * 40)
    
    issues_solutions = {
        "❌ Connection already using TLS": [
            "• تأكد من استخدام المنفذ 587 مع STARTTLS",
            "• لا تستخدم المنفذ 465 مع STARTTLS",
            "• تحقق من إعدادات TLS في الكود"
        ],
        "❌ Relaying disallowed": [
            "• تحقق من صحة اسم المستخدم وكلمة المرور",
            "• تأكد من أن البريد الإلكتروني نشط في Zoho",
            "• استخدم App Password إذا كان 2FA مُفعل",
            "• تحقق من إعدادات SMTP في حساب Zoho"
        ],
        "❌ Authentication failed": [
            "• تحقق من صحة بيانات تسجيل الدخول",
            "• استخدم App Password بدلاً من كلمة المرور العادية",
            "• تأكد من تفعيل IMAP/SMTP في إعدادات Zoho"
        ],
        "❌ Connection timeout": [
            "• تحقق من الاتصال بالإنترنت",
            "• قد يكون هناك حجب للمنفذ 587",
            "• جرب استخدام VPN إذا كان في بيئة مؤسسية"
        ]
    }
    
    for issue, solutions in issues_solutions.items():
        print(f"\n{issue}:")
        for solution in solutions:
            print(f"  {solution}")

def show_setup_guide():
    """دليل الإعداد خطوة بخطوة"""
    
    print("\n📚 دليل الإعداد خطوة بخطوة:")
    print("=" * 40)
    
    steps = [
        "1️⃣ إنشاء حساب Zoho Mail أو استخدام حساب موجود",
        "2️⃣ تسجيل الدخول لـ Zoho Mail Admin Console",
        "3️⃣ تفعيل IMAP/SMTP في الإعدادات",
        "4️⃣ إنشاء App Password (إذا كان 2FA مُفعل)",
        "5️⃣ ضبط متغيرات البيئة في ملف .env",
        "6️⃣ تشغيل سكريبت الاختبار هذا",
        "7️⃣ اختبار إرسال إيميل حقيقي"
    ]
    
    for step in steps:
        print(f"  {step}")
    
    print(f"\n💡 نصائح إضافية:")
    print(f"  • استخدم نطاق مخصص لمظهر أكثر احترافية")
    print(f"  • احتفظ بنسخة احتياطية من App Passwords")
    print(f"  • راقب حدود الإرسال اليومية في Zoho")

async def main():
    """الدالة الرئيسية"""
    
    print("🚀 أداة اختبار وتشخيص إعدادات Zoho Email")
    print("=" * 50)
    
    while True:
        print("\nاختر العملية:")
        print("1️⃣ اختبار الإعدادات الحالية")
        print("2️⃣ عرض دليل حل المشاكل")
        print("3️⃣ عرض دليل الإعداد")
        print("0️⃣ خروج")
        
        choice = input("\nالخيار: ").strip()
        
        if choice == "1":
            await test_email_setup()
        elif choice == "2":
            await troubleshoot_common_issues()
        elif choice == "3":
            show_setup_guide()
        elif choice == "0":
            print("👋 إلى اللقاء!")
            break
        else:
            print("❌ خيار غير صحيح، حاول مرة أخرى")

if __name__ == "__main__":
    # تشغيل الاختبار
    asyncio.run(main())