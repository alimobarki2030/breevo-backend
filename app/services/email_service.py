# app/services/email_service.py
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import asyncio
import aiosmtplib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import httpx
from jinja2 import Template
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class ZohoEmailService:
    """خدمة الإيميلات باستخدام Zoho TransMail"""
    
    def __init__(self):
        # إعدادات Zoho SMTP
        self.smtp_server = "smtp.zoho.com"
        self.smtp_port = 587
        self.username = os.getenv("ZOHO_EMAIL_USERNAME")  # your-email@yourdomain.com
        self.password = os.getenv("ZOHO_EMAIL_PASSWORD")  # كلمة المرور أو app password
        
        # إعدادات Zoho API (للمميزات المتقدمة)
        self.api_key = os.getenv("ZOHO_API_KEY")  # اختياري للبداية
        self.api_url = "https://transmail.zoho.com/v1/email"
        
        # إعدادات عامة
        self.from_email = os.getenv("FROM_EMAIL", self.username)
        self.from_name = os.getenv("FROM_NAME", "فريق تحسين السيو")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        self.support_email = os.getenv("SUPPORT_EMAIL", "support@yoursite.com")
        
        # مجلد القوالب
        self.templates_dir = Path(__file__).parent.parent / "templates" / "emails"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # التحقق من الإعدادات
        if not self.username or not self.password:
            logger.warning("⚠️ إعدادات Zoho غير مكتملة - سيعمل في وضع الاختبار")
            self.test_mode = True
        else:
            self.test_mode = False
            logger.info("✅ تم تهيئة Zoho Email Service بنجاح")

    async def send_email_smtp(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """إرسال إيميل عبر Zoho SMTP - مُصحح لحل مشكلة TLS"""
        try:
            if self.test_mode:
                logger.info(f"📧 [TEST MODE] إيميل لـ {to_email}")
                logger.info(f"📋 الموضوع: {subject}")
                logger.info(f"📄 المحتوى: {html_content[:200]}...")
                return True

            # إنشاء الرسالة
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email

            # إضافة النص العادي إذا توفر
            if text_content:
                text_part = MIMEText(text_content, "plain", "utf-8")
                message.attach(text_part)

            # إضافة HTML
            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)

            # ✅ الحل المُصحح: استخدام SSL مباشرة مع port 465
            try:
                async with aiosmtplib.SMTP(
                    hostname=self.smtp_server, 
                    port=465,  # استخدام SSL port
                    use_tls=True,  # SSL مباشرة
                    timeout=30  # مهلة زمنية
                ) as server:
                    await server.login(self.username, self.password)
                    await server.send_message(message)

                logger.info(f"✅ تم إرسال إيميل بنجاح (SSL) لـ {to_email}")
                return True

            except Exception as ssl_error:
                logger.warning(f"⚠️ فشل SSL، محاولة STARTTLS لـ {to_email}: {str(ssl_error)}")
                
                # ✅ محاولة بديلة مع STARTTLS إذا فشل SSL
                async with aiosmtplib.SMTP(
                    hostname=self.smtp_server, 
                    port=587,  # STARTTLS port
                    use_tls=False,  # بدون TLS مباشرة
                    timeout=30
                ) as server:
                    await server.starttls()  # بدء TLS
                    await server.login(self.username, self.password)
                    await server.send_message(message)
                
                logger.info(f"✅ تم إرسال إيميل بنجاح (STARTTLS) لـ {to_email}")
                return True

        except Exception as e:
            logger.error(f"❌ فشل إرسال إيميل لـ {to_email}: {str(e)}")
            return False

    async def send_email_api(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        template_id: Optional[str] = None
    ) -> bool:
        """إرسال إيميل عبر Zoho API (للمميزات المتقدمة)"""
        if not self.api_key:
            # تراجع للـ SMTP إذا لم يوجد API key
            return await self.send_email_smtp(to_email, subject, html_content, text_content)

        try:
            headers = {
                "Authorization": f"Zoho-oauthtoken {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "from": {
                    "address": self.from_email,
                    "name": self.from_name
                },
                "to": [{"email": to_email}],
                "subject": subject,
                "htmlbody": html_content
            }

            if text_content:
                payload["textbody"] = text_content

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ تم إرسال إيميل عبر API لـ {to_email}")
                    return True
                else:
                    logger.error(f"❌ فشل API: {response.status_code} - {response.text}")
                    # تراجع للـ SMTP
                    return await self.send_email_smtp(to_email, subject, html_content, text_content)

        except Exception as e:
            logger.error(f"❌ خطأ في API: {str(e)}")
            # تراجع للـ SMTP
            return await self.send_email_smtp(to_email, subject, html_content, text_content)

    def load_template(self, template_name: str) -> str:
        """تحميل قالب HTML"""
        template_path = self.templates_dir / f"{template_name}.html"
        
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            # إنشاء قالب افتراضي بسيط
            default_template = self.get_default_template()
            # حفظ القالب الافتراضي
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(default_template)
            return default_template

    def get_default_template(self) -> str:
        """قالب HTML افتراضي مع تصميم عربي جميل"""
        return """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ subject }}</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
            direction: rtl;
            text-align: right;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background-color: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 20px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 24px;
            font-weight: bold;
        }
        .content {
            padding: 30px 20px;
            line-height: 1.6;
            color: #333;
        }
        .button {
            display: inline-block;
            padding: 12px 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important;
            text-decoration: none;
            border-radius: 25px;
            font-weight: bold;
            margin: 20px 0;
            transition: transform 0.2s;
        }
        .button:hover {
            transform: translateY(-2px);
        }
        .info-box {
            background-color: #f8f9ff;
            border: 1px solid #e1e5f8;
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
        }
        .footer {
            background-color: #f8f9fa;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #666;
            border-top: 1px solid #eee;
        }
        .footer a {
            color: #667eea;
            text-decoration: none;
        }
        .emoji {
            font-size: 1.2em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ header_title | default('🚀 فريق تحسين السيو') }}</h1>
        </div>
        <div class="content">
            {{ content }}
        </div>
        <div class="footer">
            <p>هذا إيميل تلقائي من نظام تحسين السيو</p>
            <p>
                <a href="{{ frontend_url }}">الموقع الرئيسي</a> | 
                <a href="mailto:{{ support_email }}">الدعم الفني</a> |
                <a href="{{ frontend_url }}/unsubscribe">إلغاء الاشتراك</a>
            </p>
            <p style="margin-top: 15px; color: #999;">
                © 2024 جميع الحقوق محفوظة لفريق تحسين السيو
            </p>
        </div>
    </div>
</body>
</html>
        """

    def render_template(self, template_content: str, variables: Dict[str, Any]) -> str:
        """تطبيق المتغيرات على القالب"""
        try:
            # إضافة متغيرات افتراضية
            default_vars = {
                'frontend_url': self.frontend_url,
                'support_email': self.support_email,
                'current_year': datetime.now().year,
                'current_date': datetime.now().strftime('%Y-%m-%d')
            }
            variables.update(default_vars)
            
            template = Template(template_content)
            return template.render(**variables)
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة القالب: {str(e)}")
            return template_content

    # ===== إيميلات مخصصة للتطبيق =====

    async def send_store_welcome_email(
        self,
        store_email: str,
        store_name: str,
        store_id: str,
        verification_token: str,
        products_count: int = 0
    ) -> bool:
        """إرسال إيميل ترحيب بعد تثبيت التطبيق في سلة"""
        
        verification_link = f"{self.frontend_url}/connect-store?token={verification_token}"
        
        # محتوى الإيميل
        content = f"""
        <h2>🎉 مبروك! تم تثبيت تطبيق تحسين السيو بنجاح</h2>
        
        <p>مرحباً صاحب متجر <strong>{store_name}</strong>!</p>
        
        <p>تم ربط متجرك بنظام تحسين السيو بنجاح. الآن يمكنك الاستفادة من:</p>
        
        <ul>
            <li><span class="emoji">🔍</span> تحليل تلقائي لجميع منتجاتك ({products_count} منتج)</li>
            <li><span class="emoji">🤖</span> تحسين السيو بالذكاء الاصطناعي</li>
            <li><span class="emoji">📈</span> زيادة الظهور في نتائج البحث</li>
            <li><span class="emoji">📊</span> تقارير شاملة عن أداء متجرك</li>
        </ul>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verification_link}" class="button">
                🚀 ابدأ تحسين متجرك الآن
            </a>
        </div>
        
        <div class="info-box">
            <p><strong>📝 معلومات مهمة:</strong></p>
            <p>• معرف متجرك: <code>#{store_id}</code></p>
            <p>• صالح لمدة 7 أيام من تاريخ هذا الإيميل</p>
            <p>• إذا كان لديك حساب مسبقاً، سجل دخول أولاً ثم اضغط الرابط</p>
        </div>
        
        <p>تحتاج مساعدة؟ لا تتردد في <a href="mailto:{self.support_email}">التواصل معنا</a></p>
        
        <p>مع تحيات فريق تحسين السيو ❤️</p>
        """
        
        variables = {
            'header_title': f'🎉 مرحباً بمتجر {store_name}',
            'content': content,
            'store_name': store_name,
            'store_id': store_id,
            'verification_link': verification_link,
            'products_count': products_count
        }
        
        template_content = self.load_template('store_welcome')
        html_content = self.render_template(template_content, variables)
        
        return await self.send_email_smtp(
            to_email=store_email,
            subject=f"🎉 مبروك! تم ربط متجر {store_name} بنجاح",
            html_content=html_content
        )

    async def send_store_reminder_email(
        self,
        store_email: str,
        store_name: str,
        store_id: str,
        verification_token: str,
        days_remaining: int = 6
    ) -> bool:
        """إرسال إيميل تذكير بربط المتجر"""
        
        verification_link = f"{self.frontend_url}/connect-store?token={verification_token}"
        
        content = f"""
        <h2>⏰ تذكير: لا تنس إكمال إعداد متجر {store_name}</h2>
        
        <p>مرحباً مرة أخرى!</p>
        
        <p>لاحظنا أنك لم تكمل ربط متجر <strong>{store_name}</strong> بحسابك بعد.</p>
        
        <div class="info-box" style="border-color: #f39c12; background-color: #fef9e7;">
            <p><strong>⚠️ تنبيه مهم:</strong></p>
            <p>الرابط سينتهي خلال <strong>{days_remaining} أيام</strong></p>
            <p>بعدها ستحتاج لإعادة تثبيت التطبيق من متجر سلة</p>
        </div>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verification_link}" class="button">
                🔗 إكمال ربط المتجر الآن
            </a>
        </div>
        
        <p><strong>🎁 ما تحصل عليه:</strong></p>
        <ul>
            <li>تحليل مجاني لجميع منتجاتك</li>
            <li>تحسينات سيو احترافية</li>
            <li>زيادة في مبيعاتك وظهورك</li>
        </ul>
        
        <p><strong>💡 بديل سريع:</strong></p>
        <p>يمكنك أيضاً ربط متجرك يدوياً:</p>
        <ol>
            <li>ادخل على: <a href="{self.frontend_url}/login">{self.frontend_url}/login</a></li>
            <li>سجل دخول أو أنشئ حساب جديد</li>
            <li>اذهب لإعدادات المتجر</li>
            <li>أدخل معرف المتجر: <code>#{store_id}</code></li>
        </ol>
        
        <p>أي استفسار؟ راسلنا على <a href="mailto:{self.support_email}">{self.support_email}</a></p>
        """
        
        variables = {
            'header_title': f'⏰ تذكير لمتجر {store_name}',
            'content': content,
            'store_name': store_name,
            'store_id': store_id,
            'verification_link': verification_link,
            'days_remaining': days_remaining
        }
        
        template_content = self.load_template('store_reminder')
        html_content = self.render_template(template_content, variables)
        
        return await self.send_email_smtp(
            to_email=store_email,
            subject=f"⏰ تذكير: إكمال إعداد متجر {store_name}",
            html_content=html_content
        )

    async def send_store_connected_email(
        self,
        user_email: str,
        user_name: str,
        store_name: str,
        products_synced: int = 0
    ) -> bool:
        """إرسال إيميل تأكيد ربط المتجر بنجاح"""
        
        dashboard_link = f"{self.frontend_url}/dashboard"
        products_link = f"{self.frontend_url}/products"
        
        content = f"""
        <h2>✅ تم ربط متجر {store_name} بنجاح!</h2>
        
        <p>مرحباً {user_name}،</p>
        
        <p>تهانينا! تم ربط متجر <strong>{store_name}</strong> بحسابك بنجاح وبدأنا في تحليل منتجاتك.</p>
        
        <div class="info-box" style="border-color: #27ae60; background-color: #eafaf1;">
            <p><strong>📊 ما تم إنجازه:</strong></p>
            <ul>
                <li>✅ ربط المتجر بحسابك</li>
                <li>✅ مزامنة {products_synced} منتج</li>
                <li>✅ تحليل السيو الأولي</li>
                <li>✅ إعداد التحديثات التلقائية</li>
            </ul>
        </div>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{dashboard_link}" class="button">
                📊 عرض لوحة التحكم
            </a>
            <a href="{products_link}" class="button" style="margin-right: 10px;">
                📦 إدارة المنتجات
            </a>
        </div>
        
        <p><strong>🚀 الخطوات التالية:</strong></p>
        <ol>
            <li>راجع تحليل السيو لمنتجاتك</li>
            <li>ابدأ بتحسين المنتجات التي تحتاج تطوير</li>
            <li>استخدم الذكاء الاصطناعي لتوليد محتوى محسن</li>
            <li>تابع التحسن في نتائج البحث</li>
        </ol>
        
        <p>🎯 <strong>نصيحة:</strong> ابدأ بالمنتجات الأكثر مبيعاً لتحقيق أسرع النتائج!</p>
        
        <p>نحن هنا لمساعدتك في رحلة تحسين متجرك. أي استفسار؟ <a href="mailto:{self.support_email}">تواصل معنا</a></p>
        
        <p>بالتوفيق في رحلة النجاح! 🌟</p>
        """
        
        variables = {
            'header_title': f'✅ نجح ربط {store_name}',
            'content': content,
            'user_name': user_name,
            'store_name': store_name,
            'products_synced': products_synced,
            'dashboard_link': dashboard_link,
            'products_link': products_link
        }
        
        template_content = self.load_template('store_connected')
        html_content = self.render_template(template_content, variables)
        
        return await self.send_email_smtp(
            to_email=user_email,
            subject=f"✅ تم ربط متجر {store_name} بنجاح!",
            html_content=html_content
        )

    async def send_password_reset_email(
        self,
        user_email: str,
        user_name: str,
        reset_token: str
    ) -> bool:
        """إرسال إيميل إعادة تعيين كلمة المرور"""
        
        reset_link = f"{self.frontend_url}/reset-password?token={reset_token}"
        
        content = f"""
        <h2>🔑 إعادة تعيين كلمة المرور</h2>
        
        <p>مرحباً {user_name}،</p>
        
        <p>تلقينا طلباً لإعادة تعيين كلمة المرور لحسابك.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_link}" class="button">
                🔑 إعادة تعيين كلمة المرور
            </a>
        </div>
        
        <div class="info-box" style="border-color: #e74c3c; background-color: #fdedec;">
            <p><strong>🔒 معلومات أمنية مهمة:</strong></p>
            <ul>
                <li>هذا الرابط صالح لمدة ساعة واحدة فقط</li>
                <li>إذا لم تطلب إعادة التعيين، تجاهل هذا الإيميل</li>
                <li>لا تشارك هذا الرابط مع أي شخص</li>
            </ul>
        </div>
        
        <p>إذا لم تطلب إعادة تعيين كلمة المرور، يمكنك تجاهل هذا الإيميل بأمان.</p>
        
        <p>لأي استفسارات أمنية، تواصل معنا فوراً على <a href="mailto:{self.support_email}">{self.support_email}</a></p>
        """
        
        variables = {
            'header_title': '🔑 إعادة تعيين كلمة المرور',
            'content': content,
            'user_name': user_name,
            'reset_link': reset_link
        }
        
        template_content = self.load_template('password_reset')
        html_content = self.render_template(template_content, variables)
        
        return await self.send_email_smtp(
            to_email=user_email,
            subject="🔑 إعادة تعيين كلمة المرور - تحسين السيو",
            html_content=html_content
        )

# إنشاء instance عالمي
email_service = ZohoEmailService()

# دوال مساعدة للاستخدام السهل
async def send_welcome_email(store_email: str, store_name: str, store_id: str, verification_token: str, products_count: int = 0):
    """دالة مساعدة لإرسال إيميل الترحيب"""
    return await email_service.send_store_welcome_email(
        store_email, store_name, store_id, verification_token, products_count
    )

async def send_reminder_email(store_email: str, store_name: str, store_id: str, verification_token: str, days_remaining: int = 6):
    """دالة مساعدة لإرسال إيميل التذكير"""
    return await email_service.send_store_reminder_email(
        store_email, store_name, store_id, verification_token, days_remaining
    )

async def send_connected_email(user_email: str, user_name: str, store_name: str, products_synced: int = 0):
    """دالة مساعدة لإرسال إيميل تأكيد الربط"""
    return await email_service.send_store_connected_email(
        user_email, user_name, store_name, products_synced
    )

async def send_password_reset(user_email: str, user_name: str, reset_token: str):
    """دالة مساعدة لإرسال إيميل إعادة تعيين كلمة المرور"""
    return await email_service.send_password_reset_email(
        user_email, user_name, reset_token
    )