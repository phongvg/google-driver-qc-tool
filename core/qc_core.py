import json

from core.utils import combine_status, to_builtin
from validators.schema import validate_schema
from validators.timeline import validate_timeline
from validators.camera_matrix import validate_camera_matrix
from validators.fov import validate_fov
from validators.input_validator import validate_input
from validators.video import validate_video
from validators.sync import validate_sync
from validators.fps_sync import validate_fps_sync

_SKIPPED = {"status": "PASS", "skipped": True, "issues": []}


def _run_csv_validators(df):
    schema = validate_schema(df)
    if schema["status"] == "FAIL":
        return schema, _SKIPPED, _SKIPPED, _SKIPPED, _SKIPPED
    return (
        schema,
        validate_timeline(df),
        validate_camera_matrix(df),
        validate_fov(df),
        validate_input(df),
    )


def _build_report(csv_path, mp4_path, schema, timeline, matrix, fov, input_r, video, sync, fps_sync):
    raw_status = combine_status(
        schema["status"], timeline["status"], matrix["status"],
        fov["status"], input_r["status"], video["status"],
        sync["status"], fps_sync["status"],
    )
    had_warnings = raw_status == "WARN"
    return to_builtin({
        "status": "PASS" if had_warnings else raw_status,
        "had_warnings": had_warnings,
        "files": {"csv": csv_path, "mp4": mp4_path},
        "checks": {
            "schema_validation": schema,
            "timeline_validation": timeline,
            "camera_matrix_validation": matrix,
            "fov_validation": fov,
            "input_validation": input_r,
            "video_validation": video,
            "sync_validation": sync,
            "fps_sync_validation": fps_sync,
        },
    })


def summarize_issues(report: dict) -> str:
    labels = []
    checks = report.get("checks", {})
    mapping = {
        "schema_validation": "schema",
        "timeline_validation": "timeline",
        "camera_matrix_validation": "matrix",
        "fov_validation": "fov",
        "input_validation": "input",
        "video_validation": "video",
        "sync_validation": "sync",
        "fps_sync_validation": "fps_sync",
    }
    for key, short_name in mapping.items():
        issues = checks.get(key, {}).get("issues", [])
        if issues:
            unique_issues = list(dict.fromkeys(issues))
            labels.append(f"{short_name}: " + " | ".join(unique_issues[:2]))
    return " ; ".join(labels[:4])


def run_csv_only(csv_path: str) -> dict:
    import pandas as pd
    df = pd.read_csv(csv_path)
    schema, timeline, matrix, fov, input_r = _run_csv_validators(df)
    return _build_report(csv_path, None, schema, timeline, matrix, fov, input_r, _SKIPPED, _SKIPPED, _SKIPPED)


def run_qc(csv_path: str, mp4_path: str, output_json: str = None) -> dict:
    import pandas as pd
    df = pd.read_csv(csv_path)
    schema, timeline, matrix, fov, input_r = _run_csv_validators(df)

    video = validate_video(mp4_path)
    if schema["status"] == "FAIL":
        sync = _SKIPPED
        fps_sync = _SKIPPED
    else:
        sync = validate_sync(df, video)
        fps_sync = validate_fps_sync(video.get("fps"), timeline.get("delta_ms_mean"))

    report = _build_report(csv_path, mp4_path, schema, timeline, matrix, fov, input_r, video, sync, fps_sync)

    if output_json:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    return report
