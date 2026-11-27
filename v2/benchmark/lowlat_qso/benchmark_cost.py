#!/usr/bin/env python3
"""How many spectroscopic quasars of the local benchmarks the survey-count switches would hold back (2.61.5).

    python benchmark_cost.py --out OUT

The local benchmarks (``benchmark/truth_data/ground_truth.csv`` with ``benchmark/catalog_features``, ``sdss_sky``, ``desi_external``, ``desi_fusion``) hold, for every spectroscopic
truth object, one row per catalogue in which the object has a counterpart (``catalog_features/*_trd.csv.gz``).  The number of catalogues is the number of surveys that measure the object, the quantity ``surveys2`` /
``surveys3`` ask for (``lowlat_qso.n_surveys``): every file is a different survey (Gaia, Pan-STARRS1, Legacy Surveys, AllWISE, 2MASS,
GALEX, FIRST, NVSS, VLASS, LoTSS, Chandra, XMM, eROSITA, ZTF).  The SDSS sets are SDSS spectroscopic objects, whose own SDSS imaging
(``SDSS DR18 PhotoObj``) the pipeline collects as one more survey: ``n_plus_sdss_imaging`` adds it.  The benchmarks are blind (no
spectra among the catalogues).

For each set, class and magnitude bin: ``frac_lt2`` / ``frac_lt3`` = the share of objects with fewer than 2 / 3 surveys, that is,
the share a label switch would hold back if the evidence gave them the QSO label.  The magnitude is the SDSS PSF r where the truth
table has it (``sdss_sky``), else Pan-STARRS1 r, else Legacy Surveys r.  ``sdss_sky`` has the Galactic latitude: its low-latitude
part (|b| < 20) is reported apart.  A share is not a loss of the base's labels (the base may not label them QSO anyway): the loss
by magnitude and surveys is measured on the deep COSMOS fields (``faint_cost.py``); this table says how the number of surveys of
spectroscopic quasars is distributed where only catalogue presence, not the classifier, is involved.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

B = Path(__file__).resolve().parents[1]
SETS = {  # name -> (truth csv, feature folder, pattern, SDSS imaging counts as one more survey)
    "sdss_general": (B / "truth_data" / "ground_truth.csv", B / "catalog_features", "*_trd.csv.gz", True),
    "sdss_sky": (B / "sdss_sky" / "truth.csv", B / "sdss_sky" / "catalog_features", "*_trd.csv.gz", True),
    "desi_external": (B / "desi_external" / "truth.csv", B / "desi_external" / "catalog_features", "*_trd.csv.gz", False),
    "desi_fusion": (B / "desi_fusion" / "truth.csv", B / "desi_fusion" / "catalog_features", "*_trd.csv.gz", False),
}
MAG_BINS = [(-np.inf, 19.0), (19.0, 20.0), (20.0, 21.0), (21.0, 22.0), (22.0, np.inf)]


def survey_table(truth: pd.DataFrame, folder: Path, pattern: str) -> pd.DataFrame:
    """Per truth object: the number of catalogue files with a row, and a magnitude from PS1 / Legacy Surveys."""
    ids = truth.benchmark_id.astype(str)
    n = pd.Series(0, index=ids, dtype=int)
    ps1 = pd.Series(np.nan, index=ids, dtype=float)
    ls = pd.Series(np.nan, index=ids, dtype=float)
    names = []
    for f in sorted(folder.glob(pattern)):
        d = pd.read_csv(f, low_memory=False)
        if "benchmark_id" not in d:
            continue
        d["benchmark_id"] = d.benchmark_id.astype(str)
        has = d.dropna(subset=["catalog_object_id"]) if "catalog_object_id" in d else d
        k = has.benchmark_id.drop_duplicates()
        n.loc[n.index.intersection(k)] += 1
        names.append(f.name.split("_trd")[0])
        if "rMeanPSFMag" in d:
            s = d.drop_duplicates("benchmark_id").set_index("benchmark_id").rMeanPSFMag
            m = pd.to_numeric(s, errors="coerce").reindex(ps1.index)
            ps1 = ps1.where(ps1.notna(), m.where(m > 0))
        if "flux_r" in d and "desi_legacy" in f.name:
            s = d.drop_duplicates("benchmark_id").set_index("benchmark_id").flux_r
            fr = pd.to_numeric(s, errors="coerce")
            with np.errstate(divide="ignore", invalid="ignore"):
                lm = 22.5 - 2.5 * np.log10(fr.where(fr > 0))
            ls = ls.where(ls.notna(), lm.reindex(ls.index))
    # Pan-STARRS1 r first, Legacy Surveys r where PS1 has none (the files are read in name order, desi_legacy before panstarrs1,
    # so the two are kept apart and combined here; Codex review of 2.61.5)
    mag = ps1.where(ps1.notna(), ls)
    out = pd.DataFrame({"benchmark_id": ids.to_numpy(), "n_catalogues": n.to_numpy(), "mag_cat": mag.to_numpy()})
    out.attrs["catalogues"] = names
    return out


def run(name: str) -> list[dict]:
    truth_csv, folder, pattern, sdss = SETS[name]
    t = pd.read_csv(truth_csv, low_memory=False)
    s = survey_table(t, folder, pattern)
    t = t.assign(benchmark_id=t.benchmark_id.astype(str)).merge(s, on="benchmark_id", how="left")
    mag = pd.to_numeric(t.get("psfmag_r"), errors="coerce") if "psfmag_r" in t else pd.Series(np.nan, index=t.index)
    t["mag"] = mag.where(mag.notna() & (mag > 0), t.mag_cat)
    t["n_plus_sdss_imaging"] = t.n_catalogues + (1 if sdss else 0)
    rows = []
    groups = [("all", t)]
    if "gal_b" in t:
        groups.append(("|b|<20", t[t.gal_b.abs() < 20]))
    for gname, g in groups:
        for cls in ("QSO", "STAR", "GALAXY"):
            x = g[g.truth_class == cls]
            for lo, hi in [(-np.inf, np.inf), *MAG_BINS]:
                y = x if (lo, hi) == (-np.inf, np.inf) else x[(x.mag >= lo) & (x.mag < hi)]
                if not len(y):
                    continue
                row = dict(set=name, group=gname, truth_class=cls,
                           mag="all" if (lo, hi) == (-np.inf, np.inf) else (f"<{hi:g}" if lo == -np.inf else (f">={lo:g}" if hi == np.inf else f"{lo:g}-{hi:g}")),
                           n=len(y), median_surveys=float(y.n_catalogues.median()))  # fmt: skip
                for col, lab in (("n_catalogues", ""), ("n_plus_sdss_imaging", "_plus_sdss")):
                    if lab and not sdss:
                        continue
                    row[f"frac_lt2{lab}"] = round(float((y[col] < 2).mean()), 4)
                    row[f"frac_lt3{lab}"] = round(float((y[col] < 3).mean()), 4)
                rows.append(row)
        # the distribution of the number of surveys of the quasars
        x = g[g.truth_class == "QSO"]
        for k in range(0, 8):
            rows.append(dict(set=name, group=gname, truth_class="QSO", mag=f"n_catalogues={k}" if k < 7 else "n_catalogues>=7",
                             n=int((x.n_catalogues == k).sum() if k < 7 else (x.n_catalogues >= k).sum())))  # fmt: skip
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sets", default=",".join(SETS))
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for s in a.sets.split(","):
        rows += run(s)
    d = pd.DataFrame(rows)
    d.to_csv(a.out / "benchmark_cost.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_rows", 300):
        print(d[(d.truth_class == "QSO") & ~d.mag.astype(str).str.startswith("n_cat")].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
