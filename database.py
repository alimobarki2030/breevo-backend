from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# إعداد الاتصال بقاعدة البيانات
SQLALCHEMY_DATABASE_URL = "sqlite:///./breevo.db"


engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# القاعدة الأساسية للنماذج
Base = declarative_base()

# دالة لجلب جلسة قاعدة البيانات
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ✅ دالة لإنشاء الجداول من models.py
def create_database():
    from models import Base  # يحتوي على Product
    Base.metadata.create_all(bind=engine)
    print("✅ تم إنشاء قاعدة البيانات بنجاح.")

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# إعداد الاتصال بقاعدة البيانات
SQLALCHEMY_DATABASE_URL = "sqlite:///./breevo.db"


engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# القاعدة الأساسية للنماذج
Base = declarative_base()

# دالة لجلب جلسة قاعدة البيانات
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ✅ دالة لإنشاء الجداول من models.py
def create_database():
    from models import Base  # يحتوي على Product
    Base.metadata.create_all(bind=engine)
    print("✅ تم إنشاء قاعدة البيانات بنجاح.")
