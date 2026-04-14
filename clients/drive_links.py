import re
from urllib.parse import parse_qs, unquote, urlparse


_FOLDER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,}$")
_QUERY_ID_PATH_TAILS = {"open", "folderview", "embeddedfolderview"}


def _clean_link(link: str) -> str:
    raw = str(link or "").strip()
    if raw.startswith("<") and raw.endswith(">"):
        raw = raw[1:-1].strip()
    return raw


def _is_folder_id(value: str) -> bool:
    return bool(_FOLDER_ID_RE.fullmatch(str(value or "").strip()))


def _is_drive_host(hostname: str) -> bool:
    host = str(hostname or "").lower().strip(".")
    return host == "drive.google.com" or host.endswith(".drive.google.com")


def _extract_folder_id_from_path(path: str) -> str | None:
    segments = [segment for segment in unquote(path or "").split("/") if segment]
    for index, segment in enumerate(segments[:-1]):
        if segment == "folders" and _is_folder_id(segments[index + 1]):
            return segments[index + 1]
    return None


def _path_supports_query_id(path: str) -> bool:
    segments = [segment for segment in unquote(path or "").split("/") if segment]
    return bool(segments) and segments[-1] in _QUERY_ID_PATH_TAILS


def extract_folder_id(folder_link: str) -> str:
    raw = _clean_link(folder_link)
    if not raw:
        raise ValueError("Invalid Google Drive folder link")

    if _is_folder_id(raw):
        return raw

    parsed = urlparse(raw)
    if not (_is_drive_host(parsed.hostname) and parsed.scheme in {"http", "https"}):
        raise ValueError("Invalid Google Drive folder link")

    folder_id = _extract_folder_id_from_path(parsed.path)
    if folder_id:
        return folder_id

    if _path_supports_query_id(parsed.path):
        folder_ids = parse_qs(parsed.query).get("id", [])
        if folder_ids and _is_folder_id(folder_ids[0]):
            return folder_ids[0]

    raise ValueError("Invalid Google Drive folder link")


def is_supported_drive_folder_link(folder_link: str) -> bool:
    try:
        extract_folder_id(folder_link)
        return True
    except ValueError:
        return False
