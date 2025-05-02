from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="الرجاء تسجيل الدخول أولاً",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # ملاحظة: هنا يمكنك لاحقًا فك تشفير JWT للتحقق من المستخدم الحقيقي
    return {"id": 1, "username": "demo_user"}
