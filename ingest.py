"""إدخال الـ CVs للداتابيز:  PDF ← نص ← فحص ATS ← metadata ← chunks ← embeddings ← تخزين.

القاعدة:
    CV ملتزم بـ ATS      ← status = ready        (ينعمل له chunks وembeddings فوراً)
    CV مش ملتزم بـ ATS   ← status = pending_review (ينتظر موافقة المراجع بالواجهة، ما بيدخل البحث قبلها)
"""
import json
import sys
from pathlib import Path

import chunking
import cv_parser as P
import embedding
from config import CHUNK_STRATEGY, DATA_DIR
from db import get_conn


def store_chunks(cur, doc_id, filename, text, meta, strategy=CHUNK_STRATEGY):
    """بيعمل chunks + embeddings وبيخزنهم. بيرجع عددهم."""
    sections = P.split_sections(text)
    chunks = chunking.make_chunks(strategy, text, sections, meta)
    vectors = embedding.embed_texts([c["content"] for c in chunks])    # كل القطع دفعة وحدة (أسرع)

    cur.execute("DELETE FROM document_chunks WHERE document_id = %s AND strategy = %s", (doc_id, strategy))
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        metadata = {
            "candidate": meta["candidate_name"],
            "department": meta["department"],
            "section": chunk["section"],
            "source": filename,
        }
        cur.execute(
            """INSERT INTO document_chunks
                   (document_id, strategy, chunk_index, section, content, metadata, embedding)
               VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::vector)""",
            (doc_id, strategy, i, chunk["section"], chunk["content"],
             json.dumps(metadata), embedding.to_vector(vec)),
        )
    return len(chunks)


def ingest_pdf(source, filename, drive_file_id=None):
    """source = مسار أو bytes. بيرجع قاموس فيه شو صار (للطباعة وللواجهة)."""
    text = P.read_pdf(source)
    ats = P.check_ats(text)
    meta = P.extract_metadata(text, filename)

    with get_conn() as conn, conn.cursor() as cur:
        # لو الملف موجود من قبل (نفس الاسم أو نفس رقم Drive) منتخطاه
        cur.execute(
            "SELECT id FROM documents WHERE filename = %s OR (%s::text IS NOT NULL AND drive_file_id = %s)",
            (filename, drive_file_id, drive_file_id),
        )
        row = cur.fetchone()
        if row:
            return {"filename": filename, "doc_id": row[0], "result": "skipped (already in database)", "chunks": 0}

        status = "ready" if ats["ok"] else "pending_review"
        cur.execute(
            """INSERT INTO documents
                   (filename, drive_file_id, candidate_name, title, department, years_experience,
                    skills, full_text, ats_ok, ats_issues, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (filename, drive_file_id, meta["candidate_name"], meta["title"], meta["department"],
             meta["years_experience"], meta["skills"], text, ats["ok"], ats["issues"], status),
        )
        doc_id = cur.fetchone()[0]

        n_chunks = store_chunks(cur, doc_id, filename, text, meta) if ats["ok"] else 0

    return {
        "filename": filename, "doc_id": doc_id, "candidate": meta["candidate_name"],
        "department": meta["department"], "status": status,
        "issues": ats["issues"], "chunks": n_chunks,
        "result": "added" if ats["ok"] else "sent to human review (not ATS-friendly)",
    }


def ingest_folder(folder=DATA_DIR):
    return [ingest_pdf(p, p.name) for p in sorted(Path(folder).glob("*.pdf"))]


# ---------------------------------------------------------------- مراجعة بشرية (HITL)
def approve(doc_id, name=None, department=None, years=None):
    """المراجع وافق: نعدّل الـ metadata لو بدو، وبعدين ندخله للبحث."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT filename, full_text FROM documents WHERE id = %s AND status = 'pending_review'", (doc_id,))
        row = cur.fetchone()
        if not row:
            return 0
        filename, text = row
        meta = P.extract_metadata(text, filename)
        meta["candidate_name"] = name or meta["candidate_name"]
        meta["department"] = department or meta["department"]
        meta["years_experience"] = years if years is not None else meta["years_experience"]

        cur.execute(
            """UPDATE documents SET candidate_name = %s, department = %s, years_experience = %s,
                      skills = %s, status = 'ready' WHERE id = %s""",
            (meta["candidate_name"], meta["department"], meta["years_experience"], meta["skills"], doc_id),
        )
        return store_chunks(cur, doc_id, filename, text, meta)


def reject(doc_id):
    with get_conn() as conn:
        conn.execute("UPDATE documents SET status = 'rejected' WHERE id = %s", (doc_id,))


# ---------------------------------------------------------------- قراءة / حذف (للواجهة)
def list_documents(status=None):
    sql = """SELECT id, candidate_name, department, years_experience, status, filename,
                    drive_file_id IS NOT NULL AS from_drive, ats_issues, skills
             FROM documents WHERE (%s::text IS NULL OR status = %s) ORDER BY id"""
    with get_conn() as conn:
        return conn.execute(sql, (status, status)).fetchall()


def get_document(doc_id):
    with get_conn() as conn:
        return conn.execute("SELECT filename, full_text FROM documents WHERE id = %s", (doc_id,)).fetchone()


def delete_document(doc_id):
    """بيحذف الـ CV وكل chunks تبعته (ON DELETE CASCADE)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM documents WHERE id = %s", (doc_id,))


def counts():
    with get_conn() as conn:
        rows = conn.execute("SELECT status, COUNT(*) FROM documents GROUP BY status").fetchall()
    return {status: n for status, n in rows}


if __name__ == "__main__":
    targets = [Path(a) for a in sys.argv[1:]] or sorted(Path(DATA_DIR).glob("*.pdf"))
    for p in targets:
        r = ingest_pdf(p, p.name)
        print(f"{r['filename']:45} → {r['result']}  ({r['chunks']} chunks)")
        for issue in r.get("issues", []):
            print("      -", issue)
