import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from models import User, UserAnalyticsToken
from database import get_db
from jose import jwt
from sqlalchemy.orm import Session
import json
import urllib.parse

router = APIRouter()

CLIENT_SECRETS_FILE = "/etc/secrets/client_secret.json"
SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]
REDIRECT_URI = "https://breevo-backend.onrender.com/google-auth/callback"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "mysecret")
ALGORITHM = "HS256"

@router.get("/google-auth/login")
def login():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(
        prompt="consent", access_type="offline", include_granted_scopes="true"
    )
    return RedirectResponse(auth_url)

@router.get("/google-auth/callback")
def callback(request: Request, db: Session = Depends(get_db)):
    print("🔁 OAuth Callback URL:", str(request.url))

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    # تحقق من وجود الكود
    parsed_url = urllib.parse.urlparse(str(request.url))
    query_params = urllib.parse.parse_qs(parsed_url.query)

    if 'code' not in query_params:
        print("❌ OAuth failed: 'code' parameter is missing.")
        return RedirectResponse("https://breevo-frontend-etsh.vercel.app/")


    try:
        flow.fetch_token(authorization_response=str(request.url))
    except Exception as e:
        print("❌ Error during token fetch:", e)
        return RedirectResponse("https://breevo-frontend-etsh.vercel.app/")


    credentials = flow.credentials
    request_session = GoogleRequest()
    credentials.refresh(request_session)

    token_data = {
        "refresh_token": credentials.refresh_token,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "token_uri": credentials.token_uri
    }

    from googleapiclient.discovery import build
    oauth2_service = build('oauth2', 'v2', credentials=credentials)
    user_info = oauth2_service.userinfo().get().execute()
    email = user_info.get("email")
    full_name = user_info.get("name")

    user = db.query(User).filter_by(email=email).first()
    if not user:
        user = User(email=email, full_name=full_name)
        db.add(user)
        db.commit()
        db.refresh(user)

    existing = db.query(UserAnalyticsToken).filter_by(user_id=user.id).first()
    if existing:
        existing.refresh_token = token_data["refresh_token"]
        existing.client_id = token_data["client_id"]
        existing.client_secret = token_data["client_secret"]
        existing.token_uri = token_data["token_uri"]
    else:
        new_token = UserAnalyticsToken(
            user_id=user.id,
            refresh_token=token_data["refresh_token"],
            client_id=token_data["client_id"],
            client_secret=token_data["client_secret"],
            token_uri=token_data["token_uri"],
            property_id=""
        )
        db.add(new_token)

    db.commit()

    jwt_token = jwt.encode({"user_id": user.id}, SECRET_KEY, algorithm=ALGORITHM)
    return RedirectResponse(f"https://breevo-frontend-etsh.vercel.app/analytics?token={urllib.parse.quote(jwt_token)}")

