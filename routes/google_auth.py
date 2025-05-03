import os
import json
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserAnalyticsToken
from jose import jwt, jwk, jws
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

@router.get("/login")
def login():
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

    # تحقق من id_token وجلب معلومات المستخدم
    idinfo = id_token.verify_oauth2_token(
        credentials.id_token,
        google_requests.Request(),
        client_secrets['web']['client_id']
    )
    user_email = idinfo.get('email')

    # تحقق أو أنشئ المستخدم في قاعدة البيانات
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        user = User(email=user_email)
        db.add(user)
        db.commit()
        db.refresh(user)

    # خزّن التوكنات
    analytics_token = UserAnalyticsToken(
        user_id=user.id,
        access_token=credentials.token,
        refresh_token=credentials.refresh_token,
        id_token=credentials.id_token
    )
    db.add(analytics_token)
    db.commit()

    jwt_token = jwt.encode({"sub": user.email}, SECRET_KEY, algorithm=ALGORITHM)

    frontend_url = f"https://breevo-frontend-etsh.vercel.app/complete-auth?token={jwt_token}"
    return RedirectResponse(frontend_url)
