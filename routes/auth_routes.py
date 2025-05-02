# routes/auth_routes.py

from fastapi import APIRouter, HTTPException, Form

router = APIRouter()

# قاعدة بيانات وهمية للتجربة
FAKE_USER_DB = {
    "test@example.com": {
        "password": "password123",
        "id": 1
    }
}

@router.post("/auth/manual-login")
def manual_login(email: str = Form(...), password: str = Form(...)):
    user = FAKE_USER_DB.get(email)
    if not user or user["password"] != password:
        raise HTTPException(status_code=400, detail="❌ البريد أو كلمة المرور غير صحيحة")
    
    # ✅ توليد JWT
    access_token = create_access_token(data={"sub": str(user["id"])})
    
    return {
        "token": access_token,
        "google_linked": False
    }
