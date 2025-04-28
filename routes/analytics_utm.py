from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import date, timedelta

def get_gsc_clicks_summary(data: dict):
    try:
        print("🔍 get_gsc_clicks_summary | البيانات:", data)
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
                "dimensions": [],
                "aggregationType": "byProperty"
            }
        ).execute()

        clicks = perf_response.get("rows", [{}])[0].get("clicks", 0)
        impressions = perf_response.get("rows", [{}])[0].get("impressions", 0)
        ctr = (clicks / impressions * 100) if impressions else 0

        country_response = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": ["country"],
                "rowLimit": 1,
                "orderBy": [{"field": "clicks", "descending": True}]
            }
        ).execute()

        top_country = country_response.get("rows", [{}])[0].get("keys", ["—"])[0]

        return {
            "clicks": clicks,
            "impressions": impressions,
            "ctr": round(ctr, 2),
            "top_country": top_country
        }
    except Exception as e:
        print(f"❌ خطأ في get_gsc_clicks_summary: {e}")
        raise e

def get_top_queries(data: dict):
    try:
        print("🔍 get_top_queries | البيانات:", data)
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

        response = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": ["query"],
                "rowLimit": 10,
                "orderBy": [{"field": "clicks", "descending": True}]
            }
        ).execute()

        return {
            "top_queries": response.get("rows", [])
        }
    except Exception as e:
        print(f"❌ خطأ في get_top_queries: {e}")
        raise e

def get_top_pages(data: dict):
    try:
        print("🔍 get_top_pages | البيانات:", data)
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

        response = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": ["page"],
                "rowLimit": 10,
                "orderBy": [{"field": "clicks", "descending": True}]
            }
        ).execute()

        return {
            "top_pages": response.get("rows", [])
        }
    except Exception as e:
        print(f"❌ خطأ في get_top_pages: {e}")
        raise e

def get_backlinks_count(data: dict):
    try:
        print("🔍 get_backlinks_count | البيانات:", data)
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

        response = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": ["country"],
                "rowLimit": 10,
                "orderBy": [{"field": "clicks", "descending": True}]
            }
        ).execute()

        return {
            "backlink_sources": response.get("rows", [])
        }
    except Exception as e:
        print(f"❌ خطأ في get_backlinks_count: {e}")
        raise e

def get_gsc_summary(data: dict):
    try:
        print("🔍 get_gsc_summary | البيانات:", data)
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

        response = service.searchanalytics().query(
            siteUrl=site_url,
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

        return {
            "chart_data": chart_data
        }
    except Exception as e:
        print(f"❌ خطأ في get_gsc_summary: {e}")
        raise e

def get_top_queries_chart_data(data: dict):
    try:
        print("🔍 get_top_queries_chart_data | البيانات:", data)
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

        response = service.searchanalytics().query(
            siteUrl=site_url,
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

        return {
            "chart_data": chart_data
        }
    except Exception as e:
        print(f"❌ خطأ في get_top_queries_chart_data: {e}")
        raise e