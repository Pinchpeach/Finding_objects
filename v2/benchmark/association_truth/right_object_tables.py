#!/usr/bin/env python3
"""Markdown tables of the task-"러" recount from ``right_object_recount.py`` (2.62.7).

    python right_object_tables.py --recount DIR > tables.md

Table 1  the modelling switches ``same`` / ``nearest`` / ``same_nearest`` against the default, on the 2.61.8 calibration (fields 1-9) and confirmation (10-26) split and on all 26.
Table 2  how the numbers of the variants that change the ORDER of Stage 1 (``file``, ``position``, ``floored``) and of ``same_nearest`` change with the definition: the old readings
         (``correct``, shifted-control ``shifted_false_pct``) next to the readings of METRICS.md (``right_object``, ``missed``, ``shifted_any_pct``).
Table 3  the 2.60.9 / 2.61.0 report numbers next to the rerun (all 26 fields).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

CATS = ("AllWISE", "GALEX AIS", "2MASS PSC")


def md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if pd.isna(v) else (f"{v:+g}" if isinstance(v, (int, float)) and c.startswith("Δ") else str(v)) for c, v in zip(cols, r)) + " |")
    return "\n".join(out)


def table1(d: pd.DataFrame) -> pd.DataFrame:
    x = d[d.variant.isin(["same", "nearest", "same_nearest"]) & d.split.isin(["cal9", "conf17", "all26"])].copy()
    x["split"] = x.split.map({"cal9": "보정 9", "conf17": "확인 17", "all26": "전체 26"})
    x["relabel"] = x.relabel_share_of_d_correct_pct.map(lambda v: "" if pd.isna(v) else f"{v:.0f} %")
    out = x[["catalog", "split", "variant", "with_expected", "d_correct", "d_alone_identified", "d_right_object", "d_right_object_pp", "d_right_object_ci", "d_missed", "d_false", "d_unidentified", "d_shared", "d_displaced", "d_shifted_any_pct", "relabel"]]
    out.columns = ["목록", "분할", "변형", "짝 있는 행", "Δcorrect", "Δalone_identified", "Δright_object", "Δright_object (pp)", "95 % 구간(영역 부트스트랩)", "Δmissed", "Δfalse", "Δunidentified", "Δshared", "Δdisplaced", "Δ우연 연결률(shifted_any, pp)", "재라벨 몫"]
    out["_c"] = out["목록"].map({c: i for i, c in enumerate(CATS)})
    out["_s"] = out["분할"].map({"보정 9": 0, "확인 17": 1, "전체 26": 2})
    out["_v"] = out["변형"].map({"same": 0, "nearest": 1, "same_nearest": 2})
    return out.sort_values(["_c", "_s", "_v"]).drop(columns=["_c", "_s", "_v"])


def table2(c: pd.DataFrame) -> pd.DataFrame:
    x = c[(c.split == "all26") & c.variant.isin(["base", "file", "position", "floored", "same_nearest"])].copy()
    out = x[["catalog", "variant", "correct", "false_pct_of_matched_known", "shifted_false_pct", "right_object", "right_object_pct", "wrong_object", "unidentified", "missed", "missed_pct", "shared", "displaced", "shifted_any_pct"]]
    out.columns = ["목록", "변형", "correct (옛)", "틀린 연결률 % (옛)", "이동 대조 앵커 정의 % (옛)", "right_object", "right_object %", "wrong_object", "unidentified", "missed (옛, 앵커 의존)", "놓침 %", "shared (조각)", "displaced", "우연 연결률 shifted_any %"]
    out["_c"] = out["목록"].map({k: i for i, k in enumerate(CATS)})
    out["_v"] = out["변형"].map({"base": 0, "file": 1, "position": 2, "floored": 3, "same_nearest": 4})
    return out.sort_values(["_c", "_v"]).drop(columns=["_c", "_v"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recount", type=Path, required=True)
    a = ap.parse_args()
    d = pd.read_csv(a.recount / "recount_delta.csv")
    c = pd.read_csv(a.recount / "recount_counts.csv")
    print("## 표 1. 모호 처리(`same`, `nearest`, `same_nearest`) 대 기본값\n")
    print(md(table1(d)))
    print("\n## 표 2. 정의에 따라 값이 어떻게 바뀌는가 (전체 26개 영역)\n")
    print(md(table2(c)))
    print("\n## 표 3. 2.60.9 / 2.61.0 보고 수치와 재측정 (전체 26개 영역)\n")
    t = c[(c.split == "all26") & c.variant.isin(["file", "position", "base"])][["catalog", "variant", "correct", "false", "false_pct_of_matched_known", "missed", "missed_pct", "shifted_false_pct"]]
    t.columns = ["목록", "변형", "correct", "false", "틀린 연결률 %", "missed", "놓침 %", "이동 대조(옛) %"]
    print(md(t.sort_values(["목록", "변형"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
