from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import os

# مفتاح التشفير السري (يمكن تخزينه بشكل آمن في .env)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "mysecret")
ALGORITHM = "HS256"

security = HTTPBearer()

# ✅ هذه الدالة تُستخدم للحصول على المستخدم الحالي بناءً على الـ token

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="رمز دخول غير صالح")
        return {"id": user_id}
    except JWTError:
        raise HTTPException(status_code=403, detail="تعذر التحقق من المستخدم")
