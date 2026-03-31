import re
import time
import logging
from datetime import datetime, timedelta, timezone
from collections import deque

import httplib2
from google.auth import default
from google.auth.transport.httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from config import ROOT_FOLDER_IDS

HTTP_TIMEOUT = 120


def _build_authorized_http(creds):
    return AuthorizedHttp(creds, http=httplib2.Http(timeout=HTTP_TIMEOUT))


def _call_with_retry(fn, retries=3, backoff=2.0):
    for attempt in range(retries):
        try:
            return fn()
        except HttpError as e:
            if e.resp.status in (429, 500, 503) and attempt < retries - 1:
                wait = backoff * (2 ** attempt) if e.resp.status == 429 else backoff * (attempt + 1)
                logging.warning(f"Drive API {e.resp.status}, retry {attempt+1}/{retries-1} in {wait}s...")
                time.sleep(wait)
            else:
                raise


def get_drive_service():
    creds, _ = default(scopes=["https://www.googleapis.com/auth/drive.readonly"])
    return build("drive", "v3", http=_build_authorized_http(creds), cache_discovery=False)


def get_services():
    creds, _ = default(scopes=[
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/spreadsheets",
    ])
    drive = build("drive", "v3", http=_build_authorized_http(creds), cache_discovery=False)
    sheets = build("sheets", "v4", http=_build_authorized_http(creds), cache_discovery=False)
    return drive, sheets


def extract_folder_id(folder_url: str) -> str:
    for pattern in [r"/folders/([a-zA-Z0-9_-]+)", r"id=([a-zA-Z0-9_-]+)"]:
        match = re.search(pattern, folder_url)
        if match:
            return match.group(1)
    raw = folder_url.strip()
    if re.fullmatch(r"[a-zA-Z0-9_-]{10,}", raw):
        return raw
    raise ValueError("Invalid Google Drive folder link")


def list_files_in_folder(drive_service, folder_id: str):
    response = _call_with_retry(lambda: drive_service.files().list(
        q=f"'{folder_id}' in parents and trashed = false",
        fields="files(id,name,mimeType,createdTime)",
        pageSize=100,
        corpora="allDrives",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute())
    return response.get("files", [])


def download_file(drive_service, file_id: str, output_path: str):
    request_media = drive_service.files().get_media(fileId=file_id)
    with open(output_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request_media, chunksize=10 * 1024 * 1024)  # 10MB chunk
        done = False
        while not done:
            _, done = downloader.next_chunk()


def _list_subfolders(drive_service, folder_id: str) -> list:
    items = []
    page_token = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            "fields": "nextPageToken, files(id, name, modifiedTime)",
            "pageSize": 1000,
            "corpora": "allDrives",
            "includeItemsFromAllDrives": True,
            "supportsAllDrives": True,
        }
        if page_token:
            params["pageToken"] = page_token
        result = _call_with_retry(lambda p=params: drive_service.files().list(**p).execute())
        items.extend(result.get("files", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return items


def _parse_iso_datetime(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_today_yesterday_names() -> list[str]:
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    return [f"{d.strftime('%B')} {d.day}" for d in [yesterday, today]]


def build_folder_index_rich(drive_service, root_folder_ids: list = None, date_folder_names: list = None) -> dict:
    if root_folder_ids is None:
        root_folder_ids = ROOT_FOLDER_IDS
    date_set = set(date_folder_names) if date_folder_names is not None else None
    logging.info(f"[folder_index] Building rich index (roots={len(root_folder_ids)}, dates={date_folder_names})...")
    entries = {}

    for root_id in root_folder_ids:
        root_children = _list_subfolders(drive_service, root_id)
        start_folders = [f for f in root_children if f["name"] in date_set] if date_set is not None else root_children

        for date_folder in start_folders:
            queue = deque(_list_subfolders(drive_service, date_folder["id"]))
            visited = {date_folder["id"]}

            while queue:
                folder = queue.popleft()
                if folder["id"] in visited:
                    continue
                visited.add(folder["id"])

                children = _list_subfolders(drive_service, folder["id"])
                if children:
                    queue.extend(children)
                    continue

                if folder["name"] not in entries:
                    entries[folder["name"]] = {
                        "folder_id": folder["id"],
                        "folder_url": f"https://drive.google.com/drive/folders/{folder['id']}",
                        "folder_name": folder["name"],
                        "parent_date_folder": date_folder["name"],
                        "modified_time": folder.get("modifiedTime", ""),
                    }
                else:
                    existing = entries[folder["name"]]
                    if existing["parent_date_folder"] == date_folder["name"]:
                        logging.warning(
                            f"[folder_index] CONFLICT {folder['name']!r}: "
                            f"duplicate session in same date folder {date_folder['name']!r} — keeping first"
                        )

    logging.info(f"[folder_index] Rich index built: {len(entries)} entries")
    return entries


def load_folder_index_from_gcs(bucket_name: str, blob_name: str = "folder_index.json") -> dict:
    import json
    from google.cloud import storage
    client = storage.Client()
    data = client.bucket(bucket_name).blob(blob_name).download_as_text()
    raw = json.loads(data)

    if "entries" in raw:
        index = {name: e["folder_url"] for name, e in raw["entries"].items()}
        logging.info(f"[folder_index] Loaded from GCS: {len(index)} folders (v{raw.get('version', '?')})")
    else:
        index = raw
        logging.info(f"[folder_index] Loaded from GCS: {len(index)} folders (legacy)")
    return index
