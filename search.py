"""الاسترجاع: سؤال ← أقرب chunks (SQL) ← المرشحين ← نص الـ CV الكامل لكل مرشح.

الفكرة (الدقة أعلى):
    1) نجيب أقرب K chunk بالمعنى.
    2) نعرف من أي CVs جاءوا ونختار أفضل N مرشح.
    3) نبعت الـ CV الكامل لكل مرشح للـ LLM (مش بس القطع)، فما بيفوته شي من الـ CV.
"""
import embedding
from config import CHUNK_STRATEGY, TOP_K, TOP_N
from cv_parser import redact
from db import get_conn


def search_chunks(question, k=TOP_K, department=None, min_years=None, strategy=CHUNK_STRATEGY):
    qvec = embedding.to_vector(embedding.embed_one(question))
    sql = """
        SELECT d.id, d.filename, d.candidate_name, c.section, c.content,
               c.embedding <=> %(q)s::vector AS distance
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.status = 'ready'
          AND c.strategy = %(strategy)s
          AND (%(dept)s::text IS NULL OR d.department = %(dept)s)
          AND (%(years)s::numeric IS NULL OR d.years_experience >= %(years)s)
        ORDER BY distance
        LIMIT %(k)s
    """
    params = {"q": qvec, "strategy": strategy, "dept": department, "years": min_years, "k": k}
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        {"doc_id": r[0], "filename": r[1], "candidate_name": r[2], "section": r[3],
         "content": r[4], "distance": float(r[5])}
        for r in rows
    ]


def pick_candidates(chunks, n=TOP_N):
    """نجمع الـ chunks حسب الـ CV، وبنرتب المرشحين حسب أقرب chunk لكل واحد."""
    best = {}
    for c in chunks:                                   # الـ chunks أصلاً مرتبة من الأقرب للأبعد
        item = best.setdefault(c["doc_id"], {
            "doc_id": c["doc_id"], "filename": c["filename"], "candidate_name": c["candidate_name"],
            "score": max(0.0, 1 - c["distance"]), "sections": [], "n_chunks": 0,
        })
        item["n_chunks"] += 1
        if c["section"] not in item["sections"]:
            item["sections"].append(c["section"])
    return list(best.values())[:n]


def get_full_cvs(doc_ids):
    """بيرجع الـ CV الكامل (بعد إخفاء الإيميل والهاتف) بنفس ترتيب doc_ids."""
    if not doc_ids:
        return []
    sql = """SELECT id, filename, candidate_name, title, department, years_experience, skills, full_text
             FROM documents WHERE id = ANY(%s) AND status = 'ready'"""
    with get_conn() as conn:
        rows = {r[0]: r for r in conn.execute(sql, (list(doc_ids),)).fetchall()}
    cvs = []
    for doc_id in doc_ids:
        if doc_id in rows:
            _, filename, name, title, dept, years, skills, text = rows[doc_id]
            cvs.append({"doc_id": doc_id, "filename": filename, "candidate_name": name, "title": title,
                        "department": dept, "years_experience": float(years) if years is not None else None,
                        "skills": skills, "text": redact(text)})
    return cvs
