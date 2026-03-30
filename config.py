import os

SPREADSHEET_ID  = os.environ.get("SPREADSHEET_ID", "1puWk_DoB-BXVjdbvdSDue9U51-optRQaOmypAXRy8_o")

_default_root_ids = ",".join([
    "1KyJ1jSzA58Adorfv7naOF4_hSWqxJjml",  # A Giang
    "1bnLNOqh-7UAmmheMQmQZkcwbPUCQae18",  # CTV
    "1pZ2RroDfjaQg2YQ27lMhu1yZJ6EuCu8v",  # Tuấn Anh
    "1VvJYUlOEk2kUwfZHfA7PXWnWVzvPOdJA",  # Team Offline
])
ROOT_FOLDER_IDS = [
    fid.strip()
    for fid in os.environ.get("ROOT_FOLDER_IDS", _default_root_ids).split(",")
    if fid.strip()
]

COL_SESSION_ID  = 2
COL_LINK        = 14
COL_STATUS      = 21
COL_REASON      = 22
COL_CHECKED_AT  = 23
COL_VIDEO_DUR   = 24
COL_UPLOAD_DATE = 25
