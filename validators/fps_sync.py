from validators._config import CONFIG


def validate_fps_sync(video_fps: float, delta_ms_mean: float) -> dict:
    result = {"status": "PASS", "video_fps": video_fps, "csv_fps": None, "issues": []}

    if not video_fps or not delta_ms_mean or delta_ms_mean <= 0:
        result["status"] = "FAIL"
        result["issues"].append("Cannot validate FPS sync: missing data")
        return result

    csv_fps = round(1000.0 / delta_ms_mean, 2)
    result["csv_fps"] = csv_fps

    if 30 <= video_fps <= 35:
        csv_min, csv_max = 25, 35
    elif 60 <= video_fps <= 65:
        csv_min, csv_max = 55, 65
    else:
        csv_min = round(video_fps * 0.8, 2)
        csv_max = round(video_fps * 1.2, 2)

    if not (csv_min <= csv_fps <= csv_max):
        result["status"] = "FAIL"
        result["issues"].append(
            f"FPS mismatch: video={video_fps:.1f}, csv={csv_fps:.1f} (expected {csv_min}-{csv_max})"
        )

    return result
