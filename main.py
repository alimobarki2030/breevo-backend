from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from dotenv import load_dotenv
from routes.product_routes import router as product_router



from routes.auth_routes import router as auth_router  # ✅ تم إضافته

load_dotenv()

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "https://breevo-frontend.vercel.app",
    "http://localhost:3000"
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="")  # ✅ تم إضافته
app.include_router(product_router)


@app.get("/")
def root():
    return {"message": "Hello World"} 