# app/services/email_service.py
import smtplib
import ssl
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import asyncio
import aiosmtplib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from jinja2 import Template
from pathlib import Path

logger = logging.getLogger(__name__)

class ZohoEmailService:
    """خدمة الإيميلات باستخدام Zoho SMTP للإنتاج"""
    
    def __init__(self):
        # إعدادات Zoho SMTP
        self.smtp_server = "smtp.zoho.com"
        self.username = os.getenv("ZOHO_EMAIL_USERNAME")
        self.password = os.getenv("ZOHO_EMAIL_PASSWORD")
        
        # إعدادات عامة
        self.from_email = os.getenv("FROM_EMAIL", self.username)
        self.from_name = os.getenv("FROM_NAME", "SEO Raysa Team")
        self.frontend_url = os.getenv("FRONTEND_URL", "https://www.seoraysa.com")
        self.support_email = os.getenv("SUPPORT_EMAIL", "seo@seoraysa.com")
        
        # مجلد القوالب
        self.templates_dir = Path(__file__).parent.parent / "templates" / "emails"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # التحقق من الإعدادات
        if not self.username or not self.password:
            logger.error("Zoho email credentials not configured")
            raise ValueError("Zoho email credentials are required")
            
        logger.info("Zoho Email Service initialized successfully")

    async def send_email_smtp(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """إرسال إيميل عبر Zoho SMTP"""
        try:
            # إنشاء الرسالة
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            message["Reply-To"] = self.from_email
            
            # Message-ID بالنطاق الصحيح
            domain = self.from_email.split('@')[1] if '@' in self.from_email else 'seoraysa.com'
            message["Message-ID"] = f"<{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}@{domain}>"
            
            # Headers إضافية
            message["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
            message["X-Mailer"] = "SEO Raysa System"
            message["X-Priority"] = "3"

            # إضافة النص العادي
            if text_content:
                text_part = MIMEText(text_content, "plain", "utf-8")
                message.attach(text_part)

            # إضافة HTML
            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)

            logger.info(f"Sending email to {to_email}")
            
            # محاولة إرسال عبر SSL (منفذ 465)
            try:
                async with aiosmtplib.SMTP(
                    hostname=self.smtp_server,
                    port=465,
                    use_tls=True,
                    timeout=60
                ) as server:
                    await server.login(self.username, self.password)
                    await server.send_message(message)
                    logger.info(f"Email sent successfully to {to_email}")
                    
                return True
                
            except Exception as ssl_error:
                logger.warning(f"SSL failed, trying STARTTLS: {str(ssl_error)}")
                
                # محاولة إرسال عبر STARTTLS (منفذ 587)
                async with aiosmtplib.SMTP(
                    hostname=self.smtp_server,
                    port=587,
                    use_tls=False,
                    start_tls=False,
                    timeout=60
                ) as server:
                    await server.starttls()
                    await server.login(self.username, self.password)
                    await server.send_message(message)
                    logger.info(f"Email sent successfully to {to_email} via STARTTLS")
                    
                return True

        except aiosmtplib.SMTPAuthenticationError as auth_error:
            logger.error(f"SMTP authentication failed: {str(auth_error)}")
            return False
            
        except aiosmtplib.SMTPRecipientsRefused as recipient_error:
            logger.error(f"Recipient refused {to_email}: {str(recipient_error)}")
            return False
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    async def send_email_with_retry(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        max_retries: int = 3
    ) -> bool:
        """إرسال إيميل مع إعادة المحاولة"""
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Email attempt #{attempt + 1} to {to_email}")
                
                success = await self.send_email_smtp(to_email, subject, html_content, text_content)
                
                if success:
                    return True
                    
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                logger.error(f"Error in attempt #{attempt + 1}: {str(e)}")
                
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    await asyncio.sleep(wait_time)
        
        logger.error(f"Failed to send email to {to_email} after {max_retries} attempts")
        return False

    async def test_connection(self) -> bool:
        """اختبار الاتصال بخادم Zoho SMTP"""
        try:
            logger.info("Testing Zoho SMTP connection...")
            
            # اختبار منفذ 465
            try:
                async with aiosmtplib.SMTP(
                    hostname=self.smtp_server,
                    port=465,
                    use_tls=True,
                    timeout=30
                ) as server:
                    await server.login(self.username, self.password)
                    logger.info("Port 465 connection test successful")
                    return True
            except Exception as ssl_error:
                logger.warning(f"Port 465 test failed: {str(ssl_error)}")
            
            # اختبار منفذ 587
            try:
                async with aiosmtplib.SMTP(
                    hostname=self.smtp_server,
                    port=587,
                    use_tls=False,
                    timeout=30
                ) as server:
                    await server.starttls()
                    await server.login(self.username, self.password)
                    logger.info("Port 587 connection test successful")
                    return True
            except Exception as starttls_error:
                logger.warning(f"Port 587 test failed: {str(starttls_error)}")
            
            logger.error("All connection tests failed")
            return False
            
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False

    def load_template(self, template_name: str) -> str:
        """تحميل قالب HTML"""
        template_path = self.templates_dir / f"{template_name}.html"
        
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            default_template = self.get_default_template()
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(default_template)
            return default_template

    def get_default_template(self) -> str:
        """قالب HTML افتراضي احترافي"""
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
            padding: 20px;
            background-color: #f5f7fa;
            direction: rtl;
            text-align: right;
            line-height: 1.6;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background-color: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 28px;
            font-weight: bold;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        .content {
            padding: 40px 30px;
            color: #333;
        }
        .content h2 {
            color: #2c3e50;
            margin-top: 0;
        }
        .button {
            display: inline-block;
            padding: 15px 35px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important;
            text-decoration: none;
            border-radius: 30px;
            font-weight: bold;
            margin: 25px 0;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }
        .button:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }
        .info-box {
            background: linear-gradient(135deg, #f8f9ff 0%, #e3f2fd 100%);
            border: 2px solid #e1e5f8;
            border-radius: 12px;
            padding: 20px;
            margin: 25px 0;
        }
        .info-box.warning {
            background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%);
            border-color: #ffb74d;
        }
        .info-box.success {
            background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
            border-color: #81c784;
        }
        .footer {
            background-color: #f8f9fa;
            padding: 25px;
            text-align: center;
            font-size: 14px;
            color: #666;
            border-top: 1px solid #eee;
        }
        .footer a {
            color: #667eea;
            text-decoration: none;
        }
        .emoji {
            font-size: 1.2em;
            margin-left: 5px;
        }
        ul, ol {
            padding-right: 20px;
        }
        code {
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            color: #e74c3c;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ header_title | default('🚀 SEO Raysa Team') }}</h1>
        </div>
        <div class="content">
            {{ content }}
        </div>
        <div class="footer">
            <p><strong>This is an automated email from SEO Raysa System</strong></p>
            <p>
                <a href="{{ frontend_url }}">🌐 Website</a> | 
                <a href="mailto:{{ support_email }}">📞 Support</a> |
                <a href="{{ frontend_url }}/unsubscribe">❌ Unsubscribe</a>
            </p>
            <p style="margin-top: 15px; color: #999; font-size: 12px;">
                © {{ current_year }} All rights reserved - SEO Raysa
            </p>
        </div>
    </div>
</body>
</html>
        """

    def render_template(self, template_content: str, variables: Dict[str, Any]) -> str:
        """تطبيق المتغيرات على القالب"""
        try:
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
            logger.error(f"Template rendering error: {str(e)}")
            return template_content

    async def send_store_welcome_email(
        self,
        store_email: str,
        store_name: str,
        store_id: str,
        verification_token: str,
        products_count: int = 0
    ) -> bool:
        """إرسال إيميل ترحيب للمتجر الجديد"""
        
        verification_link = f"{self.frontend_url}/connect-store?token={verification_token}"
        
        content = f"""
        <h2>🎉 Welcome! SEO optimization app installed successfully</h2>
        
        <p>Hello <strong>{store_name}</strong> owner!</p>
        
        <p>Your store has been successfully connected to our SEO optimization system. Now you can benefit from:</p>
        
        <ul>
            <li><span class="emoji">🔍</span> Automatic analysis for all your products ({products_count} products)</li>
            <li><span class="emoji">🤖</span> AI-powered SEO optimization</li>
            <li><span class="emoji">📈</span> Increased visibility in search results</li>
            <li><span class="emoji">📊</span> Comprehensive reports on your store performance</li>
        </ul>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verification_link}" class="button">
                🚀 Start optimizing your store now
            </a>
        </div>
        
        <div class="info-box">
            <p><strong>📝 Important information:</strong></p>
            <p>• Your store ID: <code>#{store_id}</code></p>
            <p>• Valid for 7 days from this email date</p>
            <p>• If you already have an account, login first then click the link</p>
        </div>
        
        <p>Need help? Don't hesitate to <a href="mailto:{self.support_email}">contact us</a></p>
        
        <p>Best regards, SEO Raysa Team ❤️</p>
        """
        
        variables = {
            'header_title': f'🎉 Welcome {store_name}',
            'content': content
        }
        
        template_content = self.load_template('store_welcome')
        html_content = self.render_template(template_content, variables)
        
        return await self.send_email_with_retry(
            to_email=store_email,
            subject=f"🎉 Welcome! {store_name} connected successfully",
            html_content=html_content
        )

    async def send_store_reminder_email(
        self,
        store_email: str,
        store_name: str,
        store_id: str,
        verification_token: str,
        days_remaining: int
    ) -> bool:
        """إرسال إيميل تذكير للمتجر"""
        
        verification_link = f"{self.frontend_url}/connect-store?token={verification_token}"
        
        content = f"""
        <h2>⏰ Important reminder: Connect {store_name}</h2>
        
        <p>Hello!</p>
        
        <p>We remind you that the SEO optimization app was installed in your store <strong>{store_name}</strong> yesterday, but it hasn't been connected to your account yet.</p>
        
        <div class="info-box warning">
            <p><strong>⚠️ Attention:</strong></p>
            <p>Only <strong>{days_remaining} days</strong> remaining to connect your store before the link expires</p>
        </div>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verification_link}" class="button">
                🔗 Connect store now
            </a>
        </div>
        
        <p><strong>Why should you connect your store?</strong></p>
        <ul>
            <li><span class="emoji">🚀</span> Automatic SEO optimization for all your products</li>
            <li><span class="emoji">📈</span> Increase sales through search engines</li>
            <li><span class="emoji">🎯</span> Better targeting of potential customers</li>
            <li><span class="emoji">📊</span> Detailed reports on your store performance</li>
        </ul>
        
        <p>If you don't connect within {days_remaining} days, you'll need to reinstall the app again.</p>
        
        <p>Best regards, SEO Raysa Team 💙</p>
        """
        
        variables = {
            'header_title': f'⏰ Reminder: {store_name}',
            'content': content
        }
        
        template_content = self.load_template('store_reminder')
        html_content = self.render_template(template_content, variables)
        
        return await self.send_email_with_retry(
            to_email=store_email,
            subject=f"⏰ Important reminder: Connect {store_name} ({days_remaining} days remaining)",
            html_content=html_content
        )

    async def send_store_connected_email(
        self,
        user_email: str,
        user_name: str,
        store_name: str,
        products_synced: int = 0
    ) -> bool:
        """إرسال إيميل تأكيد الربط"""
        
        dashboard_link = f"{self.frontend_url}/products"
        
        content = f"""
        <h2>🎉 Your store has been connected successfully!</h2>
        
        <p>Hello <strong>{user_name}</strong>!</p>
        
        <p>Congratulations! Store <strong>{store_name}</strong> has been successfully connected to your account.</p>
        
        <div class="info-box success">
            <p><strong>✅ What has been accomplished:</strong></p>
            <p>• Store connected to your account</p>
            <p>• {products_synced} products synchronized</p>
            <p>• SEO analysis started for products</p>
        </div>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{dashboard_link}" class="button">
                📊 View dashboard
            </a>
        </div>
        
        <p><strong>Next steps:</strong></p>
        <ol>
            <li>Review SEO analysis for your products</li>
            <li>Apply suggested recommendations</li>
            <li>Monitor improvement in your store's search ranking</li>
        </ol>
        
        <p>We're excited to help you improve your store performance!</p>
        
        <p>Best regards, SEO Raysa Team 🚀</p>
        """
        
        variables = {
            'header_title': f'🎉 {store_name} connected successfully',
            'content': content
        }
        
        template_content = self.load_template('store_connected')
        html_content = self.render_template(template_content, variables)
        
        return await self.send_email_with_retry(
            to_email=user_email,
            subject=f"🎉 Store {store_name} connected successfully!",
            html_content=html_content
        )

# إنشاء instance عالمي
email_service = ZohoEmailService()

# دوال مساعدة
async def send_welcome_email(store_email: str, store_name: str, store_id: str, verification_token: str, products_count: int = 0):
    return await email_service.send_store_welcome_email(
        store_email, store_name, store_id, verification_token, products_count
    )

async def test_email_connection():
    """اختبار اتصال الإيميل"""
    return await email_service.test_connection()