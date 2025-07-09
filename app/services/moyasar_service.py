# app/services/moyasar_service.py
import os
import logging
import httpx
from typing import Dict, Any, Optional
from base64 import b64encode
import json

logger = logging.getLogger(__name__)

class MoyasarService:
    """خدمة التكامل مع بوابة الدفع Moyasar"""
    
    def __init__(self):
        self.secret_key = os.getenv('MOYASAR_SECRET_KEY')
        self.publishable_key = os.getenv('MOYASAR_PUBLISHABLE_KEY')
        self.base_url = "https://api.moyasar.com/v1"
        
        # التحقق من وجود المفاتيح
        if not self.secret_key:
            logger.warning("Moyasar secret key not configured")
        if not self.publishable_key:
            logger.warning("Moyasar publishable key not configured")
        
        # إعداد Headers للمصادقة
        if self.secret_key:
            auth_string = b64encode(f"{self.secret_key}:".encode()).decode()
            self.headers = {
                "Authorization": f"Basic {auth_string}",
                "Content-Type": "application/json"
            }
        else:
            self.headers = {}
    
    async def create_payment(
        self,
        amount: int,  # بالهللات
        currency: str = "SAR",
        description: str = "",
        callback_url: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        source: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """إنشاء دفعة جديدة"""
        
        if not self.secret_key:
            logger.error("Cannot create payment without secret key")
            return {
                "success": False,
                "error": "Moyasar not configured"
            }
        
        try:
            payment_data = {
                "amount": amount,
                "currency": currency,
                "description": description,
                "callback_url": callback_url,
                "metadata": metadata or {}
            }
            
            if source:
                payment_data["source"] = source
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/payments",
                    json=payment_data,
                    headers=self.headers
                )
                
                response_data = response.json()
                
                if response.status_code == 201:
                    logger.info(f"Payment created successfully: {response_data.get('id')}")
                    return {
                        "success": True,
                        "payment": response_data
                    }
                else:
                    logger.error(f"Payment creation failed: {response_data}")
                    return {
                        "success": False,
                        "error": response_data.get("message", "Payment creation failed")
                    }
                    
        except Exception as e:
            logger.error(f"Error creating payment: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def verify_payment(self, payment_id: str) -> bool:
        """التحقق من حالة الدفعة"""
        
        if not self.secret_key:
            logger.warning("Cannot verify payment without secret key")
            return True  # في وضع التطوير، نقبل كل الدفعات
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/payments/{payment_id}",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    payment_data = response.json()
                    status = payment_data.get("status")
                    
                    logger.info(f"Payment {payment_id} status: {status}")
                    
                    return status in ["paid", "authorized"]
                else:
                    logger.error(f"Failed to verify payment {payment_id}: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            return False
    
    async def capture_payment(self, payment_id: str, amount: Optional[int] = None) -> Dict[str, Any]:
        """تأكيد وخصم المبلغ من البطاقة (للدفعات المعتمدة)"""
        
        if not self.secret_key:
            logger.error("Cannot capture payment without secret key")
            return {
                "success": False,
                "error": "Moyasar not configured"
            }
        
        try:
            capture_data = {}
            if amount:
                capture_data["amount"] = amount
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/payments/{payment_id}/capture",
                    json=capture_data,
                    headers=self.headers
                )
                
                response_data = response.json()
                
                if response.status_code == 200:
                    logger.info(f"Payment captured successfully: {payment_id}")
                    return {
                        "success": True,
                        "payment": response_data
                    }
                else:
                    logger.error(f"Payment capture failed: {response_data}")
                    return {
                        "success": False,
                        "error": response_data.get("message", "Payment capture failed")
                    }
                    
        except Exception as e:
            logger.error(f"Error capturing payment: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def void_payment(self, payment_id: str) -> Dict[str, Any]:
        """إلغاء دفعة معتمدة قبل خصمها"""
        
        if not self.secret_key:
            logger.error("Cannot void payment without secret key")
            return {
                "success": False,
                "error": "Moyasar not configured"
            }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/payments/{payment_id}/void",
                    headers=self.headers
                )
                
                response_data = response.json()
                
                if response.status_code == 200:
                    logger.info(f"Payment voided successfully: {payment_id}")
                    return {
                        "success": True,
                        "payment": response_data
                    }
                else:
                    logger.error(f"Payment void failed: {response_data}")
                    return {
                        "success": False,
                        "error": response_data.get("message", "Payment void failed")
                    }
                    
        except Exception as e:
            logger.error(f"Error voiding payment: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def refund_payment(
        self,
        payment_id: str,
        amount: Optional[int] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """استرجاع دفعة"""
        
        if not self.secret_key:
            logger.error("Cannot refund payment without secret key")
            return {
                "success": False,
                "error": "Moyasar not configured"
            }
        
        try:
            refund_data = {}
            if amount:
                refund_data["amount"] = amount
            if reason:
                refund_data["description"] = reason
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/payments/{payment_id}/refund",
                    json=refund_data,
                    headers=self.headers
                )
                
                response_data = response.json()
                
                if response.status_code == 201:
                    logger.info(f"Payment refunded successfully: {payment_id}")
                    return {
                        "success": True,
                        "refund": response_data
                    }
                else:
                    logger.error(f"Payment refund failed: {response_data}")
                    return {
                        "success": False,
                        "error": response_data.get("message", "Payment refund failed")
                    }
                    
        except Exception as e:
            logger.error(f"Error refunding payment: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def list_payments(
        self,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """جلب قائمة المدفوعات"""
        
        if not self.secret_key:
            logger.error("Cannot list payments without secret key")
            return {
                "success": False,
                "error": "Moyasar not configured"
            }
        
        try:
            params = {
                "page": page,
                "per_page": per_page
            }
            if status:
                params["status"] = status
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/payments",
                    params=params,
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "payments": response.json()
                    }
                else:
                    logger.error(f"Failed to list payments: {response.status_code}")
                    return {
                        "success": False,
                        "error": "Failed to list payments"
                    }
                    
        except Exception as e:
            logger.error(f"Error listing payments: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """التحقق من توقيع Webhook"""
        
        webhook_secret = os.getenv('MOYASAR_WEBHOOK_SECRET')
        if not webhook_secret:
            logger.warning("Webhook secret not configured")
            return True  # في وضع التطوير
        
        try:
            import hmac
            import hashlib
            
            expected_signature = hmac.new(
                webhook_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
    
    async def create_invoice(
        self,
        amount: int,
        currency: str = "SAR",
        description: str = "",
        expire_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """إنشاء فاتورة"""
        
        if not self.secret_key:
            logger.error("Cannot create invoice without secret key")
            return {
                "success": False,
                "error": "Moyasar not configured"
            }
        
        try:
            invoice_data = {
                "amount": amount,
                "currency": currency,
                "description": description,
                "metadata": metadata or {}
            }
            
            if expire_at:
                invoice_data["expire_at"] = expire_at
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/invoices",
                    json=invoice_data,
                    headers=self.headers
                )
                
                response_data = response.json()
                
                if response.status_code == 201:
                    logger.info(f"Invoice created successfully: {response_data.get('id')}")
                    return {
                        "success": True,
                        "invoice": response_data
                    }
                else:
                    logger.error(f"Invoice creation failed: {response_data}")
                    return {
                        "success": False,
                        "error": response_data.get("message", "Invoice creation failed")
                    }
                    
        except Exception as e:
            logger.error(f"Error creating invoice: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }