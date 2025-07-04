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
    """خدمة الإيميلات باستخدام Zoho TransMail - مُصححة"""
    
    def __init__(self):
        # إعدادات Zoho SMTP المُصححة
        self.smtp_server = "smtp.zoho.com"
        self.smtp_port = 587  # استخدام STARTTLS فقط
        self.username = os.getenv("ZOHO_EMAIL_USERNAME")
        self.password = os.getenv("ZOHO_EMAIL_PASSWORD")
        
        # إعدادات Zoho API (للمميزات المتقدمة)
        self.api_key = os.getenv("ZOHO_API_KEY")
        self.api_url = "https://transmail.zoho.com/v1/email"
        
        # إعدادات عامة مُصححة
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
            
        # التحقق من صحة عنوان الإيميل
        self._validate_email_config()

    def _validate_email_config(self):
        """التحقق من صحة إعدادات الإيميل"""
        if self.test_mode:
            return
            
        # التأكد من أن البريد الإلكتروني ينتهي بنطاق صحيح
        if self.from_email and not self.from_email.endswith(('@zoho.com', '@gmail.com')) and '@' in self.from_email:
            domain = self.from_email.split('@')[1]
            logger.info(f"📧 استخدام النطاق المخصص: {domain}")
        
        # التحقق من متغيرات البيئة المطلوبة
        required_vars = {
            'ZOHO_EMAIL_USERNAME': self.username,
            'ZOHO_EMAIL_PASSWORD': self.password,
            'FROM_EMAIL': self.from_email
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        if missing_vars:
            logger.error(f"❌ متغيرات البيئة المفقودة: {', '.join(missing_vars)}")

    async def send_email_smtp(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """إرسال إيميل عبر Zoho SMTP - مُصحح تماماً"""
        try:
            if self.test_mode:
                logger.info(f"📧 [وضع الاختبار] إيميل لـ {to_email}")
                logger.info(f"📋 الموضوع: {subject}")
                logger.info(f"📄 المحتوى: {html_content[:200]}...")
                return True

            # إنشاء الرسالة مع ترميز صحيح
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            message["Reply-To"] = self.from_email
            
            # إضافة headers إضافية لتحسين التسليم
            message["Message-ID"] = f"<{datetime.now().strftime('%Y%m%d%H%M%S')}@{self.from_email.split('@')[1]}>"
            message["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")

            # إضافة النص العادي إذا توفر
            if text_content:
                text_part = MIMEText(text_content, "plain", "utf-8")
                message.attach(text_part)

            # إضافة HTML
            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)

            # ✅ الطريقة المُصححة: استخدام STARTTLS فقط مع المنفذ 587
            try:
                logger.info(f"🔄 محاولة إرسال إيميل لـ {to_email}...")
                
                async with aiosmtplib.SMTP(
                    hostname=self.smtp_server,
                    port=self.smtp_port,  # 587 للـ STARTTLS
                    use_tls=False,        # لا نستخدم TLS مباشرة
                    timeout=60            # زيادة المهلة الزمنية
                ) as server:
                    # بدء STARTTLS أولاً
                    await server.starttls()
                    logger.info(f"✅ تم تفعيل STARTTLS بنجاح")
                    
                    # تسجيل الدخول
                    await server.login(self.username, self.password)
                    logger.info(f"✅ تم تسجيل الدخول بنجاح")
                    
                    # إرسال الرسالة
                    await server.send_message(message)
                    logger.info(f"✅ تم إرسال الإيميل بنجاح لـ {to_email}")
                    
                return True

            except aiosmtplib.SMTPAuthenticationError as auth_error:
                logger.error(f"❌ خطأ في المصادقة: {str(auth_error)}")
                logger.error("💡 تحقق من اسم المستخدم وكلمة المرور في متغيرات البيئة")
                return False
                
            except aiosmtplib.SMTPRecipientsRefused as recipient_error:
                logger.error(f"❌ خطأ في عنوان المستقبل {to_email}: {str(recipient_error)}")
                return False
                
            except aiosmtplib.SMTPDataError as data_error:
                logger.error(f"❌ خطأ في بيانات الرسالة: {str(data_error)}")
                return False

        except Exception as e:
            logger.error(f"❌ فشل إرسال إيميل لـ {to_email}: {str(e)}")
            
            # طباعة تفاصيل إضافية للتشخيص
            logger.error(f"🔍 تفاصيل الخطأ:")
            logger.error(f"   - SMTP Server: {self.smtp_server}:{self.smtp_port}")
            logger.error(f"   - Username: {self.username}")
            logger.error(f"   - From Email: {self.from_email}")
            logger.error(f"   - To Email: {to_email}")
            
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
                logger.info(f"🔄 محاولة الإرسال #{attempt + 1} لـ {to_email}")
                
                success = await self.send_email_smtp(to_email, subject, html_content, text_content)
                
                if success:
                    return True
                    
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # تأخير متزايد
                    logger.info(f"⏱️ انتظار {wait_time} ثانية قبل إعادة المحاولة...")
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                logger.error(f"❌ خطأ في المحاولة #{attempt + 1}: {str(e)}")
                
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    await asyncio.sleep(wait_time)
        
        logger.error(f"❌ فشل إرسال الإيميل نهائياً بعد {max_retries} محاولات")
        return False

    async def test_connection(self) -> bool:
        """اختبار الاتصال بخادم Zoho SMTP"""
        try:
            if self.test_mode:
                logger.info("📧 [وضع الاختبار] اختبار الاتصال نجح")
                return True
                
            logger.info("🔍 اختبار الاتصال بخادم Zoho SMTP...")
            
            async with aiosmtplib.SMTP(
                hostname=self.smtp_server,
                port=self.smtp_port,
                use_tls=False,
                timeout=30
            ) as server:
                await server.starttls()
                await server.login(self.username, self.password)
                
            logger.info("✅ اختبار الاتصال نجح!")
            return True
            
        except Exception as e:
            logger.error(f"❌ فشل اختبار الاتصال: {str(e)}")
            return False

    # باقي الدوال تبقى كما هي...
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
        """قالب HTML افتراضي مُحسن"""
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
            <h1>{{ header_title | default('🚀 فريق تحسين السيو') }}</h1>
        </div>
        <div class="content">
            {{ content }}
        </div>
        <div class="footer">
            <p><strong>هذا إيميل تلقائي من نظام تحسين السيو</strong></p>
            <p>
                <a href="{{ frontend_url }}">🌐 الموقع الرئيسي</a> | 
                <a href="mailto:{{ support_email }}">📞 الدعم الفني</a> |
                <a href="{{ frontend_url }}/unsubscribe">❌ إلغاء الاشتراك</a>
            </p>
            <p style="margin-top: 15px; color: #999; font-size: 12px;">
                © {{ current_year }} جميع الحقوق محفوظة لفريق تحسين السيو
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
            logger.error(f"❌ خطأ في معالجة القالب: {str(e)}")
            return template_content

    # دوال الإيميلات المخصصة (نفس المحتوى السابق مع استخدام send_email_with_retry)
    async def send_store_welcome_email(
        self,
        store_email: str,
        store_name: str,
        store_id: str,
        verification_token: str,
        products_count: int = 0
    ) -> bool:
        """إرسال إيميل ترحيب مع إعادة المحاولة"""
        
        verification_link = f"{self.frontend_url}/connect-store?token={verification_token}"
        
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
            'content': content
        }
        
        template_content = self.load_template('store_welcome')
        html_content = self.render_template(template_content, variables)
        
        return await self.send_email_with_retry(
            to_email=store_email,
            subject=f"🎉 مبروك! تم ربط متجر {store_name} بنجاح",
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