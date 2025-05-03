# routes/analytics_routes.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from routes.auth import get_current_user  # ✅ تأكد من المسار الصحيح بعد النقل
from database import get_db
from models import UserAnalyticsToken

router = APIRouter()

@router.post("/overview")
def get_overview(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    token_data = get_user_token(user["user_id"], db)
    return {"message": f"✅ Overview data for user {user['user_id']}"}

@router.post("/top-queries")
def get_top_queries(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    token_data = get_user_token(user["user_id"], db)
    return {"message": f"✅ Top queries data for user {user['user_id']}"}

@router.post("/top-pages")
def get_top_pages(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    token_data = get_user_token(user["user_id"], db)
    return {"message": f"✅ Top pages data for user {user['user_id']}"}

# دالة مساعد لجلب token من قاعدة البيانات
def get_user_token(user_id: int, db: Session):
    token_entry = db.query(UserAnalyticsToken).filter(UserAnalyticsToken.user_id == user_id).first()
    if not token_entry:
        raise HTTPException(status_code=404, detail="❌ لم يتم العثور على بيانات Google لهذا المستخدم")
    return {
        "access_token": token_entry.access_token,
        "refresh_token": token_entry.refresh_token,
        "id_token": token_entry.id_token
    }
