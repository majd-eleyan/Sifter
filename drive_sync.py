"""ربط Google Drive: أي CV (PDF) جديد بالمجلد بيتحمّل وبينعمل له ingest أوتوماتيك.

    python drive_sync.py          ← بيشتغل بحلقة: بيفحص المجلد كل DRIVE_POLL_SECONDS ثانية
    python drive_sync.py --once   ← فحص مرة وحدة وبيطلع

إعدادات مرة وحدة (التفاصيل بـ README):
    1) Google Cloud ← فعّل Google Drive API ← أنشئ Service Account ← نزّل مفتاح JSON باسم credentials.json
    2) شارك مجلد الـ Drive مع إيميل الـ Service Account (صلاحية Viewer)
    3) حط DRIVE_FOLDER_ID بملف .env
"""
import io
import json
import sys
import time

import ingest
from config import DRIVE_FOLDER_ID, DRIVE_POLL_SECONDS, GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_SERVICE_ACCOUNT_JSON
from db import get_conn

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def is_configured():
    from pathlib import Path
    return bool(DRIVE_FOLDER_ID) and (bool(GOOGLE_SERVICE_ACCOUNT_JSON) or Path(GOOGLE_SERVICE_ACCOUNT_FILE).exists())


def get_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    if GOOGLE_SERVICE_ACCOUNT_JSON:       # عند النشر: المفتاح بيجي كنص من الـ Secrets (ما بنرفع ملف credentials.json)
        info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:                                 # محلياً: من الملف
        creds = service_account.Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_pdfs(service, folder_id):
    files, token = [], None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false",
            fields="nextPageToken, files(id, name)", pageSize=100, pageToken=token,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        files += resp.get("files", [])
        token = resp.get("nextPageToken")
        if not token:
            return files


def download(service, file_id):
    from googleapiclient.http import MediaIoBaseDownload
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def known_drive_ids():
    with get_conn() as conn:
        rows = conn.execute("SELECT drive_file_id FROM documents WHERE drive_file_id IS NOT NULL").fetchall()
    return {r[0] for r in rows}


def sync_once(service=None):
    """بيدخل أي ملف جديد. بيرجع قائمة بنتائج الملفات الجديدة."""
    if not DRIVE_FOLDER_ID:
        raise RuntimeError("DRIVE_FOLDER_ID is missing in .env")
    service = service or get_service()
    known = known_drive_ids()
    results = []
    for f in list_pdfs(service, DRIVE_FOLDER_ID):
        if f["id"] in known:
            continue
        data = download(service, f["id"])
        results.append(ingest.ingest_pdf(data, f["name"], drive_file_id=f["id"]))
    return results


def watch():
    print(f"مراقبة المجلد كل {DRIVE_POLL_SECONDS} ثانية... (Ctrl+C للإيقاف)")
    service = get_service()
    while True:
        try:
            for r in sync_once(service):
                print(f"[Drive] {r['filename']} → {r['result']}")
        except Exception as e:                      # أي خطأ مؤقت (نت مثلاً) ما بيوقف المراقبة
            print("[Drive] error:", e)
        time.sleep(DRIVE_POLL_SECONDS)


if __name__ == "__main__":
    if "--once" in sys.argv:
        for r in sync_once():
            print(f"{r['filename']} → {r['result']}")
        print("done")
    else:
        watch()
