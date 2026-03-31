import re
import time
import logging

import httplib2
import google_auth_httplib2
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload


def _build_http(creds):
    return google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http(timeout=120))


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
    return build("drive", "v3", http=_build_http(creds), cache_discovery=False)


def get_services():
    creds, _ = default(scopes=[
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/spreadsheets",
    ])
    drive = build("drive", "v3", http=_build_http(creds), cache_discovery=False)
    sheets = build("sheets", "v4", http=_build_http(creds), cache_discovery=False)
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


