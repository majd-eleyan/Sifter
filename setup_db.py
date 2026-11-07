"""ينشئ الجداول. شغّله من VS Code Terminal:

    python setup_db.py            ← ينشئ الجداول إذا مش موجودة
    python setup_db.py --reset    ← يحذف الجداول القديمة وينشئها من جديد (بيمسح البيانات!)، وبيسألك تأكيد
    python setup_db.py --reset --yes   ← نفس الشي بدون سؤال
"""
import sys
from pathlib import Path

from config import DATABASE_URL, DB
from db import get_conn


def main():
    reset = "--reset" in sys.argv
    sql = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")

    with get_conn() as conn:
        if reset:
            target = DATABASE_URL.split("@")[-1] if DATABASE_URL else f"{DB['host']}:{DB['port']}/{DB['dbname']}"
            if "--yes" not in sys.argv and input(f"This DELETES all tables in {target}. Type yes to continue: ").strip() != "yes":
                print("Cancelled.")
                return
            conn.execute("DROP TABLE IF EXISTS rag_traces, document_chunks, documents CASCADE")
            print("تم حذف الجداول القديمة")
        conn.execute(sql)

    print("الداتابيز جاهزة ✔")


if __name__ == "__main__":
    main()
