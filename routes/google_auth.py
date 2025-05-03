import os
import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserAnalyticsToken
from jose import jwt

router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

@router.get("/login")
def login(request: Request):
    client_secrets_json = os.getenv("GOOGLE_CLIENT_SECRET_JSON")
    client_secrets = json.loads(client_secrets_json)
    
    flow = Flow.from_client_config(
        client_secrets,
        scopes=[
            "https://www.googleapis.com/auth/analytics.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid"
        ],
        redirect_uri=os.getenv("GOOGLE_REDIRECT_URI")
    )
    
    auth_url, _ = flow.authorization_url(prompt='consent')
    return RedirectResponse(auth_url)

@router.get("/callback")
def callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get('code')
    
    client_secrets_json = os.getenv("GOOGLE_CLIENT_SECRET_JSON")
    client_secrets = json.loads(client_secrets_json)
    
    flow = Flow.from_client_config(
        client_secrets,
        scopes=[
            "https://www.googleapis.com/auth/analytics.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid"
        ],
        redirect_uri=os.getenv("GOOGLE_REDIRECT_URI")
    )
    
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # احفظ التوكن في DB (اختصرتها حسب مشروعك)
    user = db.query(User).filter(User.email == credentials.id_token['email']).first()
    if not user:
        user = User(email=credentials.id_token['email'])
        db.add(user)
        db.commit()
        db.refresh(user)

    token = jwt.encode({"sub": user.email}, SECRET_KEY, algorithm=ALGORITHM)
    
    analytics_token = UserAnalyticsToken(user_id=user.id, access_token=credentials.token, refresh_token=credentials.refresh_token)
    db.add(analytics_token)
    db.commit()

    # أرسل التوكن إلى الواجهة الأمامية مع إعادة التوجيه
    frontend_url = f"https://breevo-frontend-etsh.vercel.app/complete-auth?token={token}"
    return RedirectResponse(frontend_url)
