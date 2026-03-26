import json
import subprocess

from validators._config import CONFIG
from core.utils import parse_fraction, safe_float


def ffprobe_video(video_path: str) -> dict:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "stream=codec_type,width,height,avg_frame_rate,r_frame_rate",
        "-show_entries", "format=duration",
        "-of", "json",
        video_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def validate_video(video_path: str) -> dict:
    result = {
        "status": "PASS",
        "width": None,
        "height": None,
        "fps": None,
        "duration_sec": None,
        "issues": [],
    }

    try:
        meta = ffprobe_video(video_path)
    except subprocess.CalledProcessError as e:
        result["status"] = "FAIL"
        result["issues"].append(f"ffprobe failed: {e.stderr[:500]}")
        return result
    except Exception as e:
        result["status"] = "FAIL"
        result["issues"].append(f"Cannot read video metadata: {str(e)}")
        return result

    video_streams = [s for s in meta.get("streams", []) if s.get("codec_type") == "video"]
    if not video_streams:
        result["status"] = "FAIL"
        result["issues"].append("No video stream found in MP4")
        return result

    stream = video_streams[0]
    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))
    fps = parse_fraction(stream.get("avg_frame_rate", "0/1"))
    duration_sec = safe_float(meta.get("format", {}).get("duration"))

    result["width"] = width
    result["height"] = height
    result["fps"] = fps
    result["duration_sec"] = duration_sec

    if width < CONFIG["min_width"] or height < CONFIG["min_height"]:
        result["status"] = "FAIL"
        result["issues"].append(
            f"Resolution below threshold: {width}x{height} < {CONFIG['min_width']}x{CONFIG['min_height']}"
        )

    if duration_sec is None or duration_sec <= 0:
        result["status"] = "FAIL"
        result["issues"].append("Invalid video duration")

    return result
