#!/usr/bin/env python3
"""Objects with a spectral class QSO that the survey-count switches hold back at low latitude (2.61.5).

    python spectro_held.py --base ROOT_BASE --variants surveys2=ROOT2 surveys3=ROOT3 [surveys2_keep=ROOT4 ...] --out OUT.csv

The roots are compact records of the regions classified WITH the spectroscopic catalogues (``collect_spectra.py``).  An object
counts as spectroscopically classified when its QSO rules include SPC-SDSS-003, SPC-DESI-003 or SPC-LAMOST-003 in the base run.
One row per such object: its surveys, the label in the base and in every variant, and ``lowlat_qso`` (the variants' hold statuses).
The summary line says how many of them each variant leaves QSO / holds back.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("lowlat_qso_spec", HERE.parents[1] / "Preprocess" / "lowlat_qso.py")
LL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LL)
SPEC = re.compile(r"SPC-(?:SDSS|DESI|LAMOST)-003")


def load(root: Path) -> pd.DataFrame:
    parts = []
    for f in sorted(root.glob("*/objects.csv.gz")):
        o = pd.read_csv(f, low_memory=False, usecols=lambda c: c in {"object_id", "ra", "dec", "catalogs", "primary_class", "classification_status",
                                                                       "rules_QSO", "parent_object_id"})  # fmt: skip
        o["region"] = f.parent.name
        parts.append(o)
    return pd.concat(parts, ignore_index=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--variants", nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    b = load(a.base)
    spec = b[b.rules_QSO.fillna("").str.contains(SPEC.pattern, regex=True)].copy()
    spec["n_surveys"] = LL.n_surveys(spec.catalogs)
    spec = spec.rename(columns={"primary_class": "label_base", "classification_status": "status_base"})[
        ["region", "object_id", "ra", "dec", "catalogs", "n_surveys", "label_base", "status_base"]]  # fmt: skip
    for v in a.variants:
        name, root = v.split("=", 1)
        d = load(Path(root))[["region", "object_id", "primary_class", "classification_status"]].rename(
            columns={"primary_class": f"label_{name}", "classification_status": f"status_{name}"})  # fmt: skip
        spec = spec.merge(d, on=["region", "object_id"], how="left")
    spec.to_csv(a.out, index=False)
    print(f"{len(spec)} objects with a spectral class QSO; base labels: {spec.label_base.value_counts().to_dict()}")
    for v in a.variants:
        name = v.split("=", 1)[0]
        held = spec[(spec.label_base == "QSO") & (spec[f"label_{name}"] != "QSO")]
        print(f"{name}: of {int((spec.label_base == 'QSO').sum())} labelled QSO by the base, {len(held)} are not; surveys of those: {held.n_surveys.tolist()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
