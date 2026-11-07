"""قراءة الـ CV: PDF ← نص ← أقسام ← metadata ← فحص ATS.

قالب ATS اللي بنطلبه: ملف PDF نصي (مش صورة) فيه 6 عناوين بالأحرف الكبيرة، كل عنوان بسطر لحاله:
    PROFESSIONAL SUMMARY / CORE SKILLS / EXPERIENCE / EDUCATION / SELECTED PROJECTS / CERTIFICATIONS
وأول الملف: الاسم، ثم المسمى الوظيفي، ثم سطر التواصل (إيميل | هاتف).
"""
import datetime
import re

import pymupdf

ATS_SECTIONS = [
    "PROFESSIONAL SUMMARY",
    "CORE SKILLS",
    "EXPERIENCE",
    "EDUCATION",
    "SELECTED PROJECTS",
    "CERTIFICATIONS",
]

DEPARTMENTS = [
    "Data and AI",
    "Software Engineering",
    "Cybersecurity",
    "Digital Marketing",
    "Finance and Accounting",
]

# إذا اسم الملف ما التزم بالقاعدة، بنحاول نخمّن القسم من المسمى الوظيفي
DEPT_KEYWORDS = {
    "Data and AI": ["machine learning", "data scientist", "data analyst", "data engineer", "ai engineer", "mlops"],
    "Cybersecurity": ["security", "soc ", "penetration", "incident response"],
    "Digital Marketing": ["marketing", "seo", "social media", "content"],
    "Finance and Accounting": ["account", "financ", "audit", "payroll"],
    "Software Engineering": ["software", "backend", "frontend", "full stack", "full-stack", "developer"],
}

# قاعدة تسمية الملفات:  رقم_القسم_الاسم_الأول_الاسم_الأخير.pdf   مثال: 01_Data_and_AI_Omar_Khalil.pdf
FILENAME_RE = re.compile(r"^\d+_(?P<dept>.+)_(?P<first>[A-Za-z]+)_(?P<last>[A-Za-z]+)\.pdf$", re.I)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"\+?\d{1,3}[\s.-]?\(?\d{2,4}\)?[\s.-]?\d{3}[\s.-]?\d{3,4}")


# ---------------------------------------------------------------- 1) قراءة PDF
def read_pdf(source):
    """source = مسار ملف، أو bytes (لما نحمّل الملف من Google Drive أو من رفع الواجهة)."""
    if isinstance(source, (bytes, bytearray)):
        doc = pymupdf.open(stream=bytes(source), filetype="pdf")
    else:
        doc = pymupdf.open(str(source))
    text = "\n".join(page.get_text() for page in doc)
    return "\n".join(line.rstrip() for line in text.splitlines())


# ---------------------------------------------------------------- 2) تقسيم الأقسام
def split_sections(text):
    """بترجع قاموس: اسم القسم ← نصه. كل اللي قبل أول عنوان بيروح لـ HEADER."""
    parts = {"HEADER": []}
    current = "HEADER"
    for line in text.splitlines():
        s = line.strip()
        if s in ATS_SECTIONS:
            current = s
            parts.setdefault(current, [])
        else:
            parts[current].append(s)
    return {name: "\n".join(l for l in lines if l).strip() for name, lines in parts.items()}


# ---------------------------------------------------------------- 3) فحص ATS
def check_ats(text):
    sections = split_sections(text)
    issues = [f"Missing section: {s}" for s in ATS_SECTIONS if not sections.get(s)]
    if len(text.strip()) < 300:
        issues.append("Almost no extractable text (scanned image?)")
    if not EMAIL_RE.search(text):
        issues.append("No email address found")
    return {"ok": not issues, "issues": issues}


# ---------------------------------------------------------------- 4) Metadata
def parse_filename(filename):
    m = FILENAME_RE.match(filename)
    if not m:
        return None, None
    dept = m.group("dept").replace("_", " ")
    dept = next((d for d in DEPARTMENTS if d.lower() == dept.lower()), None)
    return dept, f"{m.group('first')} {m.group('last')}"


def header_lines(sections):
    return [l for l in sections["HEADER"].splitlines() if l.strip() and not l.lower().startswith("synthetic cv")]


def extract_skills(sections):
    body = " ".join(sections.get("CORE SKILLS", "").splitlines())
    parts = re.split(r"•|\||;", body) if "•" in body or "|" in body else body.split(",")
    return [p.strip() for p in parts if p.strip()]


def extract_years(sections):
    # 1) الرقم المكتوب بالـ summary مثل "3+ years" أو "5 years"
    m = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*years?", sections.get("PROFESSIONAL SUMMARY", ""), re.I)
    if m:
        return float(m.group(1))
    # 2) وإلا نجمع فترات الشغل من قسم EXPERIENCE (2022 - 2024 / 2024 - Present)
    now = datetime.date.today().year
    total = 0
    for start, end in re.findall(r"(\d{4})\s*[-–]\s*(\d{4}|Present|Current)", sections.get("EXPERIENCE", ""), re.I):
        total += max(0, (now if end[0].isalpha() else int(end)) - int(start))
    return float(total) if total else None


def guess_department(title, summary):
    text = f"{title} {summary}".lower()
    for dept, words in DEPT_KEYWORDS.items():
        if any(w in text for w in words):
            return dept
    return None


def extract_metadata(text, filename):
    sections = split_sections(text)
    lines = header_lines(sections)
    file_dept, file_name = parse_filename(filename)

    # الاسم: أول سطر بالـ CV (إذا شكله اسم)، وإلا من اسم الملف
    name = None
    if lines and re.fullmatch(r"[A-Za-z][A-Za-z .'-]{3,60}", lines[0]) and len(lines[0].split()) >= 2:
        name = lines[0].title() if lines[0].isupper() else lines[0]
    name = name or file_name or filename.rsplit(".", 1)[0]

    title = lines[1] if len(lines) > 1 and len(lines[1]) < 80 else None

    # القسم: 1) من اسم الملف  2) من نص الـ CV  3) Unknown
    if file_dept:
        department, source = file_dept, "file name"
    else:
        guessed = guess_department(title or "", sections.get("PROFESSIONAL SUMMARY", ""))
        department, source = (guessed, "CV text") if guessed else ("Unknown", "not found")

    return {
        "candidate_name": name,
        "title": title,
        "department": department,
        "department_source": source,
        "years_experience": extract_years(sections),
        "skills": extract_skills(sections),
    }


# ---------------------------------------------------------------- 5) حماية الخصوصية
def redact(text):
    """بنخفي الإيميل والهاتف قبل ما ننشئ chunks أو نبعت النص للـ LLM."""
    text = EMAIL_RE.sub("[email hidden]", text)
    return PHONE_RE.sub("[phone hidden]", text)
