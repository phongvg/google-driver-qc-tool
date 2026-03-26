import pandas as pd
from validators._config import CONFIG, REQUIRED_COLUMNS, MATRIX_COLUMNS
from core.utils import combine_status


def validate_schema(df: pd.DataFrame) -> dict:
    all_required = REQUIRED_COLUMNS + MATRIX_COLUMNS
    missing_columns = [col for col in all_required if col not in df.columns]

    result = {
        "status": "PASS",
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "missing_columns": missing_columns,
        "null_counts": {},
        "invalid_numeric_columns": {},
        "issues": [],
    }

    if len(df) == 0:
        result["status"] = "FAIL"
        result["issues"].append("CSV is empty")
        return result

    if len(df) < CONFIG["min_rows"]:
        result["status"] = combine_status(result["status"], "WARN")
        result["issues"].append(f"CSV has very few rows: {len(df)}")

    if missing_columns:
        result["status"] = "FAIL"
        result["issues"].append("Missing required columns")
        return result

    null_counts = {col: int(df[col].isna().sum()) for col in all_required if df[col].isna().sum() > 0}
    if null_counts:
        result["status"] = "FAIL"
        result["null_counts"] = null_counts
        result["issues"].append("Null values found in required columns")

    numeric_cols = ["Frame_ID", "Timestamp_ms", "FOV_Deg", "Mouse_Delta_X", "Mouse_Delta_Y"] + MATRIX_COLUMNS
    invalid_numeric = {
        col: int(pd.to_numeric(df[col], errors="coerce").isna().sum())
        for col in numeric_cols
        if pd.to_numeric(df[col], errors="coerce").isna().sum() > 0
    }
    if invalid_numeric:
        result["status"] = "FAIL"
        result["invalid_numeric_columns"] = invalid_numeric
        result["issues"].append("Some numeric columns contain non-numeric values")

    return result
