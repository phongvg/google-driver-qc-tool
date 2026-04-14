import os
import logging
import time

from config import SHEET_NAME
from clients import get_services
from services.qc_service import process_batch_sheet


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    recheck_all = os.environ.get("RECHECK_ALL", "").strip().lower() == "all"
    recheck_fail = os.environ.get("RECHECK_FAIL", "").strip().lower() == "fail"

    _, sheets_service = get_services()
    sheet_name = SHEET_NAME
    start_time = time.time()
    logging.info(f"Processing sheet: {sheet_name}")
    stats = process_batch_sheet(
        sheets_service,
        sheet_name,
        recheck_all=recheck_all,
        recheck_fail=recheck_fail,
    )

    elapsed = int(time.time() - start_time)

    logging.info("=" * 60)
    logging.info(f"JOB SUMMARY — 1 sheet in {elapsed//60}m{elapsed%60}s")
    logging.info(f"  sheet       : {sheet_name}")
    logging.info(f"  checked     : {stats.get('checked', 0)}")
    logging.info(f"  skipped     : {stats.get('skipped', 0)}")
    logging.info(f"  no_link     : {stats.get('no_link', 0)}")
    logging.info(f"  qc_error    : {stats.get('qc_error', 0)}")
    logging.info(f"  write_error : {stats.get('write_error', 0)}")
    logging.info("=" * 60)


if __name__ == "__main__":
    main()
