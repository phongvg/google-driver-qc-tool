import numpy as np


def status_rank(status: str) -> int:
    return {"PASS": 0, "WARN": 1, "FAIL": 2}.get(status, 2)


def combine_status(*statuses):
    worst = "PASS"
    for s in statuses:
        if status_rank(s) > status_rank(worst):
            worst = s
    return worst


def to_builtin(obj):
    if isinstance(obj, dict):
        return {k: to_builtin(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_builtin(v) for v in obj]
    if isinstance(obj, tuple):
        return [to_builtin(v) for v in obj]
    if isinstance(obj, set):
        return [to_builtin(v) for v in sorted(obj)]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None


def parse_fraction(frac: str) -> float:
    try:
        if "/" in str(frac):
            a, b = str(frac).split("/")
            return float(a) / float(b) if float(b) != 0 else 0.0
        return float(frac)
    except Exception:
        return 0.0
