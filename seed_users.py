from database import SessionLocal
from models import User
from utils import pwd_context

db = SessionLocal()

# ضع هنا بيانات المستخدم التجريبي
email = "alimobarki.ad@gmail.com"
password = "Ali05736427"
hashed_password = pwd_context.hash(password)

# تأكد لا يتكرر المستخدم
existing_user = db.query(User).filter(User.email == email).first()
if not existing_user:
    new_user = User(
        email=email,
        hashed_password=hashed_password,
        auth_provider="manual"
    )
    db.add(new_user)
    db.commit()
    print(f"✅ تمت إضافة المستخدم: {email}")
else:
    print(f"⚠️ المستخدم {email} موجود مسبقًا")

db.close()
