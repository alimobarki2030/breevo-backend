from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import UserAnalyticsToken
from auth import get_current_user

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

router = APIRouter()

class AnalyticsTokenInput(BaseModel):
    refresh_token: str
    client_id: str
    client_secret: str
    property_id: str

@router.post("/ga4/save-token")
def save_ga4_token(
    data: AnalyticsTokenInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        existing = db.query(UserAnalyticsToken).filter_by(user_id=current_user["id"]).first()

        if existing:
            existing.refresh_token = data.refresh_token
            existing.client_id = data.client_id
            existing.client_secret = data.client_secret
            existing.property_id = data.property_id
        else:
            token = UserAnalyticsToken(
                user_id=current_user["id"],
                refresh_token=data.refresh_token,
                client_id=data.client_id,
                client_secret=data.client_secret,
                property_id=data.property_id,
                token_uri="https://oauth2.googleapis.com/token"
            )
            db.add(token)

        db.commit()
        return {"message": "تم حفظ بيانات Google Analytics بنجاح."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ga4/utm-summary")
def get_utm_campaign_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        token = db.query(UserAnalyticsToken).filter_by(user_id=current_user["id"]).first()

        if not token:
            raise HTTPException(status_code=404, detail="بيانات Google Analytics غير مرتبطة بالحساب.")

        creds = Credentials.from_authorized_user_info(
            info={
                "refresh_token": token.refresh_token,
                "client_id": token.client_id,
                "client_secret": token.client_secret,
                "token_uri": token.token_uri,
            },
            scopes=["https://www.googleapis.com/auth/analytics.readonly"]
        )
        creds.refresh(Request())

        client = BetaAnalyticsDataClient(credentials=creds)

        run_request = RunReportRequest(
            property=token.property_id,
            dimensions=[
                Dimension(name="sessionCampaignName"),
                Dimension(name="sessionSource")
            ],
            metrics=[
                Metric(name="sessions")
            ],
            date_ranges=[
                DateRange(start_date="30daysAgo", end_date="today")
            ]
        )

        response = client.run_report(request=run_request)

        result = []
        for row in response.rows:
            result.append({
                "campaign": row.dimension_values[0].value,
                "source": row.dimension_values[1].value,
                "sessions": int(row.metric_values[0].value)
            })

        return {"utm_campaigns": result}

    except Exception as e:
        return {"error": str(e)}
