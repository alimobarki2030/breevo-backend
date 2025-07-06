# app/services/ai_service.py
import os
import re
import json
from typing import Dict, List, Any, Optional
from openai import AsyncOpenAI
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AIService:
    """خدمة الذكاء الاصطناعي لتحليل وتحسين SEO"""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OpenAI API key not configured")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=api_key)
    
    def analyze_product_seo(self, product) -> Dict[str, Any]:
        """تحليل SEO للمنتج بدون AI (تحليل أساسي)"""
        score = 0
        issues = []
        suggestions = []
        
        # تحليل العنوان
        title_length = len(product.name) if product.name else 0
        if title_length < 30:
            issues.append({
                "type": "title_too_short",
                "severity": "medium",
                "message": "عنوان المنتج قصير جداً (أقل من 30 حرف)"
            })
            suggestions.append({
                "type": "title",
                "message": "أضف المزيد من التفاصيل الوصفية للعنوان"
            })
        elif title_length > 60:
            issues.append({
                "type": "title_too_long",
                "severity": "low",
                "message": "عنوان المنتج طويل جداً (أكثر من 60 حرف)"
            })
        else:
            score += 20
        
        # تحليل الوصف
        desc_length = len(product.description) if product.description else 0
        if desc_length < 50:
            issues.append({
                "type": "description_too_short",
                "severity": "high",
                "message": "وصف المنتج قصير جداً أو غير موجود"
            })
            suggestions.append({
                "type": "description",
                "message": "أضف وصف مفصل يتضمن مميزات المنتج والكلمات المفتاحية"
            })
        elif desc_length > 160:
            score += 20
        else:
            score += 10
        
        # تحليل SEO Title
        if not product.seo_title:
            issues.append({
                "type": "missing_seo_title",
                "severity": "high",
                "message": "عنوان SEO غير موجود"
            })
            suggestions.append({
                "type": "seo_title",
                "message": "أضف عنوان SEO محسّن يحتوي على الكلمات المفتاحية"
            })
        else:
            seo_title_length = len(product.seo_title)
            if 50 <= seo_title_length <= 60:
                score += 20
            else:
                issues.append({
                    "type": "seo_title_length",
                    "severity": "medium",
                    "message": f"طول عنوان SEO غير مثالي ({seo_title_length} حرف)"
                })
        
        # تحليل SEO Description
        if not product.seo_description:
            issues.append({
                "type": "missing_seo_description",
                "severity": "high",
                "message": "وصف SEO غير موجود"
            })
            suggestions.append({
                "type": "seo_description",
                "message": "أضف وصف SEO يلخص المنتج في 150-160 حرف"
            })
        else:
            seo_desc_length = len(product.seo_description)
            if 150 <= seo_desc_length <= 160:
                score += 20
            else:
                issues.append({
                    "type": "seo_description_length",
                    "severity": "medium",
                    "message": f"طول وصف SEO غير مثالي ({seo_desc_length} حرف)"
                })
        
        # تحليل الصور
        if not product.images or len(product.images) == 0:
            issues.append({
                "type": "no_images",
                "severity": "high",
                "message": "لا توجد صور للمنتج"
            })
            suggestions.append({
                "type": "images",
                "message": "أضف صور عالية الجودة للمنتج"
            })
        elif len(product.images) >= 3:
            score += 10
        else:
            score += 5
            suggestions.append({
                "type": "images",
                "message": "أضف المزيد من الصور (3 على الأقل)"
            })
        
        # تحليل الكلمات المفتاحية في المحتوى
        content = f"{product.name} {product.description or ''}"
        
        # البحث عن كلمات مفتاحية شائعة
        common_keywords = self._extract_keywords(content)
        if len(common_keywords) < 3:
            suggestions.append({
                "type": "keywords",
                "message": "استخدم المزيد من الكلمات المفتاحية ذات الصلة"
            })
        else:
            score += 10
        
        return {
            "score": min(score, 100),
            "issues": issues,
            "suggestions": suggestions,
            "keywords_found": common_keywords
        }
    
    async def optimize_product_seo(self, product) -> Dict[str, str]:
        """تحسين SEO للمنتج باستخدام AI"""
        if not self.client:
            # إذا لم يكن OpenAI متاحاً، نستخدم تحسين أساسي
            return self._basic_seo_optimization(product)
        
        try:
            # إعداد البرومبت
            prompt = f"""
            أنت خبير SEO للتجارة الإلكترونية. قم بتحسين SEO لهذا المنتج:
            
            اسم المنتج: {product.name}
            الوصف الحالي: {product.description or 'لا يوجد وصف'}
            التصنيف: {product.category_name or 'غير محدد'}
            السعر: {product.price_amount} {product.price_currency}
            
            المطلوب:
            1. عنوان SEO محسّن (50-60 حرف) - يجب أن يحتوي على الكلمات المفتاحية
            2. وصف SEO (150-160 حرف) - ملخص جذاب يشجع على النقر
            3. قائمة بـ 5 كلمات مفتاحية مقترحة
            
            أجب بصيغة JSON فقط:
            {{
                "seo_title": "العنوان المحسن",
                "seo_description": "الوصف المحسن",
                "keywords": ["كلمة1", "كلمة2", "كلمة3", "كلمة4", "كلمة5"]
            }}
            """
            
            response = await self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "أنت خبير SEO متخصص في التجارة الإلكترونية العربية. تقدم تحسينات دقيقة ومؤثرة."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # التحقق من صحة النتائج
            if not all(key in result for key in ["seo_title", "seo_description", "keywords"]):
                raise ValueError("Invalid AI response format")
            
            return result
            
        except Exception as e:
            logger.error(f"Error using OpenAI for SEO optimization: {str(e)}")
            return self._basic_seo_optimization(product)
    
    async def generate_product_description(self, product_data: Dict[str, Any]) -> str:
        """توليد وصف احترافي للمنتج"""
        if not self.client:
            return self._generate_basic_description(product_data)
        
        try:
            prompt = f"""
            اكتب وصف احترافي ومقنع لهذا المنتج:
            
            الاسم: {product_data.get('name')}
            التصنيف: {product_data.get('category', 'غير محدد')}
            المميزات: {product_data.get('features', 'غير محددة')}
            
            الوصف يجب أن يكون:
            - 100-150 كلمة
            - يركز على الفوائد للعميل
            - يحتوي على كلمات مفتاحية طبيعية
            - مقنع ويشجع على الشراء
            - مكتوب بلغة عربية احترافية
            """
            
            response = await self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "أنت كاتب محتوى تسويقي محترف متخصص في التجارة الإلكترونية."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.8,
                max_tokens=400
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating description: {str(e)}")
            return self._generate_basic_description(product_data)
    
    async def analyze_competitor_keywords(self, category: str, region: str = "SA") -> Dict[str, Any]:
        """تحليل كلمات المنافسين (يتطلب DataForSEO)"""
        # هذه الدالة ستستخدم DataForSEO API
        # مؤقتاً نرجع بيانات تجريبية
        return {
            "top_keywords": [
                {"keyword": f"{category} اون لاين", "volume": 5000, "difficulty": 45},
                {"keyword": f"افضل {category}", "volume": 3000, "difficulty": 60},
                {"keyword": f"{category} رخيص", "volume": 2000, "difficulty": 35},
            ],
            "competitor_domains": [
                "noon.com",
                "amazon.sa",
                "jarir.com"
            ],
            "recommendations": [
                f"استهدف كلمة '{category} السعودية' لحجم بحث أقل منافسة",
                "أضف محتوى عن الشحن المجاني والضمان",
                "استخدم كلمات طويلة الذيل للمنافسة"
            ]
        }
    
    def _extract_keywords(self, text: str) -> List[str]:
        """استخراج الكلمات المفتاحية من النص"""
        if not text:
            return []
        
        # إزالة الأحرف الخاصة
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # تقسيم إلى كلمات
        words = text.split()
        
        # إزالة الكلمات القصيرة جداً
        keywords = [word for word in words if len(word) > 2]
        
        # حساب التكرار
        word_freq = {}
        for word in keywords:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # ترتيب حسب التكرار
        sorted_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        
        # إرجاع أكثر 10 كلمات تكراراً
        return [word for word, freq in sorted_keywords[:10] if freq > 1]
    
    def _basic_seo_optimization(self, product) -> Dict[str, str]:
        """تحسين SEO أساسي بدون AI"""
        # عنوان SEO محسّن
        seo_title = product.name
        if product.category_name:
            seo_title = f"{product.name} - {product.category_name}"
        
        # اقتطاع للطول المناسب
        if len(seo_title) > 60:
            seo_title = seo_title[:57] + "..."
        
        # وصف SEO
        seo_description = product.description or product.name
        if len(seo_description) > 160:
            seo_description = seo_description[:157] + "..."
        elif len(seo_description) < 100:
            seo_description = f"{seo_description} - متوفر الآن بأفضل سعر مع شحن سريع"
        
        # كلمات مفتاحية مقترحة
        keywords = self._extract_keywords(f"{product.name} {product.description or ''}")[:5]
        
        return {
            "seo_title": seo_title,
            "seo_description": seo_description,
            "keywords": keywords
        }
    
    def _generate_basic_description(self, product_data: Dict[str, Any]) -> str:
        """توليد وصف أساسي بدون AI"""
        name = product_data.get('name', 'المنتج')
        category = product_data.get('category', '')
        features = product_data.get('features', '')
        
        description = f"يقدم لكم {name}"
        
        if category:
            description += f" من فئة {category}"
        
        description += " بجودة عالية وسعر منافس."
        
        if features:
            description += f" يتميز بـ {features}."
        
        description += " احصل عليه الآن مع شحن سريع وضمان الجودة."
        
        return description
    
    async def batch_analyze_products(self, products: List[Any]) -> List[Dict[str, Any]]:
        """تحليل مجموعة من المنتجات"""
        results = []
        for product in products:
            try:
                analysis = self.analyze_product_seo(product)
                results.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "analysis": analysis
                })
            except Exception as e:
                logger.error(f"Error analyzing product {product.id}: {str(e)}")
                results.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "error": str(e)
                })
        
        return results
    
    def calculate_content_quality_score(self, content: str) -> Dict[str, Any]:
        """حساب جودة المحتوى"""
        if not content:
            return {"score": 0, "issues": ["لا يوجد محتوى"]}
        
        score = 0
        issues = []
        
        # طول المحتوى
        word_count = len(content.split())
        if word_count < 50:
            issues.append("المحتوى قصير جداً")
        elif word_count > 300:
            score += 20
        else:
            score += 10
        
        # تنوع الكلمات
        unique_words = len(set(content.split()))
        diversity_ratio = unique_words / word_count if word_count > 0 else 0
        
        if diversity_ratio > 0.7:
            score += 20
        elif diversity_ratio > 0.5:
            score += 10
        else:
            issues.append("المحتوى يحتاج لتنوع أكثر في الكلمات")
        
        # وجود أرقام (مفيد للمواصفات)
        if re.search(r'\d+', content):
            score += 10
        
        # وجود علامات ترقيم
        punctuation_count = len(re.findall(r'[.,!?؛:]', content))
        if punctuation_count > 3:
            score += 10
        
        # الفقرات
        paragraphs = content.split('\n\n')
        if len(paragraphs) > 1:
            score += 10
        
        # الكلمات المفتاحية الشائعة في التجارة الإلكترونية
        ecommerce_keywords = ['جودة', 'ضمان', 'شحن', 'سريع', 'أصلي', 'مميزات', 'خصم', 'عرض']
        found_keywords = sum(1 for keyword in ecommerce_keywords if keyword in content)
        score += min(found_keywords * 5, 20)
        
        return {
            "score": min(score, 100),
            "issues": issues,
            "word_count": word_count,
            "diversity_ratio": round(diversity_ratio, 2)
        }