import numpy as np
import pandas as pd
from validators._config import CONFIG, MATRIX_COLUMNS


def validate_camera_matrix(df: pd.DataFrame) -> dict:
    result = {"status": "PASS", "nan_count": 0, "inf_count": 0, "last_row_violations": 0, "issues": []}

    matrix_df = df[MATRIX_COLUMNS].apply(pd.to_numeric, errors="coerce")
    nan_count = int(matrix_df.isna().sum().sum())
    inf_count = int(np.isinf(matrix_df.to_numpy(dtype=float)).sum())

    result["nan_count"] = nan_count
    result["inf_count"] = inf_count

    if nan_count > 0:
        result["status"] = "FAIL"
        result["issues"].append("Camera matrix contains NaN")
    if inf_count > 0:
        result["status"] = "FAIL"
        result["issues"].append("Camera matrix contains Inf")

    tol = CONFIG["matrix_last_row_tol"]
    m30 = pd.to_numeric(df["C2W_M30"], errors="coerce")
    m31 = pd.to_numeric(df["C2W_M31"], errors="coerce")
    m32 = pd.to_numeric(df["C2W_M32"], errors="coerce")
    m33 = pd.to_numeric(df["C2W_M33"], errors="coerce")

    violations = int(
        ((m30.abs() > tol) | (m31.abs() > tol) | (m32.abs() > tol) | ((m33 - 1.0).abs() > tol)).sum()
    )
    result["last_row_violations"] = violations
    if violations > 0:
        result["status"] = "FAIL"
        result["issues"].append("Camera matrix last row is not close to [0,0,0,1]")

    return result
