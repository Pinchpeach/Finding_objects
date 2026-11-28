#!/usr/bin/env python3
"""The shift of the printed position (``V2_OBJECT_POSITION=best``) on the low-latitude confirmation cones (task "버"; Stage 1 only: the shift is a function of its output).

    python shift_lowlat.py --cones DIR --out OUT.csv

``--cones``  ``DIR/<cone>/raw/*.csv`` (the 140 cones of ``lowlat_qso``, 3'-radius cones: ``lqc1_*`` = 60, ``lqc2_*`` = 40, ``lqc3_*`` = 40).  For every cone Stage 1 is run, ``object_position``
reads its table (the anchor position is ``object_ra`` / ``object_dec``), and the distance between the anchor and the most precise member is counted.  Written: one line per cone (objects,
shares, percentiles, the printed catalogue counts, Galactic latitude of the cone centre), and a last line ``ALL`` with every object of all cones.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
V2 = HERE.parents[1]
sys.path.insert(0, str(V2 / "Preprocess"))
sys.path.insert(0, str(V2 / "benchmark"))
import run_info as RI  # noqa: E402


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def gal_b(ra: float, dec: float) -> float:
    a, d = np.radians(ra), np.radians(dec)
    return float(np.degrees(np.arcsin(-0.867666135683 * np.cos(d) * np.cos(a) - 0.198076389613 * np.cos(d) * np.sin(a) + 0.455983794521 * np.sin(d))))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cones", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    OP = load(V2 / "object_position.py", "v2_object_position_s")
    S1 = load(V2 / "Preprocess" / "01_source_association.py", "v2_stage1_shift")
    rows, allshift = [], []
    for d in sorted(p for p in a.cones.iterdir() if p.is_dir() and (p / "raw").is_dir()):
        raw = d / "raw"  # the CSVs of the collectors lie directly in raw/ (the cone tag is in their names)
        m = re.search(r"ra([0-9p]+)_dec(m?[0-9p]+)_r", next(iter(raw.glob("*.csv"))).name)
        ra, dec = (float(m.group(1).replace("p", ".")), float(m.group(2).replace("m", "-").replace("p", "."))) if m else (np.nan, np.nan)
        with tempfile.TemporaryDirectory() as tmp:
            out = S1.run(raw, Path(tmp) / "source_association.csv")
            asc = pd.read_csv(out, low_memory=False)
        if asc.empty:
            continue
        best = OP.best_positions(asc)
        g = asc.drop_duplicates("object_id").set_index("object_id")
        b = best.reindex(g.index)
        dra = (b.ra - g.object_ra) * np.cos(np.radians(b.dec))
        shift = np.hypot(dra, b.dec - g.object_dec) * 3600.0
        r = dict(cone=d.name, b_deg=round(gal_b(ra, dec), 1), objects=len(g), zero_pct=round(100 * float((shift == 0).mean()), 2), over_0p1_pct=round(100 * float((shift > 0.1).mean()), 2),
                 over_0p5_pct=round(100 * float((shift > 0.5).mean()), 2), median=float(shift.median()), p99=float(shift.quantile(0.99)), max=float(shift.max()))
        r.update({f"printed_{k}": int(v) for k, v in b.source.value_counts().items()})
        rows.append(r)
        allshift.append(pd.DataFrame(dict(shift=shift.to_numpy(), source=b.source.to_numpy(), anchor=g.object_anchor_catalog.to_numpy())))
    S = pd.concat(allshift, ignore_index=True)
    tot = dict(cone="ALL", b_deg=np.nan, objects=len(S), zero_pct=round(100 * float((S["shift"] == 0).mean()), 2), over_0p1_pct=round(100 * float((S["shift"] > 0.1).mean()), 2),
               over_0p5_pct=round(100 * float((S["shift"] > 0.5).mean()), 2), median=float(S["shift"].median()), p90=float(S["shift"].quantile(0.9)), p99=float(S["shift"].quantile(0.99)), max=float(S["shift"].max()))
    tot.update({f"printed_{k}": int(v) for k, v in S.source.value_counts().items()})
    pd.DataFrame(rows + [tot]).to_csv(a.out, index=False)
    print(pd.DataFrame([tot]).T.to_string())
    RI.write(a.out, [a.cones], t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
