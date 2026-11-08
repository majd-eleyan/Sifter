# ✦ Sifter

**AI-powered CV screening with Retrieval-Augmented Generation (RAG), PostgreSQL + pgvector, and Gemini.**

Ask a question or paste a job description, and Sifter shortlists the best-matching candidates from your CV pool, then reads their **full CVs** to give a grounded answer, with the source file for every claim.

> The 15 sample CVs in `data/` are **synthetic** (generated for training and demo purposes). They contain no real people.

<!-- Add a screenshot or GIF here, e.g.:  ![Sifter](docs/screenshot.png) -->
[![image.png](https://i.postimg.cc/HkfsP44Z/image.png)](https://postimg.cc/3kFTkGqm)

[![image.png](https://i.postimg.cc/X7qjjDsz/image.png)](https://postimg.cc/HVGD33Dw)
---

## Features

- **Two-stage retrieval.** Semantic search finds the top-K matching chunks, groups them by CV, and shortlists the top-N candidates. The **complete CVs** of those candidates are then sent to the LLM, so nothing important is lost to chunk boundaries.
- **ATS template check + human review.** CVs that follow the template are indexed automatically. Others are held in a review queue (approve / edit / reject) and stay invisible to search until approved.
- **Automatic metadata extraction.** Candidate name, job title, department, years of experience, and skills, used for SQL filters (for example: Cybersecurity, 5+ years).
- **Privacy by design.** Emails and phone numbers are redacted before chunking and before any text reaches the LLM. The system prompt also refuses to reveal contact details or to filter by protected traits (gender, age, religion, nationality).
- **Follow-up questions** about the same shortlisted candidates, without a new search.
- **Google Drive sync.** New PDFs dropped into a Drive folder are ingested automatically.
- **Tracing and evaluation.** Every question is logged (retrieved chunks, CVs sent, answer, latency, tokens). A 16-case evaluation suite (Normal / Edge / Failure / Risky) with ground truth, an LLM judge, and prompt A/B comparison is included.
- **Streamlit UI** in black and gold.

## How it works

```
CV (PDF) ─► ATS check ─┬─ passes ───► metadata ─► section chunks ─► embeddings ─► PostgreSQL (ready)
                       └─ fails ────► human review ─► approve ─► same steps

Question ─► embedding ─► top-K chunks (SQL, cosine distance) ─► group by CV ─► top-N candidates
         ─► full CVs (contacts redacted) ─► Gemini ─► answer + sources ─► trace saved
```

**Database design**

| Table | Purpose |
|---|---|
| `documents` | One row per CV: file name, candidate name, department, years of experience, skills, full text, ATS result, status (`ready` / `pending_review` / `rejected`), optional Drive file ID |
| `document_chunks` | CV sections with their `VECTOR(384)` embedding and JSONB metadata. Linked to `documents` with `ON DELETE CASCADE`; HNSW index for fast search |
| `rag_traces` | One row per question, used for tracing and evaluation |

## Tech stack

| Area | Technology |
|---|---|
| UI | Streamlit |
| Database | PostgreSQL + pgvector |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, runs locally) |
| LLM | Google Gemini through its OpenAI-compatible endpoint |
| PDF parsing | PyMuPDF |
| DB driver | psycopg 3 |
| Drive integration | Google Drive API (service account, read-only) |

## Project structure

```
Sifter/
├── app.py            Streamlit UI (Search, CVs, Review)
├── rag.py            ask(): retrieval → LLM → answer + trace
├── search.py         SQL vector search, candidate shortlist, full-CV fetch
├── ingest.py         PDF → ATS check → metadata → chunks → embeddings → DB, plus approve/reject
├── cv_parser.py      PDF reading, sections, ATS check, metadata, redaction
├── chunking.py       section / recursive / fixed chunking
├── embedding.py      text → vector
├── llm.py            Gemini client with retries
├── prompts.py        system prompt (+ a baseline prompt for A/B tests)
├── drive_sync.py     Google Drive watcher
├── db.py, config.py  connection and settings
├── schema.sql        database schema
├── setup_db.py       creates the tables
├── check_db.py       checks the database connection
├── check_llm.py      checks the Gemini connection and lists available models
├── eval/             16 test cases + evaluation runner
├── data/             15 synthetic sample CVs
└── .streamlit/       UI theme
```

## Quick start (local)

**Requirements:** Python 3.10+, Docker, and a [Gemini API key](https://aistudio.google.com/). Allow about 6 GB of free disk space (PyTorch and the embedding model).

**1. Start PostgreSQL with pgvector**

```bash
docker run -d --name rag-postgres \
  -e POSTGRES_USER=raguser -e POSTGRES_PASSWORD=ragpass -e POSTGRES_DB=ragdb \
  -p 5433:5432 -v rag_postgres_data:/var/lib/postgresql \
  pgvector/pgvector:pg18
```

**2. Install**

```bash
git clone https://github.com/majd-eleyan/Sifter.git
cd Sifter
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# macOS / Linux:       source .venv/bin/activate
pip install -r requirements.txt
```

**3. Configure**

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

Open `.env` and set `GEMINI_API_KEY`. Check the model name with `python check_llm.py`, which lists the models available to your key; set `GEMINI_MODEL` if needed.

**4. Create the tables and load the sample CVs**

```bash
python setup_db.py
python ingest.py
python check_db.py          # optional: confirms the connection and shows row counts
```

The first run downloads the embedding model (about 90 MB, once).

**5. Run**

```bash
streamlit run app.py
```

Open http://localhost:8501 and try: *Who has Python skills and at least 3 years of experience?*

## Configuration

Settings come from environment variables (a `.env` file locally, or Secrets when deployed).

| Variable | Default | Description |
|---|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | `localhost`, `5433`, `ragdb`, `raguser`, `ragpass` | Local database settings |
| `DATABASE_URL` | empty | Full connection string (Neon, Supabase). Overrides the `DB_*` values |
| `GEMINI_API_KEY` | empty | **Required** |
| `GEMINI_MODEL` | `gemini-flash-latest` | Model name. Model names change over time, so verify with `check_llm.py` |
| `TOP_K` / `TOP_N` | `10` / `5` | Chunks retrieved / full CVs sent to the LLM |
| `CHUNK_STRATEGY` | `section` | `section`, `recursive`, or `fixed` |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Must output 384 dimensions (or change `VECTOR(384)` in `schema.sql`) |
| `APP_PASSWORD` | empty | If set, the UI asks for this password. Recommended for public deployments |
| `DRIVE_FOLDER_ID`, `GOOGLE_SERVICE_ACCOUNT_FILE` or `GOOGLE_SERVICE_ACCOUNT_JSON` | empty | Google Drive sync |
| `PRICE_IN_PER_1M`, `PRICE_OUT_PER_1M` | `0` | Token prices (USD per million) used to estimate cost in traces |

## CV template and file naming

A CV is added automatically when it is a **text PDF** (not a scan) with an email address and these six headings, each on its own line:

```
PROFESSIONAL SUMMARY · CORE SKILLS · EXPERIENCE · EDUCATION · SELECTED PROJECTS · CERTIFICATIONS
```

The department is read from the file name:

```
NN_Department_FirstName_LastName.pdf      e.g.  01_Data_and_AI_Omar_Khalil.pdf
```

Known departments: Data and AI, Software Engineering, Cybersecurity, Digital Marketing, Finance and Accounting. If the name does not follow the rule, the department is guessed from the job title. CVs that fail the check go to the **Review** tab.

## Google Drive sync

1. In Google Cloud Console, enable the **Google Drive API** and create a **Service Account**; download its JSON key as `credentials.json`.
2. Share your Drive folder with the service account's email (Viewer).
3. Set `DRIVE_FOLDER_ID` in `.env`.
4. Run `python drive_sync.py --once` to test, or `python drive_sync.py` to watch the folder (checks every `DRIVE_POLL_SECONDS`).

Only PDF files directly inside the folder are read. File names must be unique.

## Evaluation

```bash
python eval/run_eval.py --prompt baseline   # simple prompt (for comparison only)
python eval/run_eval.py --prompt best       # the prompt the app uses
python eval/run_eval.py --compare
```

- **16 cases:** 4 Normal, 4 Edge, 4 Failure, 4 Risky (`eval/test_cases.json`), each with a ground-truth answer or expected behavior.
- **Metrics:** retrieval recall and precision, completeness, safety (contact-detail leaks), latency, tokens/cost, and an LLM-judge verdict.
- **Tracing:** each run is stored in `rag_traces`, and the report states where a failure started (retrieval or generation).
- Reports are written to `eval/report_<prompt>.md` and `eval/results_<prompt>.json`.

The ground truth was computed from the sample CVs and should be verified manually before you rely on it.

## Security and privacy

- Secrets live in `.env` / Secrets only and are excluded by `.gitignore`.
- Contact details are redacted before indexing and before text is sent to the LLM.
- The database is queried with parameterized SQL, and CV text is HTML-escaped in the UI.
- Set `APP_PASSWORD` for any public deployment, since the UI can upload and delete CVs.
- Full CV text is sent to the Gemini API. With real candidate data you need consent and a privacy policy.

## Limitations

- The default embedding model is English-only, so questions in other languages retrieve less accurately. A multilingual 384-dimension model (`paraphrase-multilingual-MiniLM-L12-v2`) is a drop-in replacement; re-ingest after changing it.
- Only `TOP_N` CVs reach the LLM. If more candidates qualify, some are not seen; raise `TOP_N` when needed.
- Years of experience come from the CV summary (falling back to the dates), so they can differ from a manual count.
- The ATS check validates structure, not content quality. Scanned PDFs are not OCR'd.
