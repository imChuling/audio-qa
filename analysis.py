# analysis.py - run metrics on a file, apply thresholds, etc.

import os
import math
import yaml
from typing import Dict, Any

from audio_io import read_audio, read_audio_multi
from metrics import (
    peak_dbfs,
    rms_dbfs,
    crest_db,
    r128_loudness_and_lra,
    snr_db,
    true_peak_dbfs,
    per_channel_metrics,
)


def analyze_file(path: str) -> Dict[str, Any]:
    # Main table: mono (downmixed) metrics
    y, sr = read_audio(path)

    pk = peak_dbfs(y)
    rms = rms_dbfs(y)
    crest = crest_db(pk, rms)

    # R128-style loudness metrics
    L_i, L_s, L_m, LRA = r128_loudness_and_lra(y, sr)

    # SNR (hybrid estimator)
    snr = snr_db(y, sr)

    # True Peak (4× oversampling approximation)
    try:
        tp = true_peak_dbfs(y, sr, os_factor=4)
    except Exception:
        tp = None

    # Optional multi-channel analysis
    ch_rows = None
    ch_extra: Dict[str, Any] = {}
    try:
        ymc, _ = read_audio_multi(path)
        if getattr(ymc, "ndim", 1) == 2 and ymc.shape[1] >= 2:
            ch_rows, ch_extra = per_channel_metrics(ymc, sr)
    except Exception:
        pass

    row: Dict[str, Any] = {
        "file": os.path.basename(path),
        "sr": sr,
        "peak_dbfs": pk,
        "true_peak_dbfs": tp,
        "rms_dbfs": rms,
        "crest_db": crest,
        "lufs": L_i,
        "lufs_s": L_s,
        "lufs_m": L_m,
        "lra": LRA,
        "snr_db": snr,
    }
    if ch_rows is not None:
        row["channels"] = ch_rows
    if ch_extra.get("lr_corr") is not None:
        row["lr_corr"] = ch_extra["lr_corr"]
    if ch_extra.get("channel_imbalance_db") is not None:
        row["channel_imbalance_db"] = ch_extra["channel_imbalance_db"]
    row["silent_channels"] = ch_extra.get("silent_channels", [])
    return row


def _analyze_path(path: str) -> Dict[str, Any]:
    # Thin wrapper so ProcessPoolExecutor can pickle and call it
    return analyze_file(path)


def load_thresholds(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def is_near_silence(row: Dict[str, Any]) -> bool:
    # Treat RMS < -80 dBFS or Peak < -60 dBFS as "near silence" (tunable)
    return (row.get("rms_dbfs", 0) < -80.0) or (row.get("peak_dbfs", 0) < -60.0)


def verdict_from_marks(marks: Dict[str, str]) -> str:
    # If any metric FAILs, FAIL; else if any WARN, WARN; otherwise PASS
    if "FAIL" in marks.values():
        return "FAIL"
    if "WARN" in marks.values():
        return "WARN"
    return "PASS"


def judge(val, rule: Dict[str, float]) -> str:
    # NA: do not participate in the verdict
    if val is None or (isinstance(val, float) and not math.isfinite(val)):
        return "NA"

    has_min = "min" in rule
    has_max = "max" in rule

    # PASS band
    if has_min and has_max and (rule["min"] <= val <= rule["max"]):
        return "PASS"
    if has_min and not has_max and (val >= rule["min"]):
        return "PASS"
    if has_max and not has_min and (val <= rule["max"]):
        return "PASS"

    # Optional WARN band: values in warn_min–min or max–warn_max
    warn_min = rule.get("warn_min", None)
    warn_max = rule.get("warn_max", None)
    if has_min and (val < rule["min"]):
        if warn_min is not None and val >= warn_min:
            return "WARN"
        return "FAIL"
    if has_max and (val > rule["max"]):
        if warn_max is not None and val <= warn_max:
            return "WARN"
        return "FAIL"

    # If neither min nor max is configured, default to PASS
    return "PASS"


# Apply the threshold rules to a row of metrics and return per-metric judgements.
def format_marks(row: Dict[str, Any], thresholds: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not thresholds:
        return out
    for key, rule in thresholds.items():
        out[key] = judge(row.get(key), rule)
    return out