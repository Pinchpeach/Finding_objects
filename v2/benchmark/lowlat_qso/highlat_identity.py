#!/usr/bin/env python3
"""The low-latitude switches change nothing at |b| >= 20 deg: the same raw files classified with and without them (2.61.3).

    python highlat_identity.py --raw RAW_DIR [RAW_DIR ...] --out DIR [--switches surveys3,pm,wise_second,wise_footprint]

``RAW_DIR`` is a folder of collected raw files with its ``search.json`` (ra, dec, radius_arcmin).  Each is classified twice offline
(``pipeline.py --raw-dir``, same code, same hash seed, cache off): ``V2_LOWLAT_QSO`` empty and ``V2_LOWLAT_QSO=<switches>``.  One
row per raw folder: objects, objects below ``V2_LOWLAT_QSO_ABSB`` (where a switch may act), QSO labels without / with the switches,
and the number of objects whose ``primary_class`` / ``classification_status`` / ``classification_basis`` differs and the largest
change of ``p_star``, ``p_galaxy``, ``p_qso``.  At high latitude every difference column must be 0; at low latitude they show what
the switches do.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PIPE = Path(__file__).resolve().parents[2] / "pipeline.py"
LABELS = ("primary_class", "classification_status", "classification_basis")
PROBS = ("p_star", "p_galaxy", "p_qso")


def classify(raw: Path, work: Path, switches: str) -> pd.DataFrame:
    s = json.loads((raw / "search.json").read_text())
    env = dict(os.environ, PYTHONHASHSEED="0", V2_CACHE="0", V2_LOWLAT_QSO=switches)
    work.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(PIPE), "--raw-dir", str(raw), "--ra", str(s["ra"]), "--dec", str(s["dec"]), "--radius", str(s["radius_arcmin"]), "--work", str(work)]
    subprocess.run(cmd, env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return pd.read_csv(work / "classified_objects.csv", low_memory=False).set_index("object_id")


def _s(x: pd.Series) -> pd.Series:
    return x.fillna("").astype(str)


def compare(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    common = a.index.intersection(b.index)
    out = dict(objects_without=len(a), objects_with=len(b), objects_common=len(common))
    for c in LABELS:
        out[f"{c}_differs"] = int((_s(a.loc[common, c]) != _s(b.loc[common, c])).sum())
    for c in PROBS:
        d = (pd.to_numeric(a.loc[common, c], errors="coerce") - pd.to_numeric(b.loc[common, c], errors="coerce")).abs()
        out[f"{c}_max_abs_change"] = float(np.nanmax(d.to_numpy())) if len(d) and d.notna().any() else 0.0
    out["qso_labels_without"] = int((a.primary_class == "QSO").sum())
    out["qso_labels_with"] = int((b.primary_class == "QSO").sum())
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--switches", default="surveys3,pm,wise_second,wise_footprint")
    ap.add_argument("--keep", action="store_true", help="keep the classified tables (large)")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(PIPE.parent / "Preprocess"))
    import importlib.util

    spec = importlib.util.spec_from_file_location("lowlat_qso_hi", PIPE.parent / "Preprocess" / "lowlat_qso.py")
    LL = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(LL)
    rows = []
    for raw in a.raw:
        name = raw.parent.parent.name if raw.name.startswith("ra") and raw.parent.name == "raw" else raw.name
        w0, w1 = a.out / "work" / name / "off", a.out / "work" / name / "on"
        off, on = classify(raw, w0, ""), classify(raw, w1, a.switches)
        r = dict(field=name, switches=a.switches, **compare(off, on))
        ra, dec = pd.to_numeric(off.get("ra"), errors="coerce"), pd.to_numeric(off.get("dec"), errors="coerce")
        b = LL.galactic_latitude(ra.to_numpy(float), dec.to_numpy(float))
        r["objects_below_limit"] = int((np.abs(b) < LL.max_abs_b()).sum())
        r["median_abs_b"] = round(float(np.nanmedian(np.abs(b))), 1) if len(b) else np.nan
        rows.append(r)
        print(r, flush=True)
        if not a.keep:
            subprocess.run(["rm", "-rf", str(a.out / "work" / name)], check=True)
    d = pd.DataFrame(rows)
    d.to_csv(a.out / "highlat_identity.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(d.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
