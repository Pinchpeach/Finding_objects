#!/usr/bin/env python3
"""Which stored rows change their position error between V2_POSERR_UNITS=legacy and fixed (2.62.0), row by row.

    python check_units_from_rows.py --roots DIR [DIR ...] --out DIR

Every ``*_ra*.csv`` below the roots (the raw files of the collectors) is read, ``association_model.infer_poserr_arcsec`` is called for every row
in both modes, and the rows whose value differs are counted per catalogue.  The study's prediction 1 is that the only catalogues in the list are
VLASS and NVSS.  Also writes the ratio statistics of the changed rows and the unit evidence for the two (``unit_evidence.csv``: median
e_RA / e_Dec read as arcsec and as seconds of time for NVSS; e_RAJ2000 against e_RAMdeg for VLASS).
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Preprocess"))
import association_model as am  # noqa: E402


def poserr_both(catalog: str, row: dict) -> tuple[float, float]:
    out = []
    for mode in ("legacy", "fixed"):
        am.POSERR_UNITS = mode
        out.append(am.infer_poserr_arcsec(catalog, row))
    am.POSERR_UNITS = "fixed"
    return out[0], out[1]


def scan(roots: list[Path]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    acc: dict[str, dict] = {}
    regions: dict[tuple, dict] = {}  # (root name, region) -> rows whose error changes, by catalogue
    evid = {"nvss": [], "vlass": []}
    for root in roots:
        for f in sorted(root.glob("**/*_ra*.csv")):
            if f.name.startswith(("collection_summary", "galaxy_clusters")):
                continue
            region = f.relative_to(root).parts[0]  # <field> / <region> in every layout of the study
            try:
                df = pd.read_csv(f, low_memory=False)
            except Exception:
                continue
            if df.empty or not {"ra", "dec"}.issubset(df.columns):
                continue
            cat_default = f.stem.split("_ra")[0]
            for r in df.to_dict("records"):
                cat = r.get("catalog")
                cat = cat_default if cat is None or (isinstance(cat, float) and math.isnan(cat)) else str(cat)
                a, b = poserr_both(cat, r)
                s = acc.setdefault(cat, dict(catalog=cat, rows=0, changed=0, legacy=[], fixed=[]))
                s["rows"] += 1
                if not (a == b or (math.isnan(a) and math.isnan(b))):
                    s["changed"] += 1
                    g = regions.setdefault((root.name, region), dict(set=root.name, region=region, vlass=0, nvss=0, other=0))
                    g["vlass" if cat == "VLASS" else "nvss" if cat == "NVSS" else "other"] += 1
                    s["legacy"].append(a)
                    s["fixed"].append(b)
                if cat == "NVSS" and r.get("e_RAJ2000") is not None and r.get("e_DEJ2000") not in (None, 0):
                    evid["nvss"].append((float(r["e_RAJ2000"]), float(r["e_DEJ2000"]), float(r["dec"])))
                if cat == "VLASS" and r.get("e_RAMdeg") is not None:
                    evid["vlass"].append((float(r["e_RAJ2000"]), float(r["e_RAMdeg"])))
    rows = []
    for s in acc.values():
        rows.append(dict(catalog=s["catalog"], rows=s["rows"], changed=s["changed"],
                         median_legacy_arcsec=float(np.median(s["legacy"])) if s["legacy"] else math.nan,
                         median_fixed_arcsec=float(np.median(s["fixed"])) if s["fixed"] else math.nan,
                         median_ratio=float(np.median(np.array(s["fixed"]) / np.maximum(np.array(s["legacy"]), 1e-12))) if s["legacy"] else math.nan))  # fmt: skip
    ev = []
    n = np.array(evid["nvss"], float)
    if len(n):
        ra, de, dec = n[:, 0], n[:, 1], n[:, 2]
        ok = de > 0
        ev.append(dict(evidence="NVSS median e_RA/e_Dec, RA read as arcsec", value=float(np.median(ra[ok] / de[ok])), n=int(ok.sum())))
        ev.append(dict(evidence="NVSS median e_RA*15*cos(dec)/e_Dec, RA read as seconds of time", value=float(np.median(ra[ok] * 15 * np.cos(np.deg2rad(dec[ok])) / de[ok])), n=int(ok.sum())))
    v = np.array(evid["vlass"], float)
    if len(v):
        ev.append(dict(evidence="VLASS e_RAJ2000 identical to e_RAMdeg (share of rows)", value=float(np.mean(np.isclose(v[:, 0], v[:, 1]))), n=len(v)))
        ev.append(dict(evidence="VLASS median e_RAJ2000 x 3600 [arcsec] if degrees", value=float(np.median(v[:, 0]) * 3600), n=len(v)))
    return pd.DataFrame(rows).sort_values(["changed", "rows"], ascending=False), pd.DataFrame(ev), pd.DataFrame(list(regions.values()))


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roots", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    rows, ev, regs = scan(a.roots)
    regs.to_csv(a.out / "regions_changed.csv", index=False)
    rows.to_csv(a.out / "rows_changed.csv", index=False)
    ev.to_csv(a.out / "unit_evidence.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(rows.to_string(index=False))
        print(ev.to_string(index=False))
    changed = set(rows[rows.changed > 0].catalog)
    print("catalogues with changed rows:", sorted(changed))
    print(f"regions with at least one changed row: {len(regs)} (rest are identical by construction)")
    print(regs.groupby('set')[['vlass', 'nvss', 'other']].agg(['count', 'sum']).to_string())
    RI.write_args(a, ('roots',), t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
