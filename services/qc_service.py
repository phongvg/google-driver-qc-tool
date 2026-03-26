import os
import logging
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from config import (
    COL_SESSION_ID, COL_LINK,
    COL_STATUS, COL_REASON, COL_CHECKED_AT, COL_VIDEO_DUR, COL_UPLOAD_DATE,
)
from clients.drive_client import get_drive_service, get_services, extract_folder_id, list_files_in_folder, download_file
from clients.sheets_client import cell_value, make_range, read_sheet, batch_write
from core.qc_core import run_qc, run_csv_only, summarize_issues

_thread_local = threading.local()
_disk_semaphore = threading.Semaphore(4)


def _get_thread_drive_service():
    if not hasattr(_thread_local, "drive_service"):
        _thread_local.drive_service = get_drive_service()
    return _thread_local.drive_service


def _get_thread_sheets_service():
    if not hasattr(_thread_local, "sheets_service"):
        _, _thread_local.sheets_service = get_services()
    return _thread_local.sheets_service


def build_response(report: dict, mp4_created_time: str = "") -> dict:
    checks = report.get("checks", {})
    video = checks.get("video_validation", {})
    sync = checks.get("sync_validation", {})
    timeline = checks.get("timeline_validation", {})
    schema = checks.get("schema_validation", {})
    input_check = checks.get("input_validation", {})

    upload_date = ""
    if mp4_created_time:
        raw = mp4_created_time[:10]
        parts = raw.split("-")
        upload_date = f"{parts[1]}/{parts[2]}/{parts[0]}" if len(parts) == 3 else raw

    resolution = ""
    if video.get("width") and video.get("height"):
        resolution = f"{video['width']}x{video['height']}"

    duration_s = ""
    if timeline.get("duration_ms") is not None:
        duration_s = round(float(timeline["duration_ms"]) / 1000.0, 2)

    status = report.get("status", "FAIL")
    reason = summarize_issues(report)

    return {
        "status": status,
        "reason": reason,
        "resolution": resolution,
        "fps": round(video["fps"], 2) if video.get("fps") is not None else "",
        "sync_ms": round(sync["delta_ms"], 0) if sync.get("delta_ms") is not None else "",
        "rows": schema.get("row_count", ""),
        "duration_s": duration_s,
        "activity": "Yes" if input_check.get("has_activity") else "No",
        "video_duration_s": round(video["duration_sec"]) if video.get("duration_sec") is not None else "",
        "upload_date": upload_date,
        "fail_intervals_count": timeline.get("fail_intervals_count", 0),
        "warn_intervals_count": timeline.get("warn_intervals_count", 0),
        "timeline_status": timeline.get("status", ""),
        "sync_status": sync.get("status", ""),
        "timeline_issues": timeline.get("issues", []),
        "sync_issues": sync.get("issues", []),
    }


def run_check_internal(drive_service, folder_url: str) -> dict:
    tmp_dir = None
    try:
        folder_id = extract_folder_id(folder_url)
        logging.info(f"[check] folder_id={folder_id}")

        files = list_files_in_folder(drive_service, folder_id)
        csv_files = [f for f in files if f["name"].lower().endswith(".csv")]
        mp4_files = [f for f in files if f["name"].lower().endswith(".mp4")]
        logging.info(f"[check] files found: {[f['name'] for f in files]}")

        if len(csv_files) != 1 or len(mp4_files) != 1:
            reason = f"Expected 1 CSV and 1 MP4, found {len(csv_files)} CSV and {len(mp4_files)} MP4"
            logging.warning(f"[check] FAIL — {reason}")
            return {"status": "FAIL", "reason": reason, "video_duration_s": "", "upload_date": ""}

        with _disk_semaphore:
            tmp_dir = tempfile.mkdtemp(prefix="qc_")
            try:
                csv_path = os.path.join(tmp_dir, csv_files[0]["name"])
                logging.info(f"[check] Downloading {csv_files[0]['name']}...")
                download_file(drive_service, csv_files[0]["id"], csv_path)

                csv_report = run_csv_only(csv_path)
                if csv_report["status"] == "FAIL":
                    logging.info(f"[check] CSV failed — skipping MP4 download")
                    report = csv_report
                else:
                    mp4_path = os.path.join(tmp_dir, mp4_files[0]["name"])
                    logging.info(f"[check] Downloading {mp4_files[0]['name']}...")
                    download_file(drive_service, mp4_files[0]["id"], mp4_path)
                    logging.info(f"[check] Running QC...")
                    report = run_qc(csv_path, mp4_path)
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                tmp_dir = None

        result = build_response(report, mp4_files[0].get("createdTime", ""))
        logging.info(f"[check] Result: status={result['status']} reason={result['reason']!r}")
        return result

    except Exception as e:
        logging.exception(f"[check] Error for {folder_url}")
        return {"status": "ERROR", "reason": str(e), "video_duration_s": "", "upload_date": ""}

    finally:
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _process_row(sheet_name: str, i: int, row: list, folder_index: dict, recheck_all: bool = False):
    session_id = cell_value(row, COL_SESSION_ID)
    if not session_id:
        return None, None, None

    if not recheck_all and cell_value(row, COL_STATUS):
        return None, "skipped", None

    link = cell_value(row, COL_LINK)
    link_update = None
    stat_key = "checked"

    if not link:
        folder_url = folder_index.get(session_id)
        if not folder_url:
            logging.warning(f"[row {i}] session={session_id!r} — folder not found in index")
            return None, "not_found", None
        link = folder_url
        link_update = {"range": make_range(sheet_name, i, COL_LINK), "values": [[link]]}
        stat_key = "filled_and_checked"

    logging.info(f"[row {i}] START session={session_id!r}")
    qc = run_check_internal(_get_thread_drive_service(), link)
    checked_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    qc_status = qc.get("status", "ERROR")
    logging.info(f"[row {i}] DONE  session={session_id!r} status={qc_status} reason={qc.get('reason', '')!r}")

    row_updates = []
    if link_update:
        row_updates.append(link_update)
    row_updates.extend([
        {"range": make_range(sheet_name, i, COL_STATUS),     "values": [[qc_status]]},
        {"range": make_range(sheet_name, i, COL_REASON),      "values": [[qc.get("reason", "")]]},
        {"range": make_range(sheet_name, i, COL_CHECKED_AT),  "values": [[checked_at]]},
        {"range": make_range(sheet_name, i, COL_VIDEO_DUR),   "values": [[qc.get("video_duration_s", "")]]},
        {"range": make_range(sheet_name, i, COL_UPLOAD_DATE), "values": [[qc.get("upload_date", "")]]},
    ])
    return row_updates, stat_key, qc_status


def process_batch_sheet(sheets_service, sheet_name: str, folder_index: dict, max_workers: int = 7, recheck_all: bool = False) -> dict:
    # The Google API client/httplib2 transport is not thread-safe enough to share
    # across the top-level batch threads in Cloud Run jobs. Use a thread-local
    # Sheets client for per-sheet reads/writes.
    rows = read_sheet(_get_thread_sheets_service(), sheet_name)
    if len(rows) <= 1:
        return {"skipped": 0, "filled": 0, "checked": 0, "not_found": 0}

    stats = {"skipped": 0, "filled": 0, "checked": 0, "not_found": 0, "qc_error": 0, "write_error": 0}
    lock = threading.Lock()

    pending = [
        (i, row)
        for i, row in enumerate(rows[1:], start=2)
        if cell_value(row, COL_SESSION_ID)
    ]

    if not recheck_all:
        for _, row in pending:
            if cell_value(row, COL_STATUS):
                stats["skipped"] += 1

    work_items = [(i, row) for i, row in pending if recheck_all or not cell_value(row, COL_STATUS)]

    def process(item):
        i, row = item
        return _process_row(sheet_name, i, row, folder_index, recheck_all=recheck_all)

    total = len(work_items)
    logging.info(f"[{sheet_name}] Processing {total} rows with {max_workers} workers (skipped={stats['skipped']})")

    FLUSH_EVERY = 10
    pending_writes = []
    rows_pending = 0
    completed = 0

    def _flush():
        nonlocal rows_pending
        if pending_writes:
            try:
                batch_write(_get_thread_sheets_service(), pending_writes)
                pending_writes.clear()
            except Exception:
                logging.exception(f"[{sheet_name}] Failed to write batch to sheet")
                stats["write_error"] += 1
        rows_pending = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process, item): item for item in work_items}
        for future in as_completed(futures):
            try:
                row_updates, stat_key, qc_status = future.result()
            except Exception:
                logging.exception(f"[{sheet_name}] Unexpected error in worker")
                with lock:
                    completed += 1
                    stats["qc_error"] += 1
                continue
            with lock:
                completed += 1
                if stat_key == "not_found":
                    stats["not_found"] += 1
                elif stat_key in ("checked", "filled_and_checked"):
                    if qc_status == "ERROR":
                        stats["qc_error"] += 1
                    else:
                        stats["checked"] += 1
                    if stat_key == "filled_and_checked":
                        stats["filled"] += 1
                    if row_updates:
                        pending_writes.extend(row_updates)
                        rows_pending += 1
                        if rows_pending >= FLUSH_EVERY:
                            _flush()
                logging.info(f"[{sheet_name}] Progress {completed}/{total} — stats so far: {stats}")

    with lock:
        _flush()

    logging.info(f"[{sheet_name}] Finished. Final stats: {stats}")
    return stats
