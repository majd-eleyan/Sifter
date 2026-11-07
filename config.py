"""كل الإعدادات بمكان واحد. القيم بتيجي من ملف .env (وإذا مش موجودة بنستخدم الافتراضي)."""
import os
from dotenv import load_dotenv

load_dotenv()

# ---------- الداتابيز (نفس أمر docker اللي شغلناه) ----------
DB = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5433")),
    dbname=os.getenv("DB_NAME", "ragdb"),
    user=os.getenv("DB_USER", "raguser"),
    password=os.getenv("DB_PASSWORD", "ragpass"),
)

# رابط اتصال كامل (Neon / Supabase). لو موجود بيُستخدم بدل الإعدادات اللي فوق. لازم يُستخدم عند النشر.
DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_SSLMODE = os.getenv("DB_SSLMODE", "prefer")   # الداتابيز المحلية (Docker) بدون SSL، والسحابية بتطلب SSL ورابطها فيه sslmode=require

# ---------- الـ Embedding ----------
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = 384 

# ---------- الـ LLM: Google Gemini  ----------
LLM_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
LLM_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")   # غيّره لو Google AI Studio بيعرض موديل أحدث
PRICE_IN_PER_1M = float(os.getenv("PRICE_IN_PER_1M", "0"))    # سعر مليون token دخل (بالدولار)
PRICE_OUT_PER_1M = float(os.getenv("PRICE_OUT_PER_1M", "0"))  # سعر مليون token خرج

# ---------- البحث ----------
TOP_K = int(os.getenv("TOP_K", "10"))   # كم chunk نسترجع
TOP_N = int(os.getenv("TOP_N", "5"))    # كم CV كامل نبعت للـ LLM
CHUNK_STRATEGY = os.getenv("CHUNK_STRATEGY", "section")  # section | recursive | fixed

# ---------- Google Drive ----------
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID", "")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")   # محتوى ملف credentials.json كنص (للنشر، بدل الملف)
DRIVE_POLL_SECONDS = int(os.getenv("DRIVE_POLL_SECONDS", "60"))

DATA_DIR = os.getenv("DATA_DIR", "data")

# ---------- حماية الواجهة عند النشر (اختياري): لو انحطت كلمة سر، ما بتفتح الواجهة إلا فيها ----------
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
