# routes/auth.py

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import os

# إعداد OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# إعدادات JWT - الأفضل أخذ المفتاح من متغير بيئة
SECRET_KEY = os.getenv("SECRET_KEY", "mysecretkey123")
ALGORITHM = "HS256"

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="⚠️ الرجاء تسجيل الدخول أولاً",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    return {"user_id": int(user_id)}
