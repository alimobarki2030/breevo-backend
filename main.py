from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.google_auth import router as google_auth_router
from routes.analytics_routes import router as analytics_router
from routes.auth_routes import router as auth_router

app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://breevo-frontend-etsh.vercel.app",
    "https://breevo-frontend.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(google_auth_router, prefix="/google-auth")
app.include_router(analytics_router, prefix="/analytics")
app.include_router(auth_router)
