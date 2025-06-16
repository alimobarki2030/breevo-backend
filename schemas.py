from pydantic import BaseModel

class UserRegister(BaseModel):
    full_name: str
    email: str
    password: str
    phone: str
    store_url: str
    heard_from: str
    plan: str

class UserLogin(BaseModel):
    email: str
    password: str
