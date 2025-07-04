# ملف services/google_analytics_service.py

import os
from google.analytics.admin import AnalyticsAdminServiceClient
from google.analytics.data import BetaAnalyticsDataClient
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import httpx
from typing import Dict, List, Optional

class GoogleAnalyticsService:
    """خدمة متكاملة لجلب بيانات Google Analytics و Search Console"""
    
    def __init__(self):
        self.scopes = [
            'https://www.googleapis.com/auth/analytics.readonly',
            'https://www.googleapis.com/auth/analytics.manage.users',
            'https://www.googleapis.com/auth/webmasters.readonly',
            'https://www.googleapis.com/auth/userinfo.email'
        ]
    
    def get_oauth_url(self, redirect_uri: str, state: str = None) -> str:
        """إنشاء رابط OAuth لربط Google Analytics"""
        params = {
            'client_id': os.getenv('GOOGLE_CLIENT_ID'),
            'redirect_uri': redirect_uri,
            'scope': ' '.join(self.scopes),
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'consent',
            'state': state or ''
        }
        
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"https://accounts.google.com/o/oauth2/auth?{query_string}"
    
    async def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Dict:
        """تبديل authorization code بـ access token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'client_id': os.getenv('GOOGLE_CLIENT_ID'),
                    'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
                    'code': code,
                    'grant_type': 'authorization_code',
                    'redirect_uri': redirect_uri
                }
            )
            return response.json()
    
    def create_credentials(self, token_data: Dict) -> Credentials:
        """إنشاء credentials من token data"""
        return Credentials(
            token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            token_uri='https://oauth2.googleapis.com/token',
            client_id=os.getenv('GOOGLE_CLIENT_ID'),
            client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
            scopes=self.scopes
        )
    
    async def get_analytics_accounts(self, credentials: Credentials) -> List[Dict]:
        """جلب حسابات Google Analytics المتاحة للمستخدم"""
        try:
            client = AnalyticsAdminServiceClient(credentials=credentials)
            accounts = []
            
            for account in client.list_accounts():
                account_data = {
                    'id': account.name.split('/')[-1],
                    'name': account.display_name,
                    'properties': []
                }
                
                # جلب Properties لكل حساب
                try:
                    for prop in client.list_properties(parent=account.name):
                        property_data = {
                            'id': prop.name.split('/')[-1],
                            'name': prop.display_name,
                            'website_url': getattr(prop, 'website_url', ''),
                            'time_zone': prop.time_zone,
                            'currency_code': prop.currency_code
                        }
                        account_data['properties'].append(property_data)
                except Exception as e:
                    print(f"Error fetching properties for {account.display_name}: {e}")
                
                accounts.append(account_data)
            
            return accounts
        except Exception as e:
            print(f"Error fetching Analytics accounts: {e}")
            return []
    
    async def get_search_console_sites(self, credentials: Credentials) -> List[Dict]:
        """جلب مواقع Google Search Console"""
        try:
            service = build('searchconsole', 'v1', credentials=credentials)
            sites_list = service.sites().list().execute()
            
            sites = []
            for site in sites_list.get('siteEntry', []):
                site_data = {
                    'site_url': site['siteUrl'],
                    'permission_level': site['permissionLevel']
                }
                sites.append(site_data)
            
            return sites
        except Exception as e:
            print(f"Error fetching Search Console sites: {e}")
            return []
    
    async def get_website_performance(self, credentials: Credentials, property_id: str, days: int = 30) -> Dict:
        """جلب أداء الموقع من Analytics"""
        try:
            client = BetaAnalyticsDataClient(credentials=credentials)
            
            request = {
                "property": f"properties/{property_id}",
                "date_ranges": [{"start_date": f"{days}daysAgo", "end_date": "today"}],
                "metrics": [
                    {"name": "sessions"},
                    {"name": "users"},
                    {"name": "pageviews"},
                    {"name": "bounceRate"},
                    {"name": "sessionDuration"}
                ],
                "dimensions": [{"name": "date"}]
            }
            
            response = client.run_report(request=request)
            
            # معالجة البيانات
            data = {
                'total_sessions': 0,
                'total_users': 0,
                'total_pageviews': 0,
                'avg_bounce_rate': 0,
                'avg_session_duration': 0,
                'daily_data': []
            }
            
            for row in response.rows:
                date = row.dimension_values[0].value
                metrics = row.metric_values
                
                sessions = int(metrics[0].value)
                users = int(metrics[1].value)
                pageviews = int(metrics[2].value)
                bounce_rate = float(metrics[3].value)
                session_duration = float(metrics[4].value)
                
                data['total_sessions'] += sessions
                data['total_users'] += users
                data['total_pageviews'] += pageviews
                
                data['daily_data'].append({
                    'date': date,
                    'sessions': sessions,
                    'users': users,
                    'pageviews': pageviews,
                    'bounce_rate': bounce_rate,
                    'session_duration': session_duration
                })
            
            # حساب المتوسطات
            if len(data['daily_data']) > 0:
                data['avg_bounce_rate'] = sum(d['bounce_rate'] for d in data['daily_data']) / len(data['daily_data'])
                data['avg_session_duration'] = sum(d['session_duration'] for d in data['daily_data']) / len(data['daily_data'])
            
            return data
            
        except Exception as e:
            print(f"Error fetching website performance: {e}")
            return {}
    
    async def get_top_pages(self, credentials: Credentials, property_id: str, days: int = 30) -> List[Dict]:
        """جلب أفضل الصفحات أداءً"""
        try:
            client = BetaAnalyticsDataClient(credentials=credentials)
            
            request = {
                "property": f"properties/{property_id}",
                "date_ranges": [{"start_date": f"{days}daysAgo", "end_date": "today"}],
                "metrics": [
                    {"name": "sessions"},
                    {"name": "pageviews"},
                    {"name": "users"}
                ],
                "dimensions": [{"name": "pagePath"}, {"name": "pageTitle"}],
                "order_bys": [{"metric": {"metric_name": "sessions"}, "desc": True}],
                "limit": 20
            }
            
            response = client.run_report(request=request)
            
            pages = []
            for row in response.rows:
                page_path = row.dimension_values[0].value
                page_title = row.dimension_values[1].value
                sessions = int(row.metric_values[0].value)
                pageviews = int(row.metric_values[1].value)
                users = int(row.metric_values[2].value)
                
                pages.append({
                    'path': page_path,
                    'title': page_title,
                    'sessions': sessions,
                    'pageviews': pageviews,
                    'users': users
                })
            
            return pages
            
        except Exception as e:
            print(f"Error fetching top pages: {e}")
            return []
    
    async def get_search_console_performance(self, credentials: Credentials, site_url: str, days: int = 30) -> Dict:
        """جلب أداء Search Console"""
        try:
            service = build('searchconsole', 'v1', credentials=credentials)
            
            # تحديد تاريخ البداية والنهاية
            from datetime import datetime, timedelta
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            request_body = {
                'startDate': start_date.strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d'),
                'dimensions': ['query'],
                'rowLimit': 100
            }
            
            response = service.searchanalytics().query(
                siteUrl=site_url,
                body=request_body
            ).execute()
            
            # معالجة البيانات
            queries = []
            total_clicks = 0
            total_impressions = 0
            
            for row in response.get('rows', []):
                query = row['keys'][0]
                clicks = row['clicks']
                impressions = row['impressions']
                ctr = row['ctr']
                position = row['position']
                
                total_clicks += clicks
                total_impressions += impressions
                
                queries.append({
                    'query': query,
                    'clicks': clicks,
                    'impressions': impressions,
                    'ctr': round(ctr * 100, 2),
                    'position': round(position, 1)
                })
            
            return {
                'total_clicks': total_clicks,
                'total_impressions': total_impressions,
                'avg_ctr': round((total_clicks / total_impressions) * 100, 2) if total_impressions > 0 else 0,
                'queries': queries
            }
            
        except Exception as e:
            print(f"Error fetching Search Console performance: {e}")
            return {}
    
    async def analyze_seo_opportunities(self, credentials: Credentials, property_id: str, site_url: str) -> Dict:
        """تحليل فرص تحسين SEO"""
        try:
            # جلب البيانات من Analytics و Search Console
            performance_data = await self.get_website_performance(credentials, property_id)
            top_pages = await self.get_top_pages(credentials, property_id)
            search_data = await self.get_search_console_performance(credentials, site_url)
            
            # تحليل الفرص
            opportunities = []
            
            # فرص تحسين CTR
            low_ctr_queries = [q for q in search_data.get('queries', []) if q['ctr'] < 2 and q['impressions'] > 100]
            if low_ctr_queries:
                opportunities.append({
                    'type': 'low_ctr',
                    'title': 'تحسين نسبة النقر (CTR)',
                    'description': f'لديك {len(low_ctr_queries)} كلمة مفتاحية بنسبة نقر منخفضة',
                    'impact': 'high',
                    'queries': low_ctr_queries[:5]
                })
            
            # فرص تحسين الترتيب
            low_position_queries = [q for q in search_data.get('queries', []) if q['position'] > 10 and q['impressions'] > 50]
            if low_position_queries:
                opportunities.append({
                    'type': 'low_position',
                    'title': 'تحسين ترتيب الكلمات المفتاحية',
                    'description': f'لديك {len(low_position_queries)} كلمة مفتاحية في ترتيب منخفض',
                    'impact': 'high',
                    'queries': low_position_queries[:5]
                })
            
            # صفحات بمعدل ارتداد عالي
            if performance_data.get('avg_bounce_rate', 0) > 70:
                opportunities.append({
                    'type': 'high_bounce_rate',
                    'title': 'تحسين تجربة المستخدم',
                    'description': f'معدل الارتداد {performance_data["avg_bounce_rate"]:.1f}% مرتفع',
                    'impact': 'medium'
                })
            
            return {
                'opportunities': opportunities,
                'total_opportunities': len(opportunities),
                'potential_improvement': self.calculate_potential_improvement(opportunities)
            }
            
        except Exception as e:
            print(f"Error analyzing SEO opportunities: {e}")
            return {}
    
    def calculate_potential_improvement(self, opportunities: List[Dict]) -> Dict:
        """حساب التحسن المحتمل"""
        total_score = 0
        for opp in opportunities:
            if opp['impact'] == 'high':
                total_score += 30
            elif opp['impact'] == 'medium':
                total_score += 20
            else:
                total_score += 10
        
        return {
            'score': min(total_score, 100),
            'level': 'high' if total_score > 50 else 'medium' if total_score > 20 else 'low'
        }