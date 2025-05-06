from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import User
from utils import get_current_user

router = APIRouter()

class AnalyticsTokenInput(BaseModel):
    refresh_token: str
    client_id: str
    client_secret: str
    property_id: str

@router.post("/ga4/save-token")
def save_ga4_token(
    data: AnalyticsTokenInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # مبدئي: ضع هنا كود الحفظ الحقيقي لاحقًا
    return {"message": f"✅ Token saved for user {current_user.id}"}
