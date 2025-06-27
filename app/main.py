from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from dotenv import load_dotenv
from app.routers.products import router as product_router
from app.routers.ai import router as ai_router
from app.routers.auth import router as auth_router
from app.routers.dataforseo import router as dataforseo_router

load_dotenv()

app = FastAPI()

# Updated origins to include your production frontend
origins = [
    "http://localhost:3000",  # Local development
    "https://breevo-frontend.vercel.app",  # Your production frontend
    "https://your-frontend-domain.vercel.app",  # Add your actual frontend domain
    "https://accounts.google.com",
    "https://www.google.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("✅ Database engine created")

Base.metadata.create_all(bind=engine)

# Routers
app.include_router(product_router)
app.include_router(ai_router)
app.include_router(auth_router)
app.include_router(dataforseo_router)

@app.get("/")
def read_root():
    return {"message": "Hello World"}