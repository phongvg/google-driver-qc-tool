import pandas as pd
from validators._config import CONFIG


def validate_input(df: pd.DataFrame) -> dict:
    result = {
        "status": "PASS",
        "mouse_dx_nonzero_count": 0,
        "mouse_dy_nonzero_count": 0,
        "keyboard_nonempty_count": 0,
        "has_activity": False,
        "issues": [],
    }

    dx = pd.to_numeric(df["Mouse_Delta_X"], errors="coerce")
    dy = pd.to_numeric(df["Mouse_Delta_Y"], errors="coerce")
    kb = df["Keyboard_Input"].fillna("").astype(str)

    if dx.isna().any() or dy.isna().any():
        result["status"] = "FAIL"
        result["issues"].append("Mouse delta contains invalid numeric data")
        return result

    kb_clean = kb.str.strip().str.lower()
    kb_nonempty = int(((kb_clean != "") & (kb_clean != "none") & (kb_clean != "0")).sum())
    dx_nonzero = int((dx != 0).sum())
    dy_nonzero = int((dy != 0).sum())

    has_keyboard = kb_nonempty > 0
    has_mouse_dx = dx_nonzero > 0
    has_mouse_dy = dy_nonzero > 0

    result["mouse_dx_nonzero_count"] = dx_nonzero
    result["mouse_dy_nonzero_count"] = dy_nonzero
    result["keyboard_nonempty_count"] = kb_nonempty
    result["has_activity"] = bool(has_keyboard)

    if not has_keyboard and not has_mouse_dx and not has_mouse_dy:
        result["status"] = "FAIL" if CONFIG["require_activity"] else "PASS"
        if CONFIG["require_activity"]:
            result["issues"].append("No keyboard input and no mouse movement")

    return result
