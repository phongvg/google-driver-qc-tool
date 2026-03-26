import pandas as pd
from validators._config import CONFIG


def validate_sync(df: pd.DataFrame, video_result: dict) -> dict:
    result = {
        "status": "PASS",
        "csv_last_timestamp_ms": None,
        "video_duration_ms": None,
        "delta_ms": None,
        "issues": [],
    }

    if video_result["status"] == "FAIL" or not video_result.get("duration_sec"):
        result["status"] = "FAIL"
        root_video_issues = video_result.get("issues", [])
        if root_video_issues:
            result["issues"].append(
                "Skip sync check because video failed: " + " | ".join(root_video_issues)
            )
        else:
            result["issues"].append("Skip sync check because video metadata is invalid")
        return result

    ts = pd.to_numeric(df["Timestamp_ms"], errors="coerce")
    if ts.isna().any():
        result["status"] = "FAIL"
        result["issues"].append("Cannot validate sync because Timestamp_ms is invalid")
        return result

    csv_last_ts = float(ts.iloc[-1])
    video_duration_ms = float(video_result["duration_sec"]) * 1000.0
    delta_ms = abs(video_duration_ms - csv_last_ts)

    result["csv_last_timestamp_ms"] = csv_last_ts
    result["video_duration_ms"] = video_duration_ms
    result["delta_ms"] = delta_ms

    if delta_ms > CONFIG["sync_fail_ms"]:
        result["status"] = "FAIL"
        result["issues"].append(f"Sync drift too large: {delta_ms:.2f} ms > {CONFIG['sync_fail_ms']} ms")
    elif delta_ms > CONFIG["sync_warn_ms"]:
        result["status"] = "WARN"
        result["issues"].append(f"Sync drift warning: {delta_ms:.2f} ms > {CONFIG['sync_warn_ms']} ms")

    return result
