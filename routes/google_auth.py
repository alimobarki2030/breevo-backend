import os
import json
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from sqlalchemy.orm import Session
from database import SessionLocal
from models import UserAnalyticsToken

router = APIRouter()

SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]
REDIRECT_URI = "https://breevo-backend.onrender.com/google-auth/callback"

@router.get("/google-auth/login")
def login():
    client_secret_info = json.loads(os.environ["GOOGLE_CLIENT_SECRET_JSON"])
    flow = Flow.from_client_config(
        client_secret_info,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(prompt="consent")
    return RedirectResponse(auth_url)

@router.get("/google-auth/callback")
def callback(request: Request):
    code = request.query_params.get("code")

    client_secret_info = json.loads(os.environ["GOOGLE_CLIENT_SECRET_JSON"])
    flow = Flow.from_client_config(
        client_secret_info,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(code=code)

    credentials: Credentials = flow.credentials
    refresh_token = credentials.refresh_token

    # احفظ في قاعدة البيانات
    db: Session = SessionLocal()
    token_entry = UserAnalyticsToken(
        user_id=1,  # لاحقًا اربطه بالمستخدم الفعلي
        refresh_token=refresh_token,
        client_id=client_secret_info['web']['client_id'],
        client_secret=client_secret_info['web']['client_secret'],
        property_id=""  # يمكنك تعبئة property_id لاحقًا من الواجهة الأمامية
    )
    db.add(token_entry)
    db.commit()
    db.close()

    return {"message": "Tokens saved successfully"}
