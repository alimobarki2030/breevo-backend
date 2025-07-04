# app/services/salla_api.py - محدث للعمل مع Render Backend
import httpx
import hashlib
import hmac
import os
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class SallaAPIService:
    
    def __init__(self):
        self.base_url = "https://api.salla.dev/admin/v2"
        self.auth_url = "https://accounts.salla.sa/oauth2/auth"
        self.token_url = "https://accounts.salla.sa/oauth2/token"
        
        # التحقق من متغيرات البيئة المطلوبة
        self.client_id = os.getenv("SALLA_CLIENT_ID")
        self.client_secret = os.getenv("SALLA_CLIENT_SECRET")
        self.backend_url = os.getenv("BACKEND_URL")
        
        if not all([self.client_id, self.client_secret, self.backend_url]):
            logger.warning("⚠️ Salla configuration incomplete")
            logger.warning(f"Client ID: {'✅' if self.client_id else '❌'}")
            logger.warning(f"Client Secret: {'✅' if self.client_secret else '❌'}")
            logger.warning(f"Backend URL: {'✅' if self.backend_url else '❌'}")
    
    def get_authorization_url(self, state: str) -> str:
        """إنشاء رابط التفويض - محدث لاستخدام Backend URL"""
        if not self.client_id or not self.backend_url:
            raise ValueError("Missing SALLA_CLIENT_ID or BACKEND_URL configuration")
        
        # استخدام BACKEND_URL للـ callback
        redirect_uri = f"{self.backend_url}/api/salla/oauth/callback"
        
        logger.info(f"🔗 Creating authorization URL")
        logger.info(f"📍 Redirect URI: {redirect_uri}")
        logger.info(f"🆔 Client ID: {self.client_id}")
        
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": "offline_access",  
            "state": state
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        auth_url = f"{self.auth_url}?{query_string}"
        
        logger.info(f"✅ Generated auth URL: {auth_url}")
        return auth_url
    
    async def exchange_code_for_tokens(self, code: str) -> Dict:
        """تبديل authorization code بـ access token - محدث"""
        if not all([self.client_id, self.client_secret, self.backend_url]):
            raise ValueError("Missing Salla configuration")
        
        # استخدام BACKEND_URL للـ redirect_uri
        redirect_uri = f"{self.backend_url}/api/salla/oauth/callback"
        
        logger.info(f"🔄 Exchanging code for tokens...")
        logger.info(f"🔗 Using redirect_uri: {redirect_uri}")
        
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": redirect_uri
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.token_url, 
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                result = response.json()
                
                if response.status_code == 200:
                    logger.info(f"✅ Token exchange successful")
                    # إزالة client_secret من الـ logs
                    safe_result = {k: v for k, v in result.items() if k != 'client_secret'}
                    logger.info(f"📊 Token data: {safe_result}")
                else:
                    logger.error(f"❌ Token exchange failed: {response.status_code}")
                    logger.error(f"📄 Error response: {result}")
                
                return result
                
        except httpx.TimeoutException:
            logger.error("⏰ Timeout during token exchange")
            return {"error": "timeout", "error_description": "Token exchange timed out"}
        except Exception as e:
            logger.error(f"❌ Exception during token exchange: {str(e)}")
            return {"error": "exchange_failed", "error_description": str(e)}
    
    async def refresh_access_token(self, refresh_token: str) -> Dict:
        """تحديث access token باستخدام refresh token"""
        if not all([self.client_id, self.client_secret]):
            raise ValueError("Missing Salla client credentials")
        
        logger.info(f"🔄 Refreshing access token...")
        
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.token_url,
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                result = response.json()
                
                if response.status_code == 200:
                    logger.info(f"✅ Token refresh successful")
                else:
                    logger.error(f"❌ Token refresh failed: {response.status_code}")
                    logger.error(f"📄 Error response: {result}")
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Exception during token refresh: {str(e)}")
            return {"error": "refresh_failed", "error_description": str(e)}
    
    async def get_store_info(self, access_token: str) -> Dict:
        """جلب معلومات المتجر من سلة"""
        logger.info(f"🏪 Fetching store info...")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/store/info",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                result = response.json()
                
                if response.status_code == 200:
                    logger.info(f"✅ Store info retrieved successfully")
                    store_name = result.get("data", {}).get("name", "Unknown")
                    logger.info(f"🏷️ Store name: {store_name}")
                else:
                    logger.error(f"❌ Store info fetch failed: {response.status_code}")
                    logger.error(f"📄 Error response: {result}")
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Exception during store info fetch: {str(e)}")
            return {"error": "store_info_failed", "error_description": str(e)}
    
    async def get_products(self, access_token: str, page: int = 1, per_page: int = 15) -> Dict:
        """جلب منتجات المتجر من سلة"""
        logger.info(f"📦 Fetching products - Page {page}, Per page: {per_page}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/products",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"page": page, "per_page": per_page}
                )
                
                result = response.json()
                
                if response.status_code == 200:
                    products_count = len(result.get("data", []))
                    logger.info(f"✅ Retrieved {products_count} products from page {page}")
                else:
                    logger.error(f"❌ Products fetch failed: {response.status_code}")
                    logger.error(f"📄 Error response: {result}")
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Exception during products fetch: {str(e)}")
            return {"error": "products_fetch_failed", "error_description": str(e)}
    
    async def get_product(self, access_token: str, product_id: str) -> Dict:
        """جلب منتج واحد من سلة"""
        logger.info(f"📦 Fetching product: {product_id}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/products/{product_id}",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                result = response.json()
                
                if response.status_code == 200:
                    product_name = result.get("data", {}).get("name", "Unknown")
                    logger.info(f"✅ Product retrieved: {product_name}")
                else:
                    logger.error(f"❌ Product fetch failed: {response.status_code}")
                    logger.error(f"📄 Error response: {result}")
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Exception during product fetch: {str(e)}")
            return {"error": "product_fetch_failed", "error_description": str(e)}
    
    async def update_product(self, access_token: str, product_id: str, product_data: Dict) -> Dict:
        """تحديث منتج في سلة"""
        logger.info(f"✏️ Updating product: {product_id}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(
                    f"{self.base_url}/products/{product_id}",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json=product_data
                )
                
                result = response.json()
                
                if response.status_code == 200:
                    logger.info(f"✅ Product updated successfully: {product_id}")
                else:
                    logger.error(f"❌ Product update failed: {response.status_code}")
                    logger.error(f"📄 Error response: {result}")
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Exception during product update: {str(e)}")
            return {"error": "product_update_failed", "error_description": str(e)}
    
    def verify_webhook_signature(self, payload: str, signature: str, secret: str) -> bool:
        """التحقق من صحة webhook من سلة (للأمان)"""
        try:
            calculated_signature = hmac.new(
                secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            is_valid = hmac.compare_digest(signature, calculated_signature)
            
            if is_valid:
                logger.info("✅ Webhook signature verified")
            else:
                logger.warning("⚠️ Webhook signature verification failed")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"❌ Error verifying webhook signature: {str(e)}")
            return False

    def get_configuration_status(self) -> Dict:
        """التحقق من حالة إعدادات سلة"""
        return {
            "client_id_configured": bool(self.client_id),
            "client_secret_configured": bool(self.client_secret),
            "backend_url_configured": bool(self.backend_url),
            "backend_url": self.backend_url,
            "redirect_uri": f"{self.backend_url}/api/salla/oauth/callback" if self.backend_url else None,
            "all_configured": bool(self.client_id and self.client_secret and self.backend_url)
        }