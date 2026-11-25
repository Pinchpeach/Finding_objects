#!/usr/bin/env python3
"""Gaia DR4 draft data model -> table / column names, and the DR3 columns this project reads (2.60.6).

The ESA draft data model of Gaia DR4 (pre-released 2026-06-26; ``Gaia DR4: preliminary catalogue data model``, 1,231
pages, created 2026-05-20) is a PDF.  This script reads its text (``pdftotext -layout``), lists the columns of every table
and compares them with what ``Get_data/gaia_dr3.py`` requests, so the project knows *before* the release which
columns have an obvious DR4 home and which are gone.  Documentation only: no DR4 data were read.

    curl -LO https://anonftp.cosmos.esa.int/pub/GAIA_PUBLIC_DATA/Gaia_DR4/dr4-prerelease/gaia-dr4-prerelease-draft-data-model_2026-06-26.zip
    unzip gaia-dr4-prerelease-draft-data-model_2026-06-26.zip -d DM
    pdftotext -layout DM/gaia-dr4-prerelease-draft-data-model.pdf DM/dm.txt
    python v2/benchmark/gaia_dr4/parse_dr4_draft.py --text DM/dm.txt --out v2/benchmark/gaia_dr4

writes ``dr4_draft_tables.json`` (table -> columns, in the order of the draft) and ``dr3_columns_vs_dr4_draft.csv``.
The draft is a draft: the archive's own table metadata (``check_gaia_release.py --release DR4``) decides, after the
release, whether a column exists.  The 2026-06-26 draft is kept as the reference for the protocol locked in
``GAIA_DR4_READINESS_2026-11-25.md``.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parents[1]
sys.path.insert(0, str(V2 / "Get_data"))

SECTION = re.compile(r"^(\d+(?:\.\d+)+)\s+([a-z][a-z0-9_]*)\s+\[(TAP|DataLink|[A-Za-z ]+)\]")
COLUMN = re.compile(r"^([a-z][a-z0-9_]*) : ")
# where a DR3 column is expected to live in DR4 when its own table has changed (draft data model, Sect. 1 and 2)
PREFERRED = [
    "gaia_source", "all_source_astrometry", "all_source_photometry", "all_source_rvs", "all_source_flags", "ap_xp", "ap_rvs",
    "ap_class", "ap_chem", "ap_emission", "ap_hot", "vari_summary", "vari_classifier_result",
]  # fmt: skip


def parse(text_path: Path) -> "OrderedDict[str, list[str]]":
    tables: "OrderedDict[str, list[str]]" = OrderedDict()
    cur = None
    for i, line in enumerate(text_path.read_text(encoding="utf-8", errors="replace").splitlines()):
        m = SECTION.match(line)
        if m and i > 400:  # skip the table of contents
            cur = m.group(2)
            tables.setdefault(cur, [])
            continue
        m = COLUMN.match(line)
        if m and cur:
            tables[cur].append(m.group(1))
    return tables


def dr3_requests() -> "OrderedDict[str, list[str]]":
    import gaia_release

    rel = gaia_release.RELEASES["DR3"]
    out: "OrderedDict[str, list[str]]" = OrderedDict()
    for name, prod in rel.products.items():
        out[prod.table] = list(prod.columns)
    return out


def compare(tables: dict, requests: dict) -> list[dict]:
    rows = []
    for dr3_table, cols in requests.items():
        for c in cols:
            where = [t for t, cs in tables.items() if c in cs]
            home = [t for t in PREFERRED if t in where] or where[:3]
            rows.append(
                {
                    "dr3_table": dr3_table,
                    "column": c,
                    "dr4_tables_with_same_name": " ".join(home),
                    "in_draft": "yes" if where else "no",
                    "same_table_name_as_dr3": "yes" if dr3_table in where else "no",
                }
            )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--text", type=Path, required=True, help="pdftotext -layout output of the draft data model")
    ap.add_argument("--out", type=Path, default=HERE)
    a = ap.parse_args()
    tables = parse(a.text)
    a.out.mkdir(parents=True, exist_ok=True)
    body = ",\n".join(f"{json.dumps(t)}: {json.dumps(cols)}" for t, cols in tables.items())  # one table per line
    (a.out / "dr4_draft_tables.json").write_text("{\n" + body + "\n}\n", encoding="utf-8")
    rows = compare(tables, dr3_requests())
    with open(a.out / "dr3_columns_vs_dr4_draft.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    missing = [r for r in rows if r["in_draft"] == "no"]
    print(
        f"{len(tables)} tables, {sum(map(len, tables.values()))} columns; {len(rows)} DR3 columns requested, {len(missing)} not in the draft"
    )
    for r in missing:
        print("  missing:", r["dr3_table"], r["column"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
