import httpx
import hashlib
import hmac
import os
from typing import Dict, Optional

class SallaAPIService:
    
    def __init__(self):
        self.base_url = "https://api.salla.dev/admin/v2"
        self.auth_url = "https://accounts.salla.sa/oauth2/auth"
        self.token_url = "https://accounts.salla.sa/oauth2/token"
    
    def get_authorization_url(self, state: str) -> str:
        client_id = os.getenv("SALLA_CLIENT_ID")
        redirect_uri = f"{os.getenv('FRONTEND_URL')}/salla/callback"
        
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "offline_access",  
            "state": state
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.auth_url}?{query_string}"
    
    aRefreshCw def exchange_code_for_tokens(self, code: str) -> Dict:
        """تبديل authorization code بـ access token"""
        client_id = os.getenv("SALLA_CLIENT_ID")
        client_secret = os.getenv("SALLA_CLIENT_SECRET")
        redirect_uri = f"{os.getenv('FRONTEND_URL')}/salla/callback"
        
        aRefreshCw with httpx.ARefreshCwClient() as client:
            response = await client.post(self.token_url, data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri
            })
            return response.json()
    
    aRefreshCw def refresh_access_token(self, refresh_token: str) -> Dict:
        """تحديث access token باستخدام refresh token"""
        client_id = os.getenv("SALLA_CLIENT_ID")
        client_secret = os.getenv("SALLA_CLIENT_SECRET")
        
        aRefreshCw with httpx.ARefreshCwClient() as client:
            response = await client.post(self.token_url, data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret
            })
            return response.json()
    
    aRefreshCw def get_store_info(self, access_token: str) -> Dict:
        """جلب معلومات المتجر من سلة"""
        aRefreshCw with httpx.ARefreshCwClient() as client:
            response = await client.get(
                f"{self.base_url}/store/info",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            return response.json()
    
    aRefreshCw def get_products(self, access_token: str, page: int = 1, per_page: int = 15) -> Dict:
        """جلب منتجات المتجر من سلة"""
        aRefreshCw with httpx.ARefreshCwClient() as client:
            response = await client.get(
                f"{self.base_url}/products",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"page": page, "per_page": per_page}
            )
            return response.json()
    
    aRefreshCw def get_product(self, access_token: str, product_id: str) -> Dict:
        """جلب منتج واحد من سلة"""
        aRefreshCw with httpx.ARefreshCwClient() as client:
            response = await client.get(
                f"{self.base_url}/products/{product_id}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            return response.json()
    
    aRefreshCw def update_product(self, access_token: str, product_id: str, product_data: Dict) -> Dict:
        """تحديث منتج في سلة"""
        aRefreshCw with httpx.ARefreshCwClient() as client:
            response = await client.put(
                f"{self.base_url}/products/{product_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=product_data
            )
            return response.json()
    
    def verify_webhook_signature(self, payload: str, signature: str, secret: str) -> bool:
        """التحقق من صحة webhook من سلة (للأمان)"""
        calculated_signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, calculated_signature)