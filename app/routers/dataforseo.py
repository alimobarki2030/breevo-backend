from fastapi import APIRouter
from app.services.dataforseo import make_dataforseo_request

router = APIRouter()

@router.post("/dataforseo/keywords")
def get_keywords(data: dict):
    endpoint = "/keywords_data/google_ads/search_volume/live"
    return make_dataforseo_request(endpoint, data)
