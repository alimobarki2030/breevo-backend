from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from database import get_db
from models import User, UserAnalyticsToken
import os
import jwt

router = APIRouter()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "mysecret")
ALGORITHM = "HS256"

@router.get("/login")
def login():
    flow = Flow.from_client_secrets_file(
        "client_secret.json",
        scopes=[
            "https://www.googleapis.com/auth/analytics.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid",
        ],
        redirect_uri="https://breevo-backend.onrender.com/google-auth/callback"
    )
    auth_url, _ = flow.authorization_url(prompt='consent')
    return RedirectResponse(auth_url)

@router.get("/callback")
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
        state=state,
        redirect_uri="https://breevo-backend.onrender.com/google-auth/callback"
    )
    flow.fetch_token(code=code)
    credentials = flow.credentials

    user_email = credentials.id_token.get("email")

    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        user = User(email=user_email)
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
