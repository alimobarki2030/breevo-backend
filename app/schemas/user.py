from pydantic import BaseModel, EmailStr
from typing import Optional

class UserRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    phone: Optional[str] = ""
    store_url: Optional[str] = ""
    plan: Optional[str] = "free"

class UserLogin(BaseModel):
    email: EmailStr
    password: str
