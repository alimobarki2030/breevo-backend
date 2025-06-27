from database import Base, engine

print("⚠️ سيتم حذف كل الجداول...")
Base.metadata.drop_all(bind=engine)
print("🧹 تم الحذف!")

print("🚀 يتم الآن إنشاء الجداول من جديد...")
Base.metadata.create_all(bind=engine)
print("✅ تم الإنشاء بنجاح!")
