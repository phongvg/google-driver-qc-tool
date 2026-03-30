import json
import logging
import time
import os
from datetime import datetime, timezone

from google.cloud import storage

from clients.drive_client import (
    get_drive_service,
    build_folder_index_rich,
    get_today_yesterday_names,
)
from config import ROOT_FOLDER_IDS

INDEX_BLOB = "folder_index.json"
INDEX_VERSION = 1


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_existing(bucket) -> dict:
    blob = bucket.blob(INDEX_BLOB)
    if not blob.exists():
        logging.info("[index] No existing index, starting fresh.")
        return {"version": INDEX_VERSION, "entries": {}, "last_full_scan_at": ""}
    try:
        raw = json.loads(blob.download_as_text())
        if "entries" in raw:
            logging.info(f"[index] Loaded existing: {len(raw['entries'])} entries")
            return raw
        logging.info(f"[index] Migrating legacy index ({len(raw)} entries)")
        return {
            "version": INDEX_VERSION,
            "entries": {
                name: {
                    "folder_id": "", "folder_url": url, "folder_name": name,
                    "parent_date_folder": "", "modified_time": "", "last_seen_at": "",
                }
                for name, url in raw.items()
            },
            "last_full_scan_at": "",
        }
    except Exception as e:
        logging.warning(f"[index] Failed to load existing index: {e}. Starting fresh.")
        return {"version": INDEX_VERSION, "entries": {}, "last_full_scan_at": ""}


def _merge(existing_entries: dict, new_entries: dict, now: str) -> tuple[dict, int]:
    merged = dict(existing_entries)
    conflicts = 0

    for name, new in new_entries.items():
        new["last_seen_at"] = now
        existing = merged.get(name)

        if existing is None:
            merged[name] = new
        elif not existing.get("folder_id") or existing["folder_id"] == new["folder_id"]:
            merged[name] = new
        else:
            if existing.get("parent_date_folder") == new.get("parent_date_folder"):
                logging.warning(
                    f"[index] CONFLICT {name!r}: duplicate session in same date folder "
                    f"{new.get('parent_date_folder')!r} — overwriting"
                )
                conflicts += 1
            merged[name] = new

    return merged, conflicts


def _is_truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def build_and_save_index(bucket_name: str, date_folders: list = None) -> dict:
    drive_service = get_drive_service()
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    existing = _load_existing(bucket)
    now = _now_iso()

    force_full_scan = _is_truthy(os.environ.get("FULL_SCAN", ""))

    if date_folders is not None:
        effective_date_folders = date_folders
    elif force_full_scan:
        effective_date_folders = None
    else:
        effective_date_folders = get_today_yesterday_names()

    is_full_scan = effective_date_folders is None
    logging.info(f"[index] Scanning Drive (roots={len(ROOT_FOLDER_IDS)}, dates={effective_date_folders}, full={is_full_scan})...")
    t0 = time.time()
    new_entries = build_folder_index_rich(drive_service, ROOT_FOLDER_IDS, effective_date_folders)
    logging.info(f"[index] Scan complete: {len(new_entries)} folders in {int(time.time()-t0)}s")

    if is_full_scan:
        merged_entries = {name: {**e, "last_seen_at": now} for name, e in new_entries.items()}
        conflicts = 0
    else:
        merged_entries, conflicts = _merge(existing["entries"], new_entries, now)

    result = {
        "version": INDEX_VERSION,
        "updated_at": now,
        "last_full_scan_at": now if is_full_scan else existing.get("last_full_scan_at", ""),
        "entries": merged_entries,
    }

    bucket.blob(INDEX_BLOB).upload_from_string(
        json.dumps(result, ensure_ascii=False),
        content_type="application/json",
    )
    logging.info(
        f"[index] Uploaded gs://{bucket_name}/{INDEX_BLOB} "
        f"total={len(merged_entries)} conflicts={conflicts} mode={'full' if is_full_scan else 'incremental'}"
    )
    if conflicts:
        logging.warning(f"[index] {conflicts} conflict(s) — same session_id found in different folders")

    return result
