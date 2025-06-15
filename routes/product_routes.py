from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

# مخطط المنتج الذي يتم إرساله من الواجهة
class Product(BaseModel):
    name: str
    keyword: Optional[str] = ""
    description: Optional[str] = ""
    seo_title: Optional[str] = ""
    seo_url: Optional[str] = ""
    meta_description: Optional[str] = ""
    imageAlt: Optional[str] = ""
    status: Optional[str] = "جديد"
    seoScore: Optional[int] = 0

@router.post("/product/")
def add_product(product: Product):
    print("✅ تم استلام منتج:", product.dict())
    return {"message": "تم الحفظ", "product": {"id": 1, **product.dict()}}
