# utils.py - shared helpers and constants for the Audio QA Checker

import json
import math
from typing import Any

import numpy as np

VERSION = "0.2.0"


def fmt(v: Any) -> str:
    """Format a single value for tables.

    Returns "NA" for missing or non-finite values, otherwise a string
    with two decimal places.
    """
    if v is None:
        return "NA"
    if isinstance(v, float) and not math.isfinite(v):
        return "NA"
    return f"{v:.2f}"


class NpEncoder(json.JSONEncoder):
    """Small JSON encoder that understands basic numpy scalar types."""

    def default(self, o: Any):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        return super().default(o)


def json_dump(obj: Any) -> str:
    """Return a pretty-printed JSON string, handling numpy types via NpEncoder."""
    return json.dumps(obj, ensure_ascii=False, indent=2, cls=NpEncoder)