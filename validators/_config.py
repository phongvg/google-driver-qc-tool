CONFIG = {
    "min_width": 1920,
    "min_height": 1080,
    "min_fps": 30.0,
    "sync_warn_ms": 500,
    "sync_fail_ms": 1000,
    "max_delta_warn_ms": 34,
    "max_delta_fail_ms": 34,
    "max_delta_hard_fail_ms": 60,
    "max_warn_ratio": 0.02,
    "max_fail_ratio": 0.005,
    "min_session_duration_ms": 3000,
    "min_rows": 10,
    "matrix_last_row_tol": 1e-3,
    "fov_min": 1.0,
    "fov_max": 179.0,
    "allowed_fov_axis": ["horizontal", "vertical"],
    "require_activity": False,
}

REQUIRED_COLUMNS = [
    "Frame_ID", "Timestamp_ms", "FOV_Deg", "FOV_Axis",
    "Keyboard_Input", "Mouse_Delta_X", "Mouse_Delta_Y",
]

MATRIX_COLUMNS = [f"C2W_M{i}{j}" for i in range(4) for j in range(4)]
