import os
import json
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from database import get_db
from models import UserAnalyticsToken

router = APIRouter()

# تحميل إعدادات Google OAuth من متغير البيئة
client_secret_json = os.getenv("GOOGLE_CLIENT_SECRET_JSON")
if not client_secret_json:
    raise Exception("Missing GOOGLE_CLIENT_SECRET_JSON in environment variables")
client_config = json.loads(client_secret_json)

REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

@router.get("/google-auth/login")
def google_login():
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(prompt='consent')
    return RedirectResponse(auth_url)

@router.get("/google-auth/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    state = request.query_params.get("state")
    code = request.query_params.get("code")

    if not code:
        return JSONResponse({"error": "Missing code in callback"}, status_code=400)

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        state=state,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # ⚡ TODO: احفظ التوكن في قاعدة البيانات حسب user_id
    # مثال:
    # user_id = extract_user_id_somehow()
    # user_token = UserAnalyticsToken(
    #     user_id=user_id,
    #     access_token=credentials.token,
    #     refresh_token=credentials.refresh_token,
    #     token_uri=credentials.token_uri,
    #     client_id=credentials.client_id,
    #     client_secret=credentials.client_secret,
    #     scopes=",".join(credentials.scopes)
    # )
    # db.add(user_token)
    # db.commit()

    # ✅ إعادة التوجيه إلى صفحة اختيار الموقع في الواجهة الأمامية
    return RedirectResponse(
        url="https://breevo-frontend.vercel.app/site-selector"
    )
