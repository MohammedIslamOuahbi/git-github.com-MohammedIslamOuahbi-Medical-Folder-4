from __future__ import annotations

import pandas as pd

from app.utils.json_serializer import make_json_serializable


def read_csv_rows(file_path: str) -> list[dict]:
    dataframe = pd.read_csv(file_path)
    return make_json_serializable(dataframe.to_dict(orient="records"))
