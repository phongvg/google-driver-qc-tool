import re
import os
import logging
from flask import Flask, jsonify, request

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from clients import get_drive_service, get_services, build_folder_index_rich, load_folder_index_from_gcs, get_all_batch_sheet_names
from services.qc_service import run_check_internal, process_batch_sheet

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/check")
def check():
    payload = request.get_json(silent=True) or {}
    folder_url = str(payload.get("folderUrl", "")).strip()

    if not folder_url:
        return jsonify({"status": "ERROR", "reason": "Missing folderUrl"}), 400

    drive_service = get_drive_service()
    result = run_check_internal(drive_service, folder_url)
    status_code = 500 if result.get("status") == "ERROR" else 200
    return jsonify(result), status_code


@app.post("/auto-check")
def auto_check():
    payload = request.get_json(silent=True) or {}
    batch_numbers = payload.get("batches")
    date_folders = payload.get("dateFolders")
    recheck_all = str(payload.get("config", "")).strip().lower() == "all"

    try:
        drive_service, sheets_service = get_services()

        batch_sheets = get_all_batch_sheet_names(sheets_service)
        if batch_numbers:
            batch_sheets = [
                s for s in batch_sheets
                if int(re.search(r"\d+", s).group()) in batch_numbers
            ]

        if not batch_sheets:
            return jsonify({"status": "ERROR", "reason": "No matching batch sheets found"}), 400

        logging.info(f"[auto-check] Batches: {batch_sheets}")
        gcs_bucket = os.environ.get("GCS_BUCKET", "")
        if gcs_bucket:
            folder_index = load_folder_index_from_gcs(gcs_bucket)
        else:
            logging.info(f"[auto-check] Building folder index (dateFolders={date_folders})...")
            rich = build_folder_index_rich(drive_service, date_folders)
            folder_index = {name: e["folder_url"] for name, e in rich.items()}
            logging.info(f"[auto-check] Folder index built: {len(folder_index)} folders")

        results = {}
        for sheet_name in sorted(batch_sheets, key=lambda s: int(re.search(r"\d+", s).group())):
            logging.info(f"[auto-check] Processing {sheet_name}...")
            stats = process_batch_sheet(sheets_service, sheet_name, folder_index, recheck_all=recheck_all)
            logging.info(f"[auto-check] {sheet_name}: {stats}")
            results[sheet_name] = stats

        return jsonify({"status": "OK", "results": results}), 200

    except Exception as e:
        logging.exception("[auto-check] Unexpected error")
        return jsonify({"status": "ERROR", "reason": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
