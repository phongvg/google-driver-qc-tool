import os
import re
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from clients import get_services, get_all_batch_sheet_names
from services.qc_service import process_batch_sheet


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    batch_numbers_env = os.environ.get("BATCH_NUMBERS", "")
    recheck_all = os.environ.get("RECHECK_ALL", "").strip().lower() == "all"
    recheck_fail = os.environ.get("RECHECK_FAIL", "").strip().lower() == "fail"

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

    def run_batch(sheet_name):
        logging.info(f"Processing {sheet_name}...")
        stats = process_batch_sheet(
            sheets_service,
            sheet_name,
            recheck_all=recheck_all,
            recheck_fail=recheck_fail,
        )
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
    keys = ["checked", "skipped", "no_link", "qc_error", "write_error"]
    total = {k: sum(r.get(k, 0) for r in all_results.values()) for k in keys}

    logging.info("=" * 60)
    logging.info(f"JOB SUMMARY — {len(all_results)} batches in {elapsed//60}m{elapsed%60}s")
    logging.info(f"  checked     : {total['checked']}")
    logging.info(f"  skipped     : {total['skipped']}")
    logging.info(f"  no_link     : {total['no_link']}")
    logging.info(f"  qc_error    : {total['qc_error']}")
    logging.info(f"  write_error : {total['write_error']}")
    logging.info("  --- per batch ---")
    for sheet_name in sorted(all_results, key=lambda s: int(re.search(r"\d+", s).group())):
        r = all_results[sheet_name]
        err = r.get("qc_error", 0) + r.get("write_error", 0)
        logging.info(f"  {sheet_name}: checked={r.get('checked',0)} skipped={r.get('skipped',0)} no_link={r.get('no_link',0)} error={err}")
    logging.info("=" * 60)


if __name__ == "__main__":
    main()
