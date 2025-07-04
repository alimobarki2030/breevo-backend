# ملف routers/google_analytics.py

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db, Base
from app.models.user import User
from app.services.google_analytics_service import GoogleAnalyticsService
from app.routers.auth import get_current_user

# إنشاء router جديد
router = APIRouter(prefix="/api/google", tags=["google_analytics"])
google_service = GoogleAnalyticsService()

# نموذج قاعدة البيانات لحفظ بيانات Google
class GoogleAnalyticsAccount(Base):
    """جدول لحفظ حسابات Google Analytics المربوطة"""
    __tablename__ = "google_analytics_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # بيانات Google OAuth
    google_email = Column(String, index=True)
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime)
    
    # بيانات Analytics
    analytics_account_id = Column(String)
    analytics_account_name = Column(String)
    property_id = Column(String)
    property_name = Column(String)
    website_url = Column(String)
    
    # بيانات Search Console
    search_console_site = Column(String)
    permission_level = Column(String)
    
    # إعدادات
    auto_sync_enabled = Column(Boolean, default=True)
    last_sync_at = Column(DateTime)
    
    # تواريخ
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    user = relationship("User", back_populates="google_accounts")
    reports = relationship("AnalyticsReport", back_populates="google_account")

class AnalyticsReport(Base):
    """جدول لحفظ تقارير Analytics"""
    __tablename__ = "analytics_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    google_account_id = Column(Integer, ForeignKey("google_analytics_accounts.id"))
    
    # بيانات التقرير
    report_type = Column(String)  # performance, top_pages, seo_opportunities
    date_range = Column(String)   # 7d, 30d, 90d
    data = Column(JSON)           # البيانات الفعلية
    
    # تواريخ
    generated_at = Column(DateTime, default=datetime.utcnow)
    
    # العلاقات
    google_account = relationship("GoogleAnalyticsAccount", back_populates="reports")

# ===== Endpoints =====

@router.get("/auth/url")
async def get_google_auth_url(
    analytics: bool = False,
    store_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """الحصول على رابط OAuth لربط Google"""
    try:
        state = json.dumps({
            "user_id": current_user.id,
            "analytics": analytics,
            "store_id": store_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        redirect_uri = f"{os.getenv('FRONTEND_URL')}/auth/google/callback"
        auth_url = google_service.get_oauth_url(redirect_uri, state)
        
        return {
            "authorization_url": auth_url,
            "state": state,
            "message": "افتح الرابط لربط حساب Google"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في إنشاء رابط الربط: {str(e)}")

@router.post("/auth/callback")
async def handle_google_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """معالجة callback من Google OAuth"""
    try:
        # فك تشفير state
        state_data = json.loads(state)
        user_id = state_data["user_id"]
        analytics_mode = state_data.get("analytics", False)
        store_id = state_data.get("store_id")
        
        # التحقق من المستخدم
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")
        
        # تبديل code بـ tokens
        redirect_uri = f"{os.getenv('FRONTEND_URL')}/auth/google/callback"
        token_data = await google_service.exchange_code_for_tokens(code, redirect_uri)
        
        if "access_token" not in token_data:
            raise HTTPException(status_code=400, detail="فشل في الحصول على رمز الوصول")
        
        # إنشاء credentials
        credentials = google_service.create_credentials(token_data)
        
        # جلب حسابات Analytics
        analytics_accounts = await google_service.get_analytics_accounts(credentials)
        search_console_sites = await google_service.get_search_console_sites(credentials)
        
        # جلب معلومات المستخدم من Google
        user_info = await get_google_user_info(credentials)
        google_email = user_info.get("email", "")
        
        # البحث عن حساب Google موجود
        existing_account = db.query(GoogleAnalyticsAccount).filter(
            GoogleAnalyticsAccount.user_id == user_id,
            GoogleAnalyticsAccount.google_email == google_email
        ).first()
        
        if existing_account:
            # تحديث الحساب الموجود
            existing_account.access_token = token_data["access_token"]
            existing_account.refresh_token = token_data.get("refresh_token")
            existing_account.token_expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
            existing_account.updated_at = datetime.utcnow()
            google_account = existing_account
        else:
            # إنشاء حساب جديد
            # اختيار أول موقع/property متاح
            first_property = None
            first_site = None
            
            if analytics_accounts:
                for account in analytics_accounts:
                    if account["properties"]:
                        first_property = account["properties"][0]
                        break
            
            if search_console_sites:
                first_site = search_console_sites[0]
            
            google_account = GoogleAnalyticsAccount(
                user_id=user_id,
                google_email=google_email,
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                token_expires_at=datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600)),
                analytics_account_id=first_property["id"] if first_property else None,
                analytics_account_name=first_property["name"] if first_property else None,
                property_id=first_property["id"] if first_property else None,
                property_name=first_property["name"] if first_property else None,
                website_url=first_property.get("website_url", "") if first_property else "",
                search_console_site=first_site["site_url"] if first_site else None,
                permission_level=first_site["permission_level"] if first_site else None
            )
            db.add(google_account)
        
        db.commit()
        db.refresh(google_account)
        
        # إنشاء تقرير أولي في الخلفية
        background_tasks = BackgroundTasks()
        background_tasks.add_task(generate_initial_reports, db, google_account.id)
        
        # توجيه مناسب
        frontend_url = os.getenv("FRONTEND_URL")
        if store_id:
            # إذا كان قادم من ربط متجر سلة
            redirect_url = f"{frontend_url}/salla/welcome?store_id={store_id}&step=3&google_connected=true"
        elif analytics_mode:
            redirect_url = f"{frontend_url}/dashboard/analytics?google_connected=true"
        else:
            redirect_url = f"{frontend_url}/dashboard?google_connected=true"
        
        return {
            "success": True,
            "message": "تم ربط حساب Google بنجاح!",
            "redirect_url": redirect_url,
            "google_account": {
                "id": google_account.id,
                "email": google_account.google_email,
                "analytics_connected": bool(google_account.property_id),
                "search_console_connected": bool(google_account.search_console_site)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ خطأ في Google callback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"خطأ في ربط حساب Google: {str(e)}")

@router.get("/accounts")
async def get_google_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """جلب حسابات Google المربوطة"""
    try:
        accounts = db.query(GoogleAnalyticsAccount).filter(
            GoogleAnalyticsAccount.user_id == current_user.id
        ).all()
        
        return [
            {
                "id": account.id,
                "email": account.google_email,
                "analytics_account_name": account.analytics_account_name,
                "property_name": account.property_name,
                "website_url": account.website_url,
                "search_console_site": account.search_console_site,
                "analytics_connected": bool(account.property_id),
                "search_console_connected": bool(account.search_console_site),
                "last_sync": account.last_sync_at,
                "connected_at": account.created_at
            }
            for account in accounts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في جلب الحسابات: {str(e)}")

@router.get("/analytics/{account_id}/performance")
async def get_analytics_performance(
    account_id: int,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """جلب أداء الموقع من Analytics"""
    try:
        # التحقق من الحساب
        account = db.query(GoogleAnalyticsAccount).filter(
            GoogleAnalyticsAccount.id == account_id,
            GoogleAnalyticsAccount.user_id == current_user.id
        ).first()
        
        if not account:
            raise HTTPException(status_code=404, detail="حساب Google غير موجود")
        
        if not account.property_id:
            raise HTTPException(status_code=400, detail="لم يتم ربط Google Analytics")
        
        # إنشاء credentials
        credentials = google_service.create_credentials({
            "access_token": account.access_token,
            "refresh_token": account.refresh_token
        })
        
        # جلب البيانات
        performance_data = await google_service.get_website_performance(
            credentials, account.property_id, days
        )
        
        # حفظ التقرير
        report = AnalyticsReport(
            google_account_id=account.id,
            report_type="performance",
            date_range=f"{days}d",
            data=performance_data
        )
        db.add(report)
        db.commit()
        
        return {
            "account": {
                "id": account.id,
                "property_name": account.property_name,
                "website_url": account.website_url
            },
            "performance": performance_data,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في جلب بيانات الأداء: {str(e)}")

@router.get("/analytics/{account_id}/seo-opportunities")
async def get_seo_opportunities(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """تحليل فرص تحسين SEO"""
    try:
        # التحقق من الحساب
        account = db.query(GoogleAnalyticsAccount).filter(
            GoogleAnalyticsAccount.id == account_id,
            GoogleAnalyticsAccount.user_id == current_user.id
        ).first()
        
        if not account:
            raise HTTPException(status_code=404, detail="حساب Google غير موجود")
        
        # إنشاء credentials
        credentials = google_service.create_credentials({
            "access_token": account.access_token,
            "refresh_token": account.refresh_token
        })
        
        # تحليل الفرص
        opportunities = await google_service.analyze_seo_opportunities(
            credentials, 
            account.property_id, 
            account.search_console_site
        )
        
        # حفظ التقرير
        report = AnalyticsReport(
            google_account_id=account.id,
            report_type="seo_opportunities",
            date_range="30d",
            data=opportunities
        )
        db.add(report)
        db.commit()
        
        return {
            "account": {
                "id": account.id,
                "property_name": account.property_name
            },
            "opportunities": opportunities,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في تحليل فرص SEO: {str(e)}")

@router.post("/analytics/{account_id}/sync")
async def sync_analytics_data(
    account_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """مزامنة بيانات Analytics"""
    try:
        # التحقق من الحساب
        account = db.query(GoogleAnalyticsAccount).filter(
            GoogleAnalyticsAccount.id == account_id,
            GoogleAnalyticsAccount.user_id == current_user.id
        ).first()
        
        if not account:
            raise HTTPException(status_code=404, detail="حساب Google غير موجود")
        
        # بدء المزامنة في الخلفية
        background_tasks.add_task(sync_analytics_task, db, account.id)
        
        return {
            "success": True,
            "message": "بدأت مزامنة بيانات Google Analytics في الخلفية"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في بدء المزامنة: {str(e)}")

@router.delete("/accounts/{account_id}")
async def disconnect_google_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """قطع ربط حساب Google"""
    try:
        account = db.query(GoogleAnalyticsAccount).filter(
            GoogleAnalyticsAccount.id == account_id,
            GoogleAnalyticsAccount.user_id == current_user.id
        ).first()
        
        if not account:
            raise HTTPException(status_code=404, detail="حساب Google غير موجود")
        
        # حذف التقارير المرتبطة
        db.query(AnalyticsReport).filter(
            AnalyticsReport.google_account_id == account_id
        ).delete()
        
        # حذف الحساب
        db.delete(account)
        db.commit()
        
        return {
            "success": True,
            "message": "تم قطع ربط حساب Google بنجاح"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في قطع الربط: {str(e)}")

# ===== Background Tasks =====

async def generate_initial_reports(db: Session, google_account_id: int):
    """توليد تقارير أولية بعد ربط الحساب"""
    try:
        account = db.query(GoogleAnalyticsAccount).filter(
            GoogleAnalyticsAccount.id == google_account_id
        ).first()
        
        if not account:
            return
        
        credentials = google_service.create_credentials({
            "access_token": account.access_token,
            "refresh_token": account.refresh_token
        })
        
        # توليد تقرير الأداء
        if account.property_id:
            performance_data = await google_service.get_website_performance(
                credentials, account.property_id, 30
            )
            
            report = AnalyticsReport(
                google_account_id=account.id,
                report_type="performance",
                date_range="30d",
                data=performance_data
            )
            db.add(report)
        
        # توليد تقرير فرص SEO
        if account.property_id and account.search_console_site:
            opportunities = await google_service.analyze_seo_opportunities(
                credentials, 
                account.property_id, 
                account.search_console_site
            )
            
            report = AnalyticsReport(
                google_account_id=account.id,
                report_type="seo_opportunities",
                date_range="30d",
                data=opportunities
            )
            db.add(report)
        
        # تحديث وقت آخر مزامنة
        account.last_sync_at = datetime.utcnow()
        db.commit()
        
        print(f"✅ تم توليد التقارير الأولية للحساب {account.google_email}")
        
    except Exception as e:
        print(f"❌ خطأ في توليد التقارير الأولية: {str(e)}")
        db.rollback()

async def sync_analytics_task(db: Session, google_account_id: int):
    """مهمة مزامنة بيانات Analytics"""
    try:
        account = db.query(GoogleAnalyticsAccount).filter(
            GoogleAnalyticsAccount.id == google_account_id
        ).first()
        
        if not account:
            return
        
        print(f"🔄 بدء مزامنة بيانات Google Analytics للحساب: {account.google_email}")
        
        credentials = google_service.create_credentials({
            "access_token": account.access_token,
            "refresh_token": account.refresh_token
        })
        
        # مزامنة بيانات مختلفة
        sync_count = 0
        
        # بيانات الأداء لفترات مختلفة
        for days in [7, 30, 90]:
            if account.property_id:
                performance_data = await google_service.get_website_performance(
                    credentials, account.property_id, days
                )
                
                # حفظ أو تحديث التقرير
                existing_report = db.query(AnalyticsReport).filter(
                    AnalyticsReport.google_account_id == account.id,
                    AnalyticsReport.report_type == "performance",
                    AnalyticsReport.date_range == f"{days}d"
                ).first()
                
                if existing_report:
                    existing_report.data = performance_data
                    existing_report.generated_at = datetime.utcnow()
                else:
                    report = AnalyticsReport(
                        google_account_id=account.id,
                        report_type="performance",
                        date_range=f"{days}d",
                        data=performance_data
                    )
                    db.add(report)
                
                sync_count += 1
        
        # أفضل الصفحات
        if account.property_id:
            top_pages = await google_service.get_top_pages(credentials, account.property_id)
            
            existing_report = db.query(AnalyticsReport).filter(
                AnalyticsReport.google_account_id == account.id,
                AnalyticsReport.report_type == "top_pages",
                AnalyticsReport.date_range == "30d"
            ).first()
            
            if existing_report:
                existing_report.data = {"pages": top_pages}
                existing_report.generated_at = datetime.utcnow()
            else:
                report = AnalyticsReport(
                    google_account_id=account.id,
                    report_type="top_pages",
                    date_range="30d",
                    data={"pages": top_pages}
                )
                db.add(report)
            
            sync_count += 1
        
        # فرص SEO
        if account.property_id and account.search_console_site:
            opportunities = await google_service.analyze_seo_opportunities(
                credentials, 
                account.property_id, 
                account.search_console_site
            )
            
            existing_report = db.query(AnalyticsReport).filter(
                AnalyticsReport.google_account_id == account.id,
                AnalyticsReport.report_type == "seo_opportunities",
                AnalyticsReport.date_range == "30d"
            ).first()
            
            if existing_report:
                existing_report.data = opportunities
                existing_report.generated_at = datetime.utcnow()
            else:
                report = AnalyticsReport(
                    google_account_id=account.id,
                    report_type="seo_opportunities",
                    date_range="30d",
                    data=opportunities
                )
                db.add(report)
            
            sync_count += 1
        
        # تحديث وقت آخر مزامنة
        account.last_sync_at = datetime.utcnow()
        db.commit()
        
        print(f"✅ انتهت مزامنة Google Analytics - تم تحديث {sync_count} تقرير")
        
    except Exception as e:
        print(f"❌ خطأ في مزامنة Google Analytics: {str(e)}")
        db.rollback()

# ===== Helper Functions =====

async def get_google_user_info(credentials):
    """جلب معلومات المستخدم من Google"""
    try:
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        return user_info
    except Exception as e:
        print(f"Error fetching Google user info: {e}")
        return {}