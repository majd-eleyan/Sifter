"""طرق التقطيع الثلاثة  الافتراضي: section لأنه قالب ATS بيضمن وجود الأقسام."""
import cv_parser as P


def fixed_chunks(text, size=500, overlap=50):
    chunks, start = [], 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap          # نرجع للخلف = الـ overlap
    return chunks


def recursive_chunks(text, size=500, overlap=50):
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    return RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap).split_text(text)


def clean_header(header):
    """الاسم والمسمى والمدينة فقط. نشيل سطر "Synthetic CV" والإيميل والهاتف."""
    keep = []
    for line in header.splitlines():
        if line.lower().startswith("synthetic cv"):
            continue
        if "@" in line:                       # سطر التواصل: منحتفظ بالمدينة بس (أول جزء قبل |)
            line = line.split("|")[0].strip()
        if line.strip():
            keep.append(line.strip())
    return "\n".join(keep)


def section_chunks(sections, meta):
    """قطعة لكل قسم. كل قطعة بتبدأ باسم المرشح والقسم، عشان تنفهم لحالها (حتى لو انرجعت لحالها من البحث)."""
    ctx = f"Candidate: {meta['candidate_name']} | Department: {meta['department']}"
    out = []
    for name in ["HEADER"] + P.ATS_SECTIONS:
        body = clean_header(sections["HEADER"]) if name == "HEADER" else sections.get(name, "")
        if not body:
            continue
        label = "PROFILE" if name == "HEADER" else name
        pieces = [body] if len(body) <= 1200 else recursive_chunks(body, 800, 100)   # حماية من الأقسام الطويلة
        for piece in pieces:
            out.append({"section": label, "content": f"{ctx} | Section: {label}\n{piece}"})
    return out


def make_chunks(strategy, text, sections, meta):
    ctx = f"Candidate: {meta['candidate_name']} | Department: {meta['department']}"
    has_ats = any(sections.get(s) for s in P.ATS_SECTIONS)

    if strategy == "section" and has_ats:
        return section_chunks(sections, meta)

    # fixed / recursive، أو CV بدون أقسام ATS (بعد موافقة المراجع): نشتغل على النص كامل بعد إخفاء التواصل
    clean = P.redact(text)
    splitter = fixed_chunks if strategy == "fixed" else recursive_chunks
    return [{"section": "TEXT", "content": f"{ctx}\n{piece}"} for piece in splitter(clean)]
