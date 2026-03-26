import os
import re
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from google.cloud import storage
from clients import get_services, get_all_batch_sheet_names
from services.qc_service import process_batch_sheet

BUCKET_NAME = os.environ.get("GCS_BUCKET", "tbrain-qc-cache")
INDEX_BLOB = "folder_index.json"


def load_folder_index() -> dict:
    try:
        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(INDEX_BLOB)
        if not blob.exists():
            raise FileNotFoundError(
                f"folder_index.json not found in GCS bucket={BUCKET_NAME}. Run the index job first."
            )
        raw = json.loads(blob.download_as_text())
        if "entries" in raw:
            index = {name: e["folder_url"] for name, e in raw["entries"].items()}
            logging.info(f"Loaded folder index from GCS: {len(index)} folders (v{raw.get('version', '?')})")
        else:
            index = raw
            logging.info(f"Loaded folder index from GCS: {len(index)} folders (legacy)")
        return index
    except FileNotFoundError:
        raise
    except Exception as e:
        logging.error(f"Failed to load folder index from GCS bucket={BUCKET_NAME}: {e}")
        raise


def main():
    batch_numbers_env = os.environ.get("BATCH_NUMBERS", "")
    recheck_all = os.environ.get("RECHECK_ALL", "").strip().lower() == "all"

    batch_numbers = None
    if batch_numbers_env:
        nums = []
        for part in batch_numbers_env.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                nums.extend(range(int(a), int(b) + 1))
            elif part.isdigit():
                nums.append(int(part))
        batch_numbers = nums or None

    _, sheets_service = get_services()

    batch_sheets = get_all_batch_sheet_names(sheets_service)
    if batch_numbers:
        batch_sheets = [
            s for s in batch_sheets
            if int(re.search(r"\d+", s).group()) in batch_numbers
        ]

    if not batch_sheets:
        logging.error("No matching batch sheets found")
        return

    logging.info(f"Batches: {batch_sheets}")
    folder_index = load_folder_index()

    def run_batch(sheet_name):
        logging.info(f"Processing {sheet_name}...")
        stats = process_batch_sheet(sheets_service, sheet_name, folder_index, recheck_all=recheck_all)
        logging.info(f"{sheet_name}: {stats}")
        return sheet_name, stats

    sorted_sheets = sorted(batch_sheets, key=lambda s: int(re.search(r"\d+", s).group()))
    all_results = {}
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(run_batch, s): s for s in sorted_sheets}
        for future in as_completed(futures):
            sheet_name, stats = future.result()
            all_results[sheet_name] = stats

    elapsed = int(time.time() - start_time)
    keys = ["checked", "filled", "skipped", "not_found", "qc_error", "write_error"]
    total = {k: sum(r.get(k, 0) for r in all_results.values()) for k in keys}

    logging.info("=" * 60)
    logging.info(f"JOB SUMMARY — {len(all_results)} batches in {elapsed//60}m{elapsed%60}s")
    logging.info(f"  checked     : {total['checked']}")
    logging.info(f"  filled      : {total['filled']}")
    logging.info(f"  skipped     : {total['skipped']}")
    logging.info(f"  not_found   : {total['not_found']}")
    logging.info(f"  qc_error    : {total['qc_error']}")
    logging.info(f"  write_error : {total['write_error']}")
    logging.info("  --- per batch ---")
    for sheet_name in sorted(all_results, key=lambda s: int(re.search(r"\d+", s).group())):
        r = all_results[sheet_name]
        err = r.get("qc_error", 0) + r.get("write_error", 0)
        logging.info(f"  {sheet_name}: checked={r.get('checked',0)} filled={r.get('filled',0)} skipped={r.get('skipped',0)} not_found={r.get('not_found',0)} error={err}")
    logging.info("=" * 60)
