from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from database import get_db
from models import User, UserAnalyticsToken
import json
import os
import urllib.parse
import jwt

router = APIRouter()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "mysecret")
ALGORITHM = "HS256"

@router.get("/google-auth/callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    state = request.query_params.get("state")
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="No code provided from Google")

    flow = Flow.from_client_secrets_file(
        "client_secret.json",
        scopes=[
            "https://www.googleapis.com/auth/analytics.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid",
        ],
        state=state
    )
    flow.redirect_uri = "https://breevo-backend.onrender.com/google-auth/callback"

    flow.fetch_token(code=code)
    credentials = flow.credentials

    user_info = {
        "id": credentials.id_token,
        "email": credentials.id_token.get("email"),
    }

    user = db.query(User).filter(User.email == user_info["email"]).first()
    if not user:
        user = User(email=user_info["email"])
        db.add(user)
        db.commit()
        db.refresh(user)

    token_data = UserAnalyticsToken(
        user_id=user.id,
        access_token=credentials.token,
        refresh_token=credentials.refresh_token,
        id_token=credentials.id_token
    )
    db.add(token_data)
    db.commit()

    jwt_token = jwt.encode({"email": user.email}, SECRET_KEY, algorithm=ALGORITHM)

    frontend_redirect_url = f"https://breevo-frontend-etsh.vercel.app/complete-auth?token={jwt_token}"
    return RedirectResponse(frontend_redirect_url)
