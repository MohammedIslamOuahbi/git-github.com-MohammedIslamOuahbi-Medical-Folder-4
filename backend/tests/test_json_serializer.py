from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

import numpy as np
import pandas as pd

from app.utils.excel_reader import read_excel_rows
from app.utils.json_serializer import make_json_serializable


class SampleEnum(Enum):
    READY = "ready"


def test_make_json_serializable_handles_nested_pandas_numpy_values():
    payload = {
        "timestamp": pd.Timestamp("2025-05-29 08:15:00"),
        "datetime": datetime(2025, 5, 29, 8, 15, 0),
        "date": date(2025, 5, 29),
        "numpy_int": np.int64(42),
        "numpy_float": np.float64(12.5),
        "numpy_bool": np.bool_(True),
        "decimal": Decimal("19.75"),
        "uuid": UUID("12345678-1234-5678-1234-567812345678"),
        "enum": SampleEnum.READY,
        "bytes": b"hello",
        "nan": np.nan,
        "nat": pd.NaT,
        "none": None,
        "tuple": (np.int32(7), pd.Timestamp("2025-06-01")),
        "nested": {
            "list": [
                pd.Timestamp("2025-05-30"),
                np.float64(2.5),
                np.bool_(False),
                {"value": Decimal("3.14")},
            ]
        },
    }

    result = make_json_serializable(payload)

    assert result["timestamp"] == "2025-05-29T08:15:00"
    assert result["datetime"] == "2025-05-29T08:15:00"
    assert result["date"] == "2025-05-29"
    assert result["numpy_int"] == 42
    assert result["numpy_float"] == 12.5
    assert result["numpy_bool"] is True
    assert result["decimal"] == 19.75
    assert result["uuid"] == "12345678-1234-5678-1234-567812345678"
    assert result["enum"] == "ready"
    assert result["bytes"] == "hello"
    assert result["nan"] is None
    assert result["nat"] is None
    assert result["tuple"] == [7, "2025-06-01T00:00:00"]
    assert result["nested"]["list"][0] == "2025-05-30T00:00:00"
    assert result["nested"]["list"][1] == 2.5
    assert result["nested"]["list"][2] is False
    assert result["nested"]["list"][3]["value"] == 3.14
    json.dumps(result)


def test_read_excel_rows_returns_json_safe_records(tmp_path):
    file_path = tmp_path / "import.xlsx"
    dataframe = pd.DataFrame(
        [
            {
                "firstName": "Alice",
                "visitDate": pd.Timestamp("2025-05-29 09:30:00"),
                "birthDate": date(1990, 1, 2),
                "weight": np.int64(70),
                "height": np.float64(172.5),
                "isPeriodic": np.bool_(True),
                "emptyCell": np.nan,
                "emptyDate": pd.NaT,
            }
        ]
    )
    dataframe.to_excel(file_path, index=False)

    rows = read_excel_rows(str(file_path))

    assert len(rows) == 1
    assert rows[0]["firstName"] == "Alice"
    assert rows[0]["visitDate"] == "2025-05-29T09:30:00"
    assert rows[0]["birthDate"] == "1990-01-02T00:00:00"
    assert rows[0]["weight"] == 70
    assert rows[0]["height"] == 172.5
    assert rows[0]["isPeriodic"] is True
    assert rows[0]["emptyCell"] is None
    assert rows[0]["emptyDate"] is None
    json.dumps(rows)
