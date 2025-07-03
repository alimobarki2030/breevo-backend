from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models import User
from app.routers.products import router as product_router


def reset_users():
    db: Session = SessionLocal()
    try:
        deleted_count = db.query(User).delete()
        db.commit()
        print(f"🧹 تم حذف {deleted_count} مستخدم(ين) من قاعدة البيانات.")
    except Exception as e:
        db.rollback()
        print("❌ حدث خطأ أثناء حذف المستخدمين:", e)
    finally:
        db.close()

if __name__ == "__main__":
    reset_users()