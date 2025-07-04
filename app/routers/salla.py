# إضافة في app/routers/salla.py

import secrets
import string
from app.services.email_service import EmailService
from app.utils.password import get_password_hash, generate_random_password

email_service = EmailService()

@router.post("/oauth/callback")
async def handle_oauth_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """معالجة callback من سلة مع إنشاء حساب تلقائي مُحسن"""
    try:
        print(f"🔄 بدء التسجيل التلقائي لعميل سلة")
        
        # 1. تبديل code بـ access token
        token_data = await salla_service.exchange_code_for_tokens(code)
        
        if "access_token" not in token_data:
            raise HTTPException(status_code=400, detail="فشل في الحصول على رمز الوصول")
        
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        
        # 2. جلب معلومات المتجر
        store_info = await salla_service.get_store_info(access_token)
        if "data" not in store_info:
            raise HTTPException(status_code=400, detail="فشل في جلب معلومات المتجر")
        
        store_data = store_info["data"]
        
        # 3. جلب معلومات المالك/المدير
        try:
            owner_info = await salla_service.get_store_owner(access_token)
            owner_data = owner_info.get("data", {})
        except:
            owner_data = {}
        
        # 4. تحديد بيانات المستخدم الجديد
        user_email = owner_data.get("email") or f"{store_data.get('id')}@salla.store"
        user_name = owner_data.get("name") or store_data.get("name", "مالك المتجر")
        store_name = store_data.get("name", "متجر سلة")
        
        # 5. التحقق من وجود مستخدم بنفس الإيميل
        existing_user = db.query(User).filter(User.email == user_email).first()
        
        if existing_user:
            # المستخدم موجود - ربط المتجر الجديد
            user = existing_user
            action = "ربط متجر إضافي"
            print(f"✅ ربط متجر جديد مع حساب موجود: {user_email}")
        else:
            # إنشاء مستخدم جديد
            random_password = generate_random_password()
            
            new_user = User(
                email=user_email,
                username=f"salla_{store_data.get('id')}",
                full_name=user_name,
                hashed_password=get_password_hash(random_password),
                is_verified=True,  # حساب موثق من سلة
                is_active=True,
                registration_source="salla_auto",
                # إضافة معلومات إضافية
                phone=owner_data.get("mobile"),
                created_via_salla=True
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            user = new_user
            action = "تسجيل حساب جديد"
            print(f"✅ تم إنشاء حساب جديد: {user_email}")
            
            # إرسال بيانات الدخول بالإيميل
            await send_welcome_email_with_credentials(
                user_email, user_name, store_name, random_password
            )
        
        # 6. ربط المتجر مع المستخدم
        existing_store = db.query(SallaStore).filter(
            SallaStore.store_id == str(store_data.get("id"))
        ).first()
        
        if existing_store:
            # تحديث المتجر الموجود
            existing_store.user_id = user.id
            existing_store.access_token = access_token
            existing_store.refresh_token = refresh_token
            existing_store.token_expires_at = datetime.utcnow() + timedelta(days=14)
            existing_store.store_name = store_data.get("name")
            existing_store.store_domain = store_data.get("domain")
            existing_store.store_plan = store_data.get("plan")
            existing_store.store_status = store_data.get("status")
            existing_store.updated_at = datetime.utcnow()
            store = existing_store
        else:
            # إنشاء متجر جديد
            store = SallaStore(
                user_id=user.id,
                store_id=str(store_data.get("id")),
                store_name=store_data.get("name"),
                store_domain=store_data.get("domain"),
                store_plan=store_data.get("plan"),
                store_status=store_data.get("status"),
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=datetime.utcnow() + timedelta(days=14),
                webhook_secret=str(uuid.uuid4()),
                auto_sync_enabled=True
            )
            db.add(store)
        
        db.commit()
        db.refresh(store)
        
        # 7. إنشاء JWT token للمستخدم
        access_token_jwt = create_access_token(data={"sub": user.email})
        
        # 8. بدء مزامنة المنتجات في الخلفية
        background_tasks = BackgroundTasks()
        background_tasks.add_task(sync_products_task, db, store)
        
        # 9. توجيه المستخدم لصفحة الترحيب
        frontend_url = os.getenv("FRONTEND_URL")
        redirect_url = f"{frontend_url}/welcome?token={access_token_jwt}&store_id={store.id}&action={action}&store_name={store_name}"
        
        return RedirectResponse(url=redirect_url)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ خطأ في التسجيل التلقائي: {str(e)}")
        error_url = f"{os.getenv('FRONTEND_URL')}/error?message=حدث خطأ في ربط المتجر"
        return RedirectResponse(url=error_url)


async def send_welcome_email_with_credentials(email: str, name: str, store_name: str, password: str):
    """إرسال إيميل ترحيب مع بيانات الدخول"""
    try:
        subject = f"مرحباً بك! تم ربط متجر {store_name} بنجاح"
        
        html_content = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="ar">
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; direction: rtl; text-align: right; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: white; padding: 30px; border: 1px solid #e0e0e0; }}
                .credentials {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-right: 4px solid #007bff; }}
                .footer {{ background: #f8f9fa; padding: 20px; text-align: center; border-radius: 0 0 10px 10px; color: #666; }}
                .button {{ display: inline-block; background: #007bff; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 15px 5px; }}
                .warning {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 مرحباً بك، {name}!</h1>
                    <p>تم ربط متجر "{store_name}" بنجاح مع منصتنا</p>
                </div>
                
                <div class="content">
                    <h2>✅ تم إنشاء حساب جديد لك</h2>
                    <p>لقد قمنا بإنشاء حساب جديد لك تلقائياً لتتمكن من إدارة متجرك وأدوات SEO.</p>
                    
                    <div class="credentials">
                        <h3>🔐 بيانات الدخول الخاصة بك:</h3>
                        <p><strong>الإيميل:</strong> {email}</p>
                        <p><strong>كلمة المرور:</strong> <code style="background:#e9ecef;padding:5px 10px;border-radius:3px;">{password}</code></p>
                    </div>
                    
                    <div class="warning">
                        <strong>⚠️ مهم:</strong> احفظ هذه البيانات في مكان آمن. يمكنك تغيير كلمة المرور بعد تسجيل الدخول.
                    </div>
                    
                    <h3>🚀 ماذا بعد؟</h3>
                    <ul>
                        <li>يمكنك الآن الدخول لحسابك من أي متصفح أو جهاز</li>
                        <li>سيتم مزامنة منتجات متجرك تلقائياً</li>
                        <li>ستحصل على أدوات SEO متقدمة لمنتجاتك</li>
                        <li>إدارة شاملة لمتجرك ومنتجاتك</li>
                    </ul>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{os.getenv('FRONTEND_URL')}/login" class="button">تسجيل الدخول الآن</a>
                        <a href="{os.getenv('FRONTEND_URL')}/dashboard" class="button" style="background: #28a745;">الذهاب للوحة التحكم</a>
                    </div>
                </div>
                
                <div class="footer">
                    <p>إذا لم تقم بربط هذا المتجر، يرجى تجاهل هذا الإيميل.</p>
                    <p>فريق الدعم | <a href="mailto:support@yoursite.com">support@yoursite.com</a></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        await email_service.send_email(
            to_email=email,
            subject=subject,
            html_content=html_content
        )
        
        print(f"✅ تم إرسال إيميل الترحيب لـ {email}")
        
    except Exception as e:
        print(f"❌ خطأ في إرسال إيميل الترحيب: {str(e)}")


def generate_random_password(length: int = 12) -> str:
    """توليد كلمة مرور عشوائية قوية"""
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    # ضمان وجود حرف كبير وصغير ورقم ورمز
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase), 
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*")
    ]
    
    # ملء باقي الطول
    for _ in range(length - 4):
        password.append(secrets.choice(characters))
    
    # خلط الترتيب
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)


# إضافة في salla_api.py
async def get_store_owner(self, access_token: str) -> Dict:
    """جلب معلومات مالك المتجر من سلة"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{self.base_url}/profile",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            return response.json()
        except:
            # إذا فشل جلب معلومات المالك، نرجع بيانات فارغة
            return {"data": {}}