#!/usr/bin/env python3
"""AGB chemistry truth from GCVS long-period variables with spectral types.

The Suh (2021) O-AGB stars are IR-selected and dusty (median Ks - W3 = 1.93),
so a model fitted on them calls dust-free O-rich giants carbon-rich: 65 % of
the Gaia DR3 LPVs in random cones came out C-rich (agb_gate_sample).  The
General Catalogue of Variable Stars (Samus et al. 2017, VizieR B/gcvs)
lists Miras, semiregulars and slow irregulars (types M, SR*, L*) with
literature spectral types, dusty or not:

* M... (not MS) -> O-rich;  C..., R..., N... -> C-rich;  S, MS, SC -> dropped.

Photometry: Gaia DR3, 2MASS, AllWISE and the Gaia DR3 LPV table, nearest
source (VizieR multi-position cone search, as build_agb_chemistry_truth.py).
Output: v2/benchmark/agb_truth/agb_gcvs_truth.csv.gz
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
from build_agb_chemistry_truth import ASU_CATALOGS, retry, vizier_asu  # noqa: E402

LPV_TYPES = re.compile(r"^(M|SR[ABCDS]?|L[BC]?)(?![A-Z])")


def chem_of(sp: str) -> str | None:
    s = str(sp or "").strip().upper()
    if not s or s in ("NAN", "NONE"):
        return None
    if s.startswith(("MS", "SC", "S")):
        return None
    if s.startswith("M"):
        return "O"
    if s.startswith(("C", "R", "N")):
        return "C"
    return None


def labels() -> pd.DataFrame:
    from astroquery.vizier import Vizier
    v = Vizier(columns=["GCVS", "VarType", "SpType", "Period", "_RAJ2000", "_DEJ2000"], row_limit=-1, timeout=600)
    t = retry(lambda: v.get_catalogs("B/gcvs/gcvs_cat"), tries=3, wait=30)[0].to_pandas()
    print("GCVS rows:", len(t), "columns:", list(t.columns), flush=True)
    t["var"] = t["VarType"].astype(str).str.strip().str.upper()
    t = t[t["var"].str.match(LPV_TYPES)]
    t["chem"] = t["SpType"].map(chem_of)
    t = t.dropna(subset=["chem", "_RAJ2000", "_DEJ2000"])
    out = pd.DataFrame({"agb_id": range(len(t)), "ra": pd.to_numeric(t["_RAJ2000"]).to_numpy(),
                        "dec": pd.to_numeric(t["_DEJ2000"]).to_numpy(), "chem": t["chem"].to_numpy(),
                        "gcvs_name": t["GCVS"].astype(str).str.strip().to_numpy(), "gcvs_type": t["var"].to_numpy(),
                        "gcvs_sptype": t["SpType"].astype(str).str.strip().to_numpy()})
    print("GCVS LPVs with spectral types:", out.chem.value_counts().to_dict(),
          out.gcvs_type.str.extract(r"^([A-Z]+)")[0].value_counts().head(8).to_dict(), flush=True)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=BENCH / "agb_truth" / "agb_gcvs_truth.csv.gz")
    a = p.parse_args()
    cats = dict(ASU_CATALOGS)
    cats["gaia"] = (cats["gaia"][0], 3.0, *cats["gaia"][2:])       # GCVS positions are older
    df = vizier_asu(labels(), catalogs=cats)
    phot = [c for c in df.columns if c.startswith(("g_", "tm_", "aw_"))]
    if not phot or df[phot].notna().any(axis=1).mean() < 0.2:
        raise SystemExit(f"photometry missing for most stars ({phot}); not writing {a.out}")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False, compression="gzip")
    print(df.shape, df.chem.value_counts().to_dict(), "->", a.out)


if __name__ == "__main__":
    main()
