#!/usr/bin/env python3
"""Build an SDSS-independent, magnitude-stratified STAR/GALAXY/QSO truth set from DESI DR1.

Source: DESI DR1 redshift catalog (DESI Collaboration 2025; VizieR V/161/zcatdr1).
Labels are Redrock SPECTYPE (``OType``) with the standard good-redshift cuts
ZWARN == 0 and DELTACHI2 > 25 on the primary coadded spectrum.  Objects are
drawn from several RA windows (to avoid one sky patch) in r-band bins from the
Legacy Surveys flux (r = 22.5 - 2.5 log10 FLUX_R), and anything within 2 arcsec
of the SDSS benchmark truth is excluded.
"""

from __future__ import annotations
import argparse, math
from pathlib import Path
import numpy as np, pandas as pd

CLASSES = ("STAR", "GALAXY", "QSO")
R_BINS = ((18.0, 20.0), (20.0, 21.0), (21.0, 22.0), (22.0, 23.0))
RA_WINDOWS = ((5, 15), (35, 45), (125, 135), (150, 160), (175, 185), (200, 210), (225, 235), (330, 340))


def flux_range(lo, hi):
    f = lambda m: 10 ** ((22.5 - m) / 2.5)
    return f(hi), f(lo)


def query(cls, rlo, rhi, ra_lo, ra_hi, limit):
    from astroquery.vizier import Vizier

    fmin, fmax = flux_range(rlo, rhi)
    v = Vizier(
        columns=[
            "TargetID",
            "RAICRS",
            "DEICRS",
            "OType",
            "SubType",
            "z",
            "ZWARN",
            "delChi2",
            "Fr",
            "MType",
            "ZCAT_PRIM",
            "Prog",
        ],
        row_limit=limit,
    )
    t = v.query_constraints(
        catalog="V/161/zcatdr1",
        OType=cls,
        ZWARN="=0",
        delChi2=">25",
        ZCAT_PRIM="=1",
        Fr=f"{fmin:.4f}..{fmax:.4f}",
        RAICRS=f"{ra_lo}..{ra_hi}",
    )
    return t[0].to_pandas() if t else pd.DataFrame()


def sep_arcsec(ra1, dec1, ra2, dec2):
    r1, d1, r2, d2 = map(np.radians, (ra1, dec1, ra2, dec2))
    a = np.sin((d2 - d1) / 2) ** 2 + np.cos(d1) * np.cos(d2) * np.sin((r2 - r1) / 2) ** 2
    return np.degrees(2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))) * 3600


def main():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Get_data"))
    import throttle

    throttle.install()  # 3-5 s before every archive request (2.33.0)
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-cell", type=int, default=150, help="objects per class per r bin")
    ap.add_argument("--sdss-truth", type=Path, default=Path(__file__).with_name("truth_data") / "ground_truth.csv")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20261008)
    # 2.26.0: a second, larger DESI set for fusion training only.  It must
    # not share objects with the DESI external benchmark or with the LS-GBM
    # training set (LS-GBM-001 evidence would be in-sample there).
    ap.add_argument(
        "--ra-windows",
        default=None,
        help="RA windows 'lo-hi,lo-hi,...' (default: the external benchmark's eight windows)",
    )
    ap.add_argument(
        "--exclude",
        type=Path,
        nargs="*",
        default=[],
        help="CSV files whose desi_targetid / targetid values are excluded",
    )
    ap.add_argument("--id-prefix", default="DESI")
    a = ap.parse_args()
    global RA_WINDOWS
    if a.ra_windows:
        RA_WINDOWS = tuple(tuple(float(v) for v in w.split("-")) for w in a.ra_windows.split(","))
    excluded = set()
    for f in a.exclude:
        x = pd.read_csv(f, low_memory=False)
        col = next(c for c in ("desi_targetid", "targetid", "TargetID") if c in x.columns)
        excluded |= set(x[col].astype(str))
    rng = np.random.default_rng(a.seed)
    per_window = math.ceil(a.per_cell / len(RA_WINDOWS))
    parts = []
    n_excluded = 0
    for cls in CLASSES:
        for rlo, rhi in R_BINS:
            got = []
            for ra_lo, ra_hi in RA_WINDOWS:
                d = query(cls, rlo, rhi, ra_lo, ra_hi, per_window * 4)
                # Excluded objects are dropped before sampling: dropped after
                # head(per_cell) they left the cells short.
                if excluded and len(d):
                    keep = ~d.TargetID.astype(str).isin(excluded)
                    n_excluded += int((~keep).sum())
                    d = d[keep]
                if len(d):
                    got.append(d.sample(min(len(d), per_window), random_state=int(rng.integers(1 << 31))))
            d = pd.concat(got, ignore_index=True) if got else pd.DataFrame()
            print(f"{cls} r={rlo}-{rhi}: {len(d)}", flush=True)
            if len(d):
                d["r_bin"] = f"{rlo:g}-{rhi:g}"
                parts.append(d.head(a.per_cell))
    t = pd.concat(parts, ignore_index=True).drop_duplicates("TargetID")
    if excluded:
        print(f"excluded {n_excluded} queried objects listed in --exclude", flush=True)
    t["ra"] = pd.to_numeric(t.RAICRS, errors="coerce")
    t["dec"] = pd.to_numeric(t.DEICRS, errors="coerce")
    sd = pd.read_csv(a.sdss_truth)
    near = np.zeros(len(t), dtype=bool)
    for i, (r, d) in enumerate(zip(t.ra, t.dec)):
        m = (sd.dec - d).abs() < 0.001
        if m.any():
            near[i] = (sep_arcsec(r, d, sd.ra[m].to_numpy(), sd.dec[m].to_numpy()) < 2).any()
    t = t[~near].copy()
    t["r_mag"] = 22.5 - 2.5 * np.log10(pd.to_numeric(t.Fr, errors="coerce").where(lambda x: x > 0))
    out = pd.DataFrame(
        {
            "benchmark_id": [f"{a.id_prefix}{i:06d}" for i in range(1, len(t) + 1)],
            "ra": t.ra.to_numpy(),
            "dec": t.dec.to_numpy(),
            "truth_class": t.OType.astype(str).str.strip().to_numpy(),
            "truth_subclass": t.SubType.astype(str).to_numpy(),
            "z": t.z.to_numpy(),
            "r_mag": t.r_mag.to_numpy(),
            "r_bin": t.r_bin.to_numpy(),
            "desi_targetid": t.TargetID.astype(str).to_numpy(),
            "desi_program": t.Prog.astype(str).to_numpy(),
            "truth_source": "DESI_DR1_V161",
            "truth_quality": "ZWARN0_DELTACHI2_GT25_ZCAT_PRIMARY",
        }
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)
    print(f"[OK] {len(out)} rows (excluded {int(near.sum())} near SDSS truth) -> {a.out}")
    print(out.groupby(["truth_class", "r_bin"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
