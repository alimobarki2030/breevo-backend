import os
import re

def fix_pydantic_in_directory(directory="app"):
    """
    يبحث ويصلح جميع ملفات Python في المجلد المحدد
    """
    fixed_files = []
    error_files = []
    
    print(f"🔍 البحث في مجلد: {directory}")
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                
                try:
                    # قراءة الملف
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # البحث عن orm_mode = True
                    if 'orm_mode = True' in content:
                        # الاستبدال
                        new_content = content.replace('orm_mode = True', 'from_attributes = True')
                        
                        # كتابة الملف المحدث
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        
                        fixed_files.append(file_path)
                        print(f"✅ تم تحديث: {file_path}")
                    
                except Exception as e:
                    error_files.append((file_path, str(e)))
                    print(f"❌ خطأ في {file_path}: {e}")
    
    # عرض النتائج
    print("\n" + "="*50)
    print(f"📊 النتائج:")
    print(f"   ✅ تم تحديث {len(fixed_files)} ملف")
    print(f"   ❌ فشل تحديث {len(error_files)} ملف")
    
    if fixed_files:
        print("\n📋 الملفات المحدثة:")
        for f in fixed_files:
            print(f"   • {f}")
    
    if error_files:
        print("\n⚠️ الملفات التي فشل تحديثها:")
        for f, e in error_files:
            print(f"   • {f}: {e}")
    
    if not fixed_files and not error_files:
        print("\n💡 لم يتم العثور على ملفات تحتاج للتحديث!")
        print("   قد تكون المشكلة في مكان آخر.")

if __name__ == "__main__":
    # تشغيل الإصلاح
    fix_pydantic_in_directory("app")
    
    print("\n✨ انتهى!")
    print("\n⚠️ تذكير: أعد تشغيل الخادم الآن")
    print("   uvicorn app.main:app --reload")