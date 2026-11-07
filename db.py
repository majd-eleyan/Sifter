"""الاتصال بالداتابيز. أي ملف بدو داتابيز بيستدعي get_conn()."""
import psycopg
from config import DATABASE_URL, DB, DB_SSLMODE


def get_conn():
    # استخدمه هيك:  with get_conn() as conn:  ...
    # بآخر الـ with بيعمل commit تلقائي (أو rollback لو صار خطأ) وبيسكر الاتصال
    # prepare_threshold=None: بيعطّل الـ prepared statements، لأن الـ poolers عند Neon وSupabase ما بتدعمها
    if DATABASE_URL:
        return psycopg.connect(DATABASE_URL, client_encoding="utf8", prepare_threshold=None)
    return psycopg.connect(**DB, sslmode=DB_SSLMODE, client_encoding="utf8", prepare_threshold=None)
