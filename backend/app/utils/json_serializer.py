from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import math
from uuid import UUID

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency guard
    np = None

try:
    import pandas as pd
except Exception:  # pragma: no cover - optional dependency guard
    pd = None


def make_json_serializable(obj):
    """Return a deep JSON-safe copy of *obj* without mutating the original."""
    if obj is None:
        return None

    if pd is not None and obj is pd.NaT:
        return None

    if isinstance(obj, dict):
        return {str(key): make_json_serializable(value) for key, value in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]

    if isinstance(obj, Enum):
        return make_json_serializable(obj.value)

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, Decimal):
        return float(obj)

    if isinstance(obj, UUID):
        return str(obj)

    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")

    if np is not None:
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            value = float(obj)
            return None if math.isnan(value) else value
        if isinstance(obj, np.ndarray):
            return [make_json_serializable(item) for item in obj.tolist()]

    if isinstance(obj, float):
        return None if math.isnan(obj) else obj

    if pd is not None:
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        if pd.isna(obj):
            return None

    return obj
