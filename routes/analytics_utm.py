from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import date, timedelta

def get_gsc_clicks_summary(data: dict):
    token_data = data["token_data"]
    site_url = data["site_url"]
    days = data.get("days", 30)

    credentials = Credentials(
        refresh_token=token_data["refresh_token"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        token_uri=token_data["token_uri"]
    )

    service = build("searchconsole", "v1", credentials=credentials)

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    perf_response = service.searchanalytics().query(
        siteUrl=site_url,
        body={
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["query"],
            "rowLimit": 10
        }
    ).execute()

    return perf_response
