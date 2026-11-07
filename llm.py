"""الاتصال بالـ LLM: Google Gemini عبر الـ endpoint المتوافق مع مكتبة OpenAI (نفس الكود تقريباً، تغيّر العنوان والمفتاح بس)."""
import time

import openai
from openai import OpenAI

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from prompts import get_prompt

_client = None

# أخطاء مؤقتة بنعيد المحاولة معها: 429 (كثرة طلبات بالدقيقة) و500/503 (ضغط على السيرفر)
RETRYABLE = (openai.RateLimitError, openai.InternalServerError)
MAX_TRIES = 4

EMPTY_ANSWER = ("⚠️ The model returned an empty answer (it may have been blocked by a safety filter). "
                "Please rephrase the question.")


def get_client():
    global _client
    if _client is None:
        if not LLM_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is missing. Add it to your .env file.")
        _client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
    return _client


def build_user_prompt(question, cvs):
    blocks = []
    for i, cv in enumerate(cvs, start=1):
        years = cv["years_experience"] if cv["years_experience"] is not None else "unknown"
        blocks.append(
            f"=== CV {i} | file: {cv['filename']} ===\n"
            f"Candidate: {cv['candidate_name']} | Department: {cv['department']} | "
            f"Years of experience (from summary): {years}\n\n{cv['text']}"
        )
    return "CVs:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion:\n{question}"


def chat(system_prompt, user_prompt):
    """نداء عام للـ LLM. بيرجع (النص، عدد الـ tokens). بيعيد المحاولة لو كان الخطأ مؤقت."""
    for attempt in range(1, MAX_TRIES + 1):
        try:
            completion = get_client().chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                temperature=0,        # 0 = جواب ثابت وأقل عشوائية
            )
            break
        except RETRYABLE:
            if attempt == MAX_TRIES:
                raise
            time.sleep(10 * attempt)  # نستنى 10 ثم 20 ثم 30 ثانية وبنحاول من جديد

    usage = completion.usage
    tokens = {"prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
              "completion_tokens": getattr(usage, "completion_tokens", 0) or 0}
    text = (completion.choices[0].message.content if completion.choices else "") or ""
    return text, tokens


def generate_answer(question, cvs, prompt_version="best"):
    text, tokens = chat(get_prompt(prompt_version), build_user_prompt(question, cvs))
    return (text if text.strip() else EMPTY_ANSWER), tokens
