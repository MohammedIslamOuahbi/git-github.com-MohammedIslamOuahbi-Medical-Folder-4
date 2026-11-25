from __future__ import annotations

from collections import defaultdict


def detect_duplicates(rows: list[dict]) -> list[int]:
    seen: dict[tuple, list[int]] = defaultdict(list)
    duplicate_indexes: list[int] = []
    for index, row in enumerate(rows, start=1):
        key = (
            row.get("employee_number"),
            row.get("national_id"),
            row.get("first_name"),
            row.get("last_name"),
            row.get("birth_date"),
        )
        seen[key].append(index)
    for indexes in seen.values():
        if len(indexes) > 1:
            duplicate_indexes.extend(indexes)
    return sorted(set(duplicate_indexes))
