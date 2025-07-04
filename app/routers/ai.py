from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from openai import OpenAI
import os
from dotenv import load_dotenv
from app.routers.auth import get_current_user

load_dotenv()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

router = APIRouter()

class PromptRequest(BaseModel):
    prompt: str

@router.post("/generate")
async def generate_text(request: PromptRequest, user=Depends(get_current_user)):
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "أنت مساعد ذكي متخصص في تحسين SEO للمنتجات."},
                {"role": "user", "content": request.prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        generated_text = response.choices[0].message.content.strip()
        return {"text": generated_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في توليد النص: {str(e)}")