import os
import logging

from services.index_service import build_and_save_index

BUCKET_NAME = os.environ.get("GCS_BUCKET", "tbrain-qc-cache")


def main():
    date_folders_env = os.environ.get("DATE_FOLDERS", "")
    date_folders = [x.strip() for x in date_folders_env.split(",") if x.strip()] or None

    build_and_save_index(BUCKET_NAME, date_folders)


if __name__ == "__main__":
    main()
