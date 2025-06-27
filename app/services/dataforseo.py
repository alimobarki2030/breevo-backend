import requests
import os

def make_dataforseo_request(endpoint, payload):
    api_username = os.getenv("DATAFORSEO_LOGIN")
    api_password = os.getenv("DATAFORSEO_PASSWORD")
    base_url = "https://api.dataforseo.com"

    response = requests.post(
        base_url + endpoint,
        auth=(api_username, api_password),
        json=payload
    )
    response.raise_for_status()
    return response.json()
