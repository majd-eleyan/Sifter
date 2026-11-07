import html

import pandas as pd
import streamlit as st

import drive_sync
import ingest
import rag
import hmac

from config import APP_PASSWORD, TOP_K, TOP_N
from cv_parser import ATS_SECTIONS, DEPARTMENTS

st.set_page_config(page_title="Sifter · CV Search", page_icon="✦", layout="wide")

# ============================================================ 
st.markdown("""
<style>
.stApp { background: radial-gradient(1100px 560px at 8% -8%, #1d1808 0%, #0a0a0a 55%); }
.hero { padding: 0.8rem 0 0.6rem; border-bottom: 1px solid #3a2f0f; margin-bottom: 0.8rem; }
.brand { font-family: Georgia, 'Playfair Display', serif; font-size: 2.5rem; font-weight: 700; letter-spacing: .3rem;
         background: linear-gradient(90deg, #F4E3A1, #D4AF37 45%, #9c7a1a);
         -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.tagline { color: #a89868; letter-spacing: .14rem; font-size: .8rem; text-transform: uppercase; }
.card { background: linear-gradient(160deg, #18150a, #0f0f0f); border: 1px solid #3a2f0f; border-left: 3px solid #D4AF37;
        border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; min-height: 165px; }
.card-top { display: flex; justify-content: space-between; align-items: center; font-size: .8rem; color: #a89868; }
.rank { color: #D4AF37; font-weight: 700; }
.score { color: #0a0a0a; background: #D4AF37; border-radius: 20px; padding: 1px 10px; font-weight: 700; }
.name { font-size: 1.15rem; color: #F4E3A1; font-family: Georgia, serif; margin: .4rem 0 .1rem; }
.meta { color: #9b8f6d; font-size: .78rem; margin-bottom: .5rem; }
.chip { display: inline-block; border: 1px solid #5a4a16; color: #e8d9a0; background: #1a1608; border-radius: 20px;
        padding: 1px 9px; font-size: .7rem; margin: 2px 3px 0 0; }
.section-title { color: #D4AF37; letter-spacing: .15rem; text-transform: uppercase; font-size: .8rem; margin: 1.1rem 0 .4rem; }
.stButton > button { background: linear-gradient(90deg, #D4AF37, #b8932a); color: #0a0a0a; font-weight: 700;
                     border: none; border-radius: 8px; }
.stButton > button:hover { filter: brightness(1.12); color: #000; }
.stTabs [data-baseweb="tab"] { color: #a89868; }
.stTabs [aria-selected="true"] { color: #D4AF37; }
.stTabs [data-baseweb="tab-highlight"] { background-color: #D4AF37; }
h1, h2, h3, h4 { color: #F4E3A1; }
</style>
<div class="hero"><div class="brand">✦ Sifter</div>
<div class="tagline">CV intelligence · semantic search over your talent pool</div></div>
""", unsafe_allow_html=True)

# ============================================================ كلمة سر اختيارية (للنشر العام)
if APP_PASSWORD and not st.session_state.get("authed"):
    pwd = st.text_input("Password", type="password")
    if pwd and hmac.compare_digest(pwd.encode(), APP_PASSWORD.encode()):
        st.session_state["authed"] = True
        st.rerun()
    elif pwd:
        st.error("Wrong password")
    st.stop()

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

# ============================================================ حالة الداتابيز
try:
    counts = ingest.counts()
except Exception as e:
    st.error("Database is not reachable. Start it with:  docker start rag-postgres")
    st.caption(str(e)[:200])
    st.stop()

pending_count = counts.get("pending_review", 0)
st.caption(f"{counts.get('ready', 0)} CVs searchable · {pending_count} waiting for review")

tab_search, tab_cvs, tab_review = st.tabs(["Search", "CVs", f"Review ({pending_count})"])


# ============================================================ أدوات عرض
def card_html(rank, c):
    chips = "".join(f"<span class='chip'>{html.escape(s)}</span>" for s in (c["skills"] or [])[:7])
    years = f"{c['years_experience']:g} yrs" if c["years_experience"] is not None else "years n/a"
    score = f"<span class='score'>{c['score'] * 100:.0f}% match</span>" if c.get("score") is not None else ""
    return (f"<div class='card'><div class='card-top'><span class='rank'>#{rank}</span>{score}</div>"
            f"<div class='name'>{html.escape(c['candidate_name'] or c['filename'])}</div>"
            f"<div class='meta'>{html.escape(c['department'] or '')} · {years}<br>{html.escape(c['filename'])}</div>{chips}</div>")


def show_result(res):
    if res["shortlist"]:
        st.markdown("<div class='section-title'>Shortlisted candidates</div>", unsafe_allow_html=True)
        cols = st.columns(min(3, len(res["shortlist"])))
        for i, c in enumerate(res["shortlist"]):
            cols[i % len(cols)].markdown(card_html(i + 1, c), unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Answer</div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(res["answer"])
    st.caption(f"{res['total_ms'] / 1000:.1f} s")


# ============================================================ تبويب 1: البحث
with tab_search:
    question = st.text_area("Ask a question or paste a job description", height=100,
                            placeholder="e.g. Who has Python skills and at least 3 years of experience?")
    with st.expander("Filters (optional)"):
        c1, c2, c3 = st.columns(3)
        dept = c1.selectbox("Department", ["All"] + DEPARTMENTS)
        min_years = c2.number_input("Minimum years of experience", 0.0, 40.0, 0.0, 0.5)
        n_cvs = c3.slider("CVs to compare", 1, 10, TOP_N, help="How many full CVs are sent to the model")

    if st.button("Search", type="primary"):
        if not question.strip():
            st.warning("Write a question first.")
        else:
            with st.spinner("Searching... (the first run also loads the embedding model)"):
                res = rag.ask(question.strip(), k=max(TOP_K, 3 * n_cvs), n_cvs=n_cvs,
                              department=None if dept == "All" else dept, min_years=min_years or None)
            st.session_state["result"] = res
            st.session_state["history"] = []

    res = st.session_state.get("result")
    if res:
        show_result(res)
        if res["shortlist"]:
            st.markdown("<div class='section-title'>Follow-up</div>", unsafe_allow_html=True)
            follow = st.text_input("Ask something else about these same candidates")
            if st.button("Ask") and follow.strip():
                with st.spinner("Thinking..."):
                    r2 = rag.ask(follow.strip(), shortlist_ids=[c["doc_id"] for c in res["shortlist"]])
                st.session_state["history"].append((follow.strip(), r2["answer"]))
            for q, a in st.session_state.get("history", []):
                with st.container(border=True):
                    st.markdown(f"**{q}**")
                    st.markdown(a)

# ============================================================ تبويب 2: الـ CVs
with tab_cvs:
    for r in st.session_state.pop("last_ingest", []):
        icon = "✅" if r.get("status") == "ready" else ("🕒" if r.get("status") == "pending_review" else "⏭️")
        st.write(f"{icon} **{r['filename']}** → {r['result']} ({r['chunks']} chunks)")
        for issue in r.get("issues", []):
            st.caption(f"      • {issue}")

    rows = ingest.list_documents()
    df = pd.DataFrame(rows, columns=["id", "name", "department", "years", "status", "file", "from_drive", "ats_issues", "skills"])
    st.dataframe(df[["name", "department", "years", "status", "file"]], hide_index=True, width="stretch")

    st.markdown("<div class='section-title'>Add CVs</div>", unsafe_allow_html=True)
    uploads = st.file_uploader("Upload CV PDFs", type="pdf", accept_multiple_files=True)
    if st.button("Add uploaded CVs", type="primary") and uploads:
        with st.spinner("Reading, checking the template, embedding..."):
            st.session_state["last_ingest"] = [ingest.ingest_pdf(f.getvalue(), f.name) for f in uploads]
        st.rerun()

    b1, b2 = st.columns(2)
    if b1.button("Load the data/ folder"):
        with st.spinner("Loading data/ ..."):
            st.session_state["last_ingest"] = ingest.ingest_folder()
        st.rerun()
    if drive_sync.is_configured() and b2.button("Sync Google Drive"):
        with st.spinner("Checking the Drive folder..."):
            try:
                st.session_state["last_ingest"] = drive_sync.sync_once() or [
                    {"filename": "(Drive)", "result": "no new CVs", "chunks": 0}]
            except Exception as e:
                st.session_state["flash"] = f"Drive error: {e}"
        st.rerun()

    with st.expander("CV template and file naming"):
        st.write("A CV is added automatically when it is a text PDF (not a scan) with these headings, each on its own line. "
                 "Otherwise it waits in the Review tab.")
        st.code("\n".join(ATS_SECTIONS))
        st.write("File name rule (the department is read from it):")
        st.code("NN_Department_FirstName_LastName.pdf      e.g.  01_Data_and_AI_Omar_Khalil.pdf")
        st.write("Departments: " + ", ".join(DEPARTMENTS))
        if not drive_sync.is_configured():
            st.caption("Google Drive sync is off. To enable it, see the README (DRIVE_FOLDER_ID and credentials.json).")

    with st.expander("Delete a CV"):
        if rows:
            options = {f"{r[1]} · {r[5]}": r[0] for r in rows}
            choice = st.selectbox("CV", list(options))
            sure = st.checkbox("I'm sure")
            if st.button("Delete") and sure:
                ingest.delete_document(options[choice])
                st.session_state["flash"] = "CV deleted."
                st.rerun()

# ============================================================ تبويب 3: مراجعة بشرية
with tab_review:
    pending = ingest.list_documents("pending_review")
    if not pending:
        st.info("No CVs are waiting for review.")
    else:
        st.caption("These CVs did not follow the template, so they are not searchable until you approve them.")
    options = DEPARTMENTS + ["Unknown"]
    for doc_id, name, department, years, _, filename, _, issues, _ in pending:
        with st.expander(f"{filename}  ·  {len(issues)} issue(s)"):
            for issue in issues:
                st.write("• " + issue)
            st.text_area("CV text preview", ingest.get_document(doc_id)[1][:3000], height=160, disabled=True, key=f"t{doc_id}")
            c1, c2, c3 = st.columns(3)
            new_name = c1.text_input("Candidate name", name or "", key=f"n{doc_id}")
            new_dept = c2.selectbox("Department", options, index=options.index(department) if department in options else len(options) - 1, key=f"d{doc_id}")
            new_years = c3.number_input("Years of experience", 0.0, 50.0, float(years or 0), 0.5, key=f"y{doc_id}")
            a, r = st.columns(2)
            if a.button("Approve", key=f"a{doc_id}", type="primary"):
                with st.spinner("Adding..."):
                    n = ingest.approve(doc_id, new_name, new_dept, new_years)
                st.session_state["flash"] = f"{filename} approved ({n} chunks added)."
                st.rerun()
            if r.button("Reject", key=f"r{doc_id}"):
                ingest.reject(doc_id)
                st.session_state["flash"] = f"{filename} rejected."
                st.rerun()
