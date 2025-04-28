from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from datetime import date, timedelta
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly"
]

class TokenData(BaseModel):
    refresh_token: str
    client_id: str
    client_secret: str
    token_uri: str

class GSCRequest(BaseModel):
    token_data: TokenData
    site_url: str
    days: Optional[int] = 30

def get_service(token_data: TokenData):
    credentials = Credentials.from_authorized_user_info(
        info=token_data.dict(),
        scopes=SCOPES
    )
    return build("searchconsole", "v1", credentials=credentials)

@router.post("/performance")
def get_gsc_performance(request: GSCRequest):
    if request.site_url.startswith("sc-domain:"):
        return JSONResponse(status_code=400, content={"error": "⚠️ لا يمكن تحليل هذا النوع من المواقع (sc-domain)."})

    service = get_service(request.token_data)
    end_date = date.today()
    start_date = end_date - timedelta(days=request.days)

    try:
        response = service.searchanalytics().query(
            siteUrl=request.site_url,
            body={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": ["date"],
                "rowLimit": 1000
            }
        ).execute()
        return {"data": response.get("rows", [])}
    except Exception as e:
        return {"error": str(e)}

@router.post("/top-queries")
def get_top_queries(request: GSCRequest):
    service = get_service(request.token_data)
    end_date = date.today()
    start_date = end_date - timedelta(days=request.days)

    try:
        response = service.searchanalytics().query(
            siteUrl=request.site_url,
            body={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": ["query"],
                "rowLimit": 10,
                "orderBy": [{"field": "clicks", "descending": True}]
            }
        ).execute()
        return {"top_queries": response.get("rows", [])}
    except Exception as e:
        return {"error": str(e)}

@router.post("/top-pages")
def get_top_pages(request: GSCRequest):
    service = get_service(request.token_data)
    end_date = date.today()
    start_date = end_date - timedelta(days=request.days)

    try:
        response = service.searchanalytics().query(
            siteUrl=request.site_url,
            body={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": ["page"],
                "rowLimit": 10,
                "orderBy": [{"field": "clicks", "descending": True}]
            }
        ).execute()
        return {"top_pages": response.get("rows", [])}
    except Exception as e:
        return {"error": str(e)}

@router.post("/backlinks")
def get_backlinks_sources(request: GSCRequest):
    service = get_service(request.token_data)
    end_date = date.today()
    start_date = end_date - timedelta(days=request.days)

    try:
        response = service.searchanalytics().query(
            siteUrl=request.site_url,
            body={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": ["country"],
                "rowLimit": 10
            }
        ).execute()
        return {"backlink_sources": response.get("rows", [])}
    except Exception as e:
        return {"error": str(e)}

@router.post("/overview")
def get_overview(request: GSCRequest):
    service = get_service(request.token_data)
    end_date = date.today()
    start_date = end_date - timedelta(days=request.days)

    try:
        response = service.searchanalytics().query(
            siteUrl=request.site_url,
            body={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": ["country"],
                "rowLimit": 1,
                "orderBy": [{"field": "clicks", "descending": True}],
                "aggregationType": "byProperty"
            }
        ).execute()

        total_clicks = sum(row.get("clicks", 0) for row in response.get("rows", []))
        total_impressions = sum(row.get("impressions", 0) for row in response.get("rows", []))
        ctr = (total_clicks / total_impressions * 100) if total_impressions else 0

        return {
            "clicks": total_clicks,
            "impressions": total_impressions,
            "ctr": round(ctr, 2),
            "top_country": response.get("rows", [{}])[0].get("keys", ["—"])[0]
        }

    except Exception as e:
        return {"error": str(e)}

@router.post("/top-queries-chart")
def get_top_queries_chart(request: GSCRequest):
    service = get_service(request.token_data)
    end_date = date.today()
    start_date = end_date - timedelta(days=request.days)

    try:
        response = service.searchanalytics().query(
            siteUrl=request.site_url,
            body={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": ["date"],
                "rowLimit": 1000,
                "orderBy": [{"field": "date", "descending": False}]
            }
        ).execute()

        chart_data = []
        for row in response.get("rows", []):
            chart_data.append({
                "date": row["keys"][0],
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0))
            })

        return {"chart_data": chart_data}

    except Exception as e:
        return {"error": str(e)}

@router.get("/test-analytics")
def test_analytics():
    return {"message": "analytics_routes are working ✅"}