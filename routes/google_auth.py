import os
import json
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow

router = APIRouter()

# اقرأ JSON مباشرة من GOOGLE_CLIENT_SECRET_JSON
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
async def auth_callback(request: Request):
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
    return JSONResponse({
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    })
