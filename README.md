# ✦ Sifter — نظام RAG للـ CVs (PostgreSQL + pgvector)

نظام بيدور على أنسب المرشحين من الـ CVs، ، وبيضيف أي CV جديد أوتوماتيك (من مجلد أو من Google Drive).

## 1) كيف بيشتغل

```
CV (PDF) ─► فحص ATS ─┬─ ملتزم ──────► metadata ─► chunks ─► embeddings ─► Postgres (ready)
                     └─ مش ملتزم ───► Human review (موافقة/رفض) ─► نفس الخطوات بعد الموافقة

سؤال ─► embedding ─► أقرب K chunk (SQL) ─► نعرف من أي CVs ─► أفضل N مرشح
      ─► نبعت الـ CV الكامل لكل مرشح للـ LLM ─► الجواب (+ Trace بجدول rag_traces)
```

**ليش نبعت الـ CV كامل مش بس الـ chunks؟** الـ chunks بتستخدم للتصفية (مين أقرب للسؤال). بعدين الـ LLM بياخد الـ CV كامل للمرشحين المختارين، فبيقدر يحسب سنوات الخبرة ويقارن المهارات بدون ما يفوته شي.

## 2) الملفات


| الملف           | شو بيعمل                                                                                                                                                                |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `schema.sql`         | تصميم الداتابيز:`documents` و`document_chunks` و`rag_traces`                                                                                                   |
| `setup_db.py`        | بينفذ`schema.sql` (بدل pgAdmin)                                                                                                                                        |
| `config.py` / `.env` | كل الإعدادات (الداتابيز، التوكن، K و N، Drive)                                                                                                   |
| `db.py`              | الاتصال بالداتابيز (`get_conn()`)                                                                                                                             |
| `cv_parser.py`       | قراءة PDF، تقسيم الأقسام، فحص**ATS**، استخراج **metadata**، إخفاء الإيميل والهاتف                                            |
| `chunking.py`        | طرق التقطيع:`section` (الافتراضي) و`recursive` و`fixed`                                                                                                   |
| `embedding.py`       | النص ← vector (384 رقم)                                                                                                                                                |
| `ingest.py`          | الخط الكامل للإدخال + الموافقة/الرفض (HITL)                                                                                                      |
| `search.py`          | البحث بـ SQL (`<=>`) واختيار المرشحين وجلب الـ CV الكامل                                                                                    |
| `prompts.py`         | الـ System Prompt المستخدم بالنظام (`SYSTEM_PROMPT`)، ونسخة بسيطة (`BASELINE_PROMPT`) بنستخدمها فقط بالتقييم للمقارنة |
| `llm.py`             | الاتصال بـ Google Gemini (مع إعادة المحاولة عند ضغط السيرفر)                                                                              |
| `rag.py`             | `ask()` بتجمع كل شي وبتسجل الـ Trace                                                                                                                         |
| `drive_sync.py`      | مراقبة مجلد Google Drive                                                                                                                                             |
| `app.py`             | الواجهة (Streamlit)                                                                                                                                                     |
| `eval/`              | الـ 16 حالة اختبار + سكربت التقييم                                                                                                                    |
| `data/`              | الـ 15 CV                                                                                                                                                                   |

## 3) المتطلبات

- Python 3.10 أو أحدث
- Docker Desktop (للداتابيز بس)
- **مساحة فاضية على القرص 6 GB على الأقل** (مكتبة torch والـ embedding model بياخدوا مساحة)
- مفتاح Gemini API (من Google AI Studio)

## 4) التشغيل خطوة خطوة (VS Code)

كل الأوامر بتنكتب بـ Terminal جوا VS Code (`Ctrl + ~`) ومن **مجلد المشروع**.

**1) افتح المجلد:** File ← Open Folder ← اختر `rag_cv_project`.

**2) أنشئ بيئة Python وفعّلها:**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

لو ويندوز منع التفعيل: `Set-ExecutionPolicy -Scope Process Bypass` ثم أعد الأمر. وبعدها اختر الـ interpreter: `Ctrl+Shift+P` ← `Python: Select Interpreter` ← اللي جواه `.venv`.

**3) ثبّت المكتبات:**

```powershell
pip install -r requirements.txt
```

**4) ملف الإعدادات:**

```powershell
copy .env.example .env
```

افتح `.env` وحط التوكن بدل `hf_ضع_التوكن_هنا`. الباقي جاهز ومطابق لأمر Docker اللي شغلناه.

**5) شغّل الداتابيز:** افتح Docker Desktop، وبعدين:

```powershell
docker start rag-postgres
docker ps
```

لازم تشوف `rag-postgres` و`Up`. (إذا ما كانت موجودة أصلاً، شغّل أمر `docker run` اللي عندك من قبل.)

**6) أنشئ الجداول:**

```powershell
python setup_db.py --reset
```

> ⚠️ `--reset` بيحذف الجداول القديمة وبينشئها من جديد. لازم تعمله **مرة وحدة** لأنه تصميم جدول `documents` تغيّر (أعمدة جديدة)، وبيمسح البيانات التجريبية القديمة. المرات الجاية: `python setup_db.py` بدون `--reset`.

**7) أدخل الـ CVs:**

```powershell
python ingest.py
```

أول مرة بينزل موديل الـ embedding (حوالي 90 MB)، فاستنى. النتيجة المتوقعة: 15 CV `added` وكل واحد 7 chunks. أي CV مش ملتزم بـ ATS بيطلع `sent to human review`.

**8) شغّل الواجهة:**

```powershell
streamlit run app.py
```

بيفتح `http://localhost:8501`. جرّب: *"Who has Python skills and at least 3 years of experience?"*

## 5) شو لازم تعدل عندك؟


| شو                                                            | الحل                                                                                                                                                                               |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| الجداول القديمة (`documents` و`document_chunks`) | `python setup_db.py --reset` (مرة وحدة)                                                                                                                                         |
| اسم الداتابيز بـ`main.ipynb` (`pdf_db`)           | ما بنحتاج الـ notebook للتشغيل. إذا استخدمته، غيّر الاسم لـ`ragdb`                                                                            |
| مفتاح LlamaCloud                                           | مش مستخدم بالمشروع (pymupdf كفاية لأنه قالب ATS ثابت). إذا استخدمته بالـ notebook، حطه بمتغير بيئة، ومش بالكود |
| المنفذ أو كلمة السر                             | عدّل`.env` ليطابق أمر `docker run`                                                                                                                                        |
| عدد الـ CVs المبعوتة للموديل (N)           | من تبويب Search ثم Filters (**CVs to compare**)، أو `TOP_N` بـ `.env`. وعدد الـ chunks (K) بيتحسب تلقائياً (3 أضعاف N على الأقل)       |
| طريقة الـ chunking                                      | `CHUNK_STRATEGY=section` أو `recursive` أو `fixed` بـ `.env` ثم `python setup_db.py --reset` و`python ingest.py`                                                              |

## 6) شغل الـ SQL بـ VS Code (بدون pgAdmin)

**الطريقة 1: من الـ Terminal مباشرة:**

```powershell
docker exec -it rag-postgres psql -U raguser -d ragdb
```

وجوا `psql`:

```sql
\dt
SELECT id, candidate_name, department, years_experience, status FROM documents;
SELECT section, COUNT(*) FROM document_chunks GROUP BY section;
SELECT d.candidate_name, c.section, LEFT(c.content, 60) FROM document_chunks c JOIN documents d ON d.id = c.document_id LIMIT 5;
\q
```

**الطريقة 2: بواجهة:** ثبّت إضافة **SQLTools** و**SQLTools PostgreSQL/Cockroach Driver**، وأضف اتصال: host `localhost` و port `5433` و database `ragdb` و user `raguser` و password `ragpass`. بعدين افتح أي ملف `.sql` ونفّذ الاستعلام المحدد.

## 7) فحص ATS والمراجعة البشرية (HITL)

**القالب المطلوب:** PDF نصي (مش صورة ممسوحة) فيه هالعناوين، كل واحد بسطر لحاله:

```
PROFESSIONAL SUMMARY / CORE SKILLS / EXPERIENCE / EDUCATION / SELECTED PROJECTS / CERTIFICATIONS
```

وفيه إيميل. ملف الـ CV الـ16 اللي كان بمجلد `data` (له عناوين مختلفة) هو مثال على CV بيروح للمراجعة.

**اللي بيصير:**

- ملتزم ← `status = ready` ← بيدخل البحث فوراً.
- مش ملتزم ← `status = pending_review` ← ما بيدخل البحث. بتروح لتبويب **Human review**، بتشوف سبب الرفض، وبتعدل الاسم والقسم والخبرة، وبعدين **Approve** (بيصير له chunks وembeddings) أو **Reject**.

**الـ metadata المستخرجة:** الاسم، المسمى، القسم، سنوات الخبرة، المهارات، اسم الملف، و`drive_file_id`.

**قاعدة تسمية الملفات** (لاستخراج القسم): `NN_Department_First_Last.pdf` مثل `01_Data_and_AI_Omar_Khalil.pdf`. إذا الاسم ما التزم، القسم بيتخمّن من المسمى الوظيفي.

## 8) ربط Google Drive

الفكرة: برنامج صغير (`drive_sync.py`) بيفحص المجلد كل دقيقة، وأي PDF جديد بيحمله ويدخله.

1. افتح console.cloud.google.com وأنشئ Project.
2. **APIs & Services ← Library** وفعّل **Google Drive API**.
3. **IAM & Admin ← Service Accounts ← Create**.
4. افتح الـ Service Account ← **Keys ← Add key ← JSON**. بينزل ملف، سمّيه `credentials.json` وحطه بمجلد المشروع.
5. انسخ إيميل الـ Service Account (شكله `xxx@yyy.iam.gserviceaccount.com`).
6. بمجلد الـ Drive: **Share** وأضف هالإيميل بصلاحية **Viewer**.
7. رقم المجلد هو الجزء اللي بعد `/folders/` بالرابط. حطه بـ `.env`: `DRIVE_FOLDER_ID=...`
8. جرّب: `python drive_sync.py --once`
9. للتشغيل الدائم، افتح Terminal ثاني: `python drive_sync.py` (خليه شغال).

أي CV بتضيفه للمجلد بيظهر بالنظام خلال `DRIVE_POLL_SECONDS` (60 ثانية). الملفات لازم تكون PDF، ولازم أسماؤها مختلفة. وزر **Sync Google Drive** بتبويب CVs (بيظهر فقط لما يكون الـ Drive مضبوط) بيعمل نفس الشي بالضغط.

## 9) التقييم (Session 25)

```powershell
python eval/run_eval.py --prompt baseline
python eval/run_eval.py --prompt best
python eval/run_eval.py --compare
```

- **16 حالة** بـ `eval/test_cases.json`: 4 Normal و4 Edge و4 Failure و4 Risky، لكل حالة Ground Truth أو سلوك متوقع.
- **Ground Truth** للحالات العادية انحسب من نص الـ 15 CV، لكن **تحقق منه بنفسك** قبل التسليم (مثلاً Lina Hassan عندها "Python Basics" فقط، وحطيناها حالة حدّية).
- **Tracing:** كل تشغيل بيتسجل بجدول `rag_traces` (الـ chunks، الـ CVs المبعوتة، الجواب، الزمن، الـ tokens). والتقرير بيحدد مكان المشكلة: **Retrieval** أو **Generation**.
- **المقاييس:** Retrieval recall وprecision، Completeness، Safety (تسريب إيميل أو هاتف)، Cost، Latency، وحكم الـ LLM Judge.
- **A/B:** `baseline` (prompt بسيط) مقابل `best` (المستخدم بالنظام) بنفس الأسئلة، والتقارير بـ `eval/report_baseline.md` و`eval/report_best.md`. لو ما بدك المقارنة، تجاهل `BASELINE_PROMPT`، ما بيأثر على النظام.
- لحساب التكلفة بالدولار، حط أسعار الموديل بـ `.env` (`PRICE_IN_PER_1M` و`PRICE_OUT_PER_1M`). بدونها بيظهر عدد الـ tokens فقط.
