from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

def save_classification(record: dict, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return output

def build_search_index(records: list[dict]) -> pd.DataFrame:
    rows = []
    for r in records:
        rows.append({
            "object_id": r.get("object_id"),
            "object_type": r.get("object_type"),
            "redshift": r.get("redshift"),
            "line_tags": "|".join(sorted(r.get("line_tags", []))),
            "object_tags": "|".join(sorted(r.get("object_tags", []))),
            "all_tags": "|".join(sorted(set(r.get("line_tags", []) + r.get("object_tags", [])))),
        })
    return pd.DataFrame(rows)
