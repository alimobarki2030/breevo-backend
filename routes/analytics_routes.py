from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from utils import get_current_user
from database import get_db

router = APIRouter()

@router.post("/overview")
def get_overview(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"message": f"✅ Overview data for user {user.id}"}

@router.post("/top-queries")
def get_top_queries(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"message": f"✅ Top queries data for user {user.id}"}

@router.post("/top-pages")
def get_top_pages(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"message": f"✅ Top pages data for user {user.id}"}
