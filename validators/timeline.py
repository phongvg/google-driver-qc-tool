import pandas as pd
from validators._config import CONFIG
from core.utils import combine_status


def validate_timeline(df: pd.DataFrame) -> dict:
    result = {
        "status": "PASS",
        "frame_id_monotonic": True,
        "frame_id_sequential": True,
        "timestamp_monotonic": True,
        "negative_timestamps": 0,
        "duplicate_timestamps": 0,
        "duration_ms": None,
        "delta_ms_mean": None,
        "delta_ms_min": None,
        "delta_ms_max": None,
        "warn_intervals_count": 0,
        "fail_intervals_count": 0,
        "warn_intervals_ratio": 0.0,
        "fail_intervals_ratio": 0.0,
        "issues": [],
    }

    frame_id = pd.to_numeric(df["Frame_ID"], errors="coerce")
    ts = pd.to_numeric(df["Timestamp_ms"], errors="coerce")

    if frame_id.isna().any() or ts.isna().any():
        result["status"] = "FAIL"
        result["issues"].append("Frame_ID or Timestamp_ms contains invalid numeric data")
        return result

    frame_diff = frame_id.diff().dropna()
    ts_diff = ts.diff().dropna()

    if (frame_diff <= 0).any():
        result["frame_id_monotonic"] = False
        result["status"] = "FAIL"
        result["issues"].append("Frame_ID is not strictly increasing")

    if not (frame_diff == 1).all():
        result["frame_id_sequential"] = False
        result["status"] = "FAIL"
        result["issues"].append("Frame_ID is not sequential by 1")

    negative_ts = int((ts < 0).sum())
    result["negative_timestamps"] = negative_ts
    if negative_ts > 0:
        result["status"] = "FAIL"
        result["issues"].append("Negative timestamps found")

    if (ts_diff < 0).any():
        result["timestamp_monotonic"] = False
        result["status"] = "FAIL"
        result["issues"].append("Timestamp_ms is not monotonic increasing")

    result["duplicate_timestamps"] = int((ts_diff == 0).sum())

    duration_ms = float(ts.iloc[-1] - ts.iloc[0])
    result["duration_ms"] = duration_ms

    if duration_ms < CONFIG["min_session_duration_ms"]:
        result["status"] = combine_status(result["status"], "FAIL")
        result["issues"].append(f"Session too short: {duration_ms:.2f} ms")

    if len(ts_diff) > 0:
        total_intervals = int(len(ts_diff))
        hard_fail_intervals = int((ts_diff > CONFIG["max_delta_hard_fail_ms"]).sum())
        warn_intervals = int((ts_diff > CONFIG["max_delta_warn_ms"]).sum())
        fail_intervals = int((ts_diff > CONFIG["max_delta_fail_ms"]).sum())

        result.update({
            "delta_ms_mean": float(ts_diff.mean()),
            "delta_ms_min": float(ts_diff.min()),
            "delta_ms_max": float(ts_diff.max()),
            "warn_intervals_count": warn_intervals,
            "fail_intervals_count": fail_intervals,
            "warn_intervals_ratio": warn_intervals / total_intervals,
            "fail_intervals_ratio": fail_intervals / total_intervals,
        })

        if hard_fail_intervals > 0:
            result["status"] = combine_status(result["status"], "FAIL")
            result["issues"].append(f"Frame gap > {CONFIG['max_delta_hard_fail_ms']} ms detected ({hard_fail_intervals} intervals)")
        elif fail_intervals >= 10:
            result["status"] = combine_status(result["status"], "FAIL")
            result["issues"].append(f"Frame gaps found > {CONFIG['max_delta_fail_ms']} ms ({fail_intervals} intervals)")
        elif fail_intervals > 0:
            result["status"] = combine_status(result["status"], "WARN")
            result["issues"].append(f"Warning: frame gaps > {CONFIG['max_delta_fail_ms']} ms ({fail_intervals} intervals)")

    return result
