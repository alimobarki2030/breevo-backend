# routes/google_auth.py

import os
import json
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from jose import jwt

router = APIRouter()

SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "https://breevo-backend.onrender.com/google-auth/callback")
SECRET_KEY = os.getenv("SECRET_KEY", "mysecret")
ALGORITHM = "HS256"

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

    # إعداد بيانات JWT للواجهة الأمامية
    token_data = {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "id_token": credentials.id_token
    }
    jwt_token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

    frontend_redirect_url = f"https://breevo-frontend.vercel.app/complete-auth?token={jwt_token}"
    return RedirectResponse(frontend_redirect_url)
