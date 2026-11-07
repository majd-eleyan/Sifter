"""الـ pipeline كامل بدالة وحدة:  سؤال ← بحث بـ SQL ← CVs كاملة ← LLM ← جواب + Trace.

ask() بتسجل كل خطوة بجدول rag_traces، فنعرف وين صارت المشكلة: Retrieval ولا Generation.
"""
import json
import time

import llm
import search
from config import PRICE_IN_PER_1M, PRICE_OUT_PER_1M, TOP_K, TOP_N
from db import get_conn

NO_RESULTS = "I could not find any matching CVs in the database, so I can't answer this question."


def _ms(start):
    return int((time.perf_counter() - start) * 1000)


def log_trace(t):
    """تسجيل التشغيل. لو فشل التسجيل ما منوقف النظام."""
    try:
        with get_conn() as conn:
            row = conn.execute(
                """INSERT INTO rag_traces
                       (test_id, prompt_version, question, retrieved, sent_cvs, answer, error,
                        retrieval_ms, llm_ms, total_ms, prompt_tokens, completion_tokens, cost_usd)
                   VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (t["test_id"], t["prompt_version"], t["question"],
                 json.dumps(t["retrieved"]), json.dumps(t["sent_cvs"]), t["answer"], t["error"],
                 t["retrieval_ms"], t["llm_ms"], t["total_ms"],
                 t["prompt_tokens"], t["completion_tokens"], t["cost_usd"]),
            ).fetchone()
        return row[0]
    except Exception:
        return None


def ask(question, k=TOP_K, n_cvs=TOP_N, prompt_version="best", department=None, min_years=None,
        shortlist_ids=None, simulate_failure=None, test_id=None):
    """
    k             كم chunk نسترجع
    n_cvs         كم CV كامل نبعت للـ LLM
    shortlist_ids لو انعطت: بنتخطى البحث ونسأل عن نفس المرشحين (أسئلة المتابعة)
    simulate_failure  "retrieval" أو "llm" (لاختبار حالات الفشل بالتقييم)
    """
    start = time.perf_counter()
    chunks, shortlist, cvs = [], [], []
    tokens = {"prompt_tokens": 0, "completion_tokens": 0}
    retrieval_ms = llm_ms = 0
    answer, error, stage = "", None, "retrieval"

    try:
        # ---------- 1) Retrieval ----------
        t = time.perf_counter()
        if simulate_failure == "retrieval":
            raise RuntimeError("Simulated failure: the CV database could not be reached")
        if shortlist_ids is None:
            chunks = search.search_chunks(question, k, department, min_years)
            picked = search.pick_candidates(chunks, n_cvs)
        else:
            picked = [{"doc_id": i, "score": None, "sections": []} for i in shortlist_ids]
        cvs = search.get_full_cvs([p["doc_id"] for p in picked])
        retrieval_ms = _ms(t)

        by_id = {p["doc_id"]: p for p in picked}
        shortlist = [
            {**cv, "score": by_id[cv["doc_id"]]["score"], "sections": by_id[cv["doc_id"]]["sections"]}
            for cv in cvs
        ]

        # ---------- 2) Generation ----------
        stage = "generation"
        if not cvs:
            answer = NO_RESULTS
        else:
            if simulate_failure == "llm":
                raise RuntimeError("Simulated failure: the language model is unavailable")
            t = time.perf_counter()
            answer, tokens = llm.generate_answer(question, cvs, prompt_version)
            llm_ms = _ms(t)

    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        detail = getattr(e, "body", None) or getattr(getattr(e, "response", None), "text", "")
        if detail:
            error += f" | {str(detail)[:300]}"      # رد السيرفر الحقيقي (مثلاً: model not found)
        if stage == "retrieval":
            answer = ("⚠️ I could not retrieve the CVs (" + error + "). I did NOT check any CVs, "
                      "so I can't give a reliable answer. Please try again.")
        else:
            answer = ("⚠️ I found the matching CVs, but could not generate the answer (" + error + "). "
                      "Please try again.")

    cost = (tokens["prompt_tokens"] * PRICE_IN_PER_1M + tokens["completion_tokens"] * PRICE_OUT_PER_1M) / 1e6
    trace = {
        "test_id": test_id, "prompt_version": prompt_version, "question": question,
        "retrieved": [{"file": c["filename"], "section": c["section"], "distance": round(c["distance"], 4)} for c in chunks],
        "sent_cvs": [c["filename"] for c in cvs],
        "answer": answer, "error": error,
        "retrieval_ms": retrieval_ms, "llm_ms": llm_ms, "total_ms": _ms(start),
        "prompt_tokens": tokens["prompt_tokens"], "completion_tokens": tokens["completion_tokens"],
        "cost_usd": round(cost, 6),
    }
    trace["trace_id"] = log_trace(trace)

    return {"answer": answer, "shortlist": shortlist, "chunks": chunks, "error": error, "stage": stage if error else None,
            "retrieval_ms": retrieval_ms, "llm_ms": llm_ms, "total_ms": trace["total_ms"],
            "tokens": tokens, "cost_usd": trace["cost_usd"], "trace_id": trace["trace_id"]}


def recent_traces(limit=30):
    with get_conn() as conn:
        return conn.execute(
            """SELECT id, created_at, test_id, prompt_version, question, retrieval_ms, llm_ms, total_ms,
                      COALESCE(prompt_tokens, 0) + COALESCE(completion_tokens, 0), error
               FROM rag_traces ORDER BY id DESC LIMIT %s""", (limit,)).fetchall()


def get_trace(trace_id):
    with get_conn() as conn:
        return conn.execute("SELECT retrieved, sent_cvs, answer FROM rag_traces WHERE id = %s", (trace_id,)).fetchone()
