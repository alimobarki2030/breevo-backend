from fastapi import APIRouter, HTTPException, Form, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import User
from utils import verify_password, create_access_token

router = APIRouter()

@router.post("/auth/manual-login")
def manual_login(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="❌ البريد أو كلمة المرور غير صحيحة")
    
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}
