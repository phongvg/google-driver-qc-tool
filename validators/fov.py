import pandas as pd
from validators._config import CONFIG


def validate_fov(df: pd.DataFrame) -> dict:
    result = {
        "status": "PASS",
        "invalid_fov_deg_rows": 0,
        "invalid_fov_axis_rows": 0,
        "issues": [],
    }

    fov_deg = pd.to_numeric(df["FOV_Deg"], errors="coerce")
    invalid_deg = int(((fov_deg < CONFIG["fov_min"]) | (fov_deg > CONFIG["fov_max"]) | fov_deg.isna()).sum())
    result["invalid_fov_deg_rows"] = invalid_deg

    axis = df["FOV_Axis"].astype(str).str.strip().str.lower()
    invalid_axis = int((~axis.isin(CONFIG["allowed_fov_axis"])).sum())
    result["invalid_fov_axis_rows"] = invalid_axis

    if invalid_deg > 0:
        result["status"] = "FAIL"
        result["issues"].append("Invalid FOV_Deg values found")

    if invalid_axis > 0:
        result["status"] = "FAIL"
        result["issues"].append("Invalid FOV_Axis values found")

    return result
