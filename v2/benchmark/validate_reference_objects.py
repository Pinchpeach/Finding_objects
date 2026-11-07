#!/usr/bin/env python3
"""Validate the classifier on the literature reference objects (2.46.2).

For a sample of the reference objects (v2/reference_objects/, 2.46.1) the full
pipeline is run in a small cone around each object, twice:

* full  -- every collector, as a user would run it;
* blind -- the spectroscopic and literature catalogues removed from the raw
  data (the same list as the independent-field validation: SDSS / LAMOST /
  DESI spectra, SIMBAD, NED, BZCAT, HASH and PN spectra, ASAS-SN and Asiago
  supernovae, Suh AGB, ATNF, galaxy-cluster catalogues), so that the source
  of a reference label cannot also be its evidence.

The pipeline object nearest to the reference position (within MATCH_ARCSEC)
is compared with the reference type:

* coarse: primary_class equals the reference's coarse class (STAR / GALAXY /
  QSO; "either" also accepts the 2.46.0 secondary GALAXY/QSO label);
* type: one of the type's expected labels appears among the classifier's
  axis classes / subtypes / sub-class code and tags (EXPECT below).

    python validate_reference_objects.py plan  --per-type 10 --shards 26 --out PLAN.csv
    python validate_reference_objects.py run   --plan PLAN.csv --shard K --out DIR
    python validate_reference_objects.py score --in DIR --out REPORT_DIR
"""

from __future__ import annotations

import argparse
import math
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[1]
REF = V2 / "reference_objects" / "reference_objects.csv.gz"
RADIUS_ARCMIN = 0.3
MATCH_ARCSEC = 3.0
MATCH_EXTENDED_ARCSEC = 8.0  # galaxies, PNe: centroids of extended sources differ between surveys
EXTENDED_TYPES = ("GALAXY_ELLIPTICAL", "GALAXY_LENTICULAR", "GALAXY_SPIRAL", "GALAXY_INTERACTING_PECULIAR", "PLANETARY_NEBULA", "SEYFERT_1", "SEYFERT_2", "LINER")
BLIND_DROP = (
    "lamost_spectroscopy_", "sdss_spectroscopy_", "desi_spectroscopy_", "desi_fastspec_", "simbad_", "ned_", "bzcat_",
    "pn_spectroscopy_", "hash_pn_", "asas_sn_supernova_", "asiago_supernova_", "agb_suh2021_", "atnf_pulsar_", "galaxy_clusters_",
)
LABEL_COLS = (
    "primary_class", "secondary_class", "detailed_class", "physical_class", "physical_subtype", "variability_class",
    "variability_subtype", "compact_class", "compact_subtype", "extragalactic_class", "extragalactic_subtype",
    "phenomenon_class", "phenomenon_subtype", "subclass_code", "subclass_tags", "paper_class",
)
KEEP = LABEL_COLS + ("classification_status", "primary_confidence", "object_id", "catalogs")

# Classifier labels that count as recognising each reference type (any one).
EXPECT = {
    "GALAXY_STAR_FORMING": ("STAR_FORMING", "STARBURST", "SF"),
    "GALAXY_STARBURST": ("STARBURST", "STAR_FORMING", "SBG"),
    "SEYFERT_1": ("AGN", "SEYFERT", "SY1", "BROADLINE", "QSO"),
    "SEYFERT_2": ("AGN", "SEYFERT", "SY2"),
    "LINER": ("AGN", "LINER", "LIN"),
    "BLAZAR_BL_LAC": ("BLAZAR", "BL_LAC", "BLL"),
    "BLAZAR_FSRQ": ("BLAZAR", "FSRQ"),
    "GALAXY_ELLIPTICAL": ("EARLY_TYPE", "QUIESCENT", "ELLIPTICAL"),
    "GALAXY_LENTICULAR": ("EARLY_TYPE", "QUIESCENT", "LENTICULAR"),
    "GALAXY_SPIRAL": ("DISK", "SPIRAL", "STAR_FORMING"),
    "GALAXY_INTERACTING_PECULIAR": ("INTERACTING", "IG", "MERGER", "PECULIAR"),
    "WHITE_DWARF_DA": ("WHITE_DWARF", "WD", "WHITE_DWARF_CANDIDATE", "DA"),
    "WHITE_DWARF_DB": ("WHITE_DWARF", "WD", "WHITE_DWARF_CANDIDATE", "DB"),
    "HOT_SUBDWARF_SDB": ("HOT_SUBDWARF", "SDB"),
    "HOT_SUBDWARF_SDO": ("HOT_SUBDWARF", "SDO"),
    "HOT_SUBDWARF_SDOB": ("HOT_SUBDWARF", "SDOB"),
    "ULTRACOOL_L_DWARF": ("ULTRACOOL_DWARF", "BROWN_DWARF", "L_DWARF"),
    "ULTRACOOL_T_DWARF": ("ULTRACOOL_DWARF", "BROWN_DWARF", "T_DWARF"),
    "ULTRACOOL_Y_DWARF": ("ULTRACOOL_DWARF", "BROWN_DWARF", "Y_DWARF"),
    "RED_GIANT": ("RGB", "RED_GIANT", "GIANT", "III"),
    "AGB_CARBON_RICH": ("AGB", "C_STAR", "C_RICH", "CARBON"),
    "AGB_OXYGEN_RICH": ("AGB", "O_RICH", "OXYGEN"),
    "YSO_TAURUS_MEMBER": ("YSO", "YOUNG_STAR", "TTAURI"),
    "YSO_VARIABLE": ("YSO", "YOUNG_STAR", "TTAURI", "ERUPTIVE"),
    "RR_LYRAE_AB": ("RR_LYRAE", "RRAB"),
    "RR_LYRAE_C": ("RR_LYRAE", "RRC"),
    "CEPHEID_CLASSICAL": ("CEPHEID", "DCEP"),
    "CEPHEID_TYPE_II_CWA": ("CEPHEID", "T2CEP", "CEPII", "CWA"),
    "CEPHEID_TYPE_II_CWB": ("CEPHEID", "T2CEP", "CEPII", "CWB"),
    "DELTA_SCUTI": ("DSCT", "DELTA_SCUTI"),
    "DELTA_SCUTI_HADS": ("DSCT", "DELTA_SCUTI", "HADS"),
    "MIRA": ("MIRA",),
    "SEMIREGULAR_VARIABLE": ("LPV", "SR", "SEMIREGULAR"),
    "ROTATIONAL_VARIABLE": ("ROTATIONAL", "ROT", "BY_DRA", "BYDRA", "RS_CVN", "RSCVN", "SOLAR_LIKE"),
    "ECLIPSING_ALGOL": ("ECLIPSING", "ECL", "EA"),
    "ECLIPSING_BETA_LYR": ("ECLIPSING", "ECL", "EB"),
    "ECLIPSING_W_UMA": ("ECLIPSING", "ECL", "EW"),
    "CATACLYSMIC_DWARF_NOVA": ("CV", "CATACLYSMIC", "DWARF_NOVA", "NOVA"),
    "CATACLYSMIC_POLAR": ("CV", "CATACLYSMIC", "POLAR", "AM_HER"),
    "NOVA_CLASSICAL": ("NOVA", "CV", "CATACLYSMIC"),
    "X_RAY_BINARY_LOW_MASS": ("XRB", "X_RAY_BINARY", "LMXB"),
    "X_RAY_BINARY_HIGH_MASS": ("XRB", "X_RAY_BINARY", "HMXB"),
    "PULSAR": ("PULSAR", "PULSAR_CANDIDATE"),
    "PLANETARY_NEBULA": ("PN", "PLANETARY_NEBULA"),
    "SUPERNOVA_IA": ("SN", "SUPERNOVA"),
    "SUPERNOVA_II": ("SN", "SUPERNOVA"),
    "SUPERNOVA_IB_IC": ("SN", "SUPERNOVA"),
    "GALAXY_CLUSTER": ("CLUSTER", "GROUP", "GALAXY_CLUSTER"),
}


# Coarser labels one level up the classifier's hierarchy (credited separately as "parent").
PARENT = {
    **{t: ("PULSATING",) for t in ("RR_LYRAE_AB", "RR_LYRAE_C", "CEPHEID_CLASSICAL", "CEPHEID_TYPE_II_CWA", "CEPHEID_TYPE_II_CWB", "DELTA_SCUTI", "DELTA_SCUTI_HADS")},
    **{t: ("LPV", "PULSATING", "MIRA") for t in ("MIRA", "SEMIREGULAR_VARIABLE")},
    "ROTATIONAL_VARIABLE": ("OTHER_VARIABLE", "VARIABLE"),
    "YSO_VARIABLE": ("VARIABLE", "OTHER_VARIABLE", "ERUPTIVE"),
    **{t: ("BINARY", "ECLIPSING") for t in ("ECLIPSING_ALGOL", "ECLIPSING_BETA_LYR", "ECLIPSING_W_UMA")},
    **{t: ("ERUPTIVE", "CV", "WD", "WHITE_DWARF_CANDIDATE") for t in ("CATACLYSMIC_DWARF_NOVA", "CATACLYSMIC_POLAR", "NOVA_CLASSICAL")},
    **{t: ("AGN", "QUASAR", "RADIO_LOUD") for t in ("SEYFERT_1", "SEYFERT_2", "LINER", "BLAZAR_BL_LAC", "BLAZAR_FSRQ")},
    **{t: ("AGB", "MIRA", "LPV", "C_STAR_CANDIDATE") for t in ("AGB_CARBON_RICH", "AGB_OXYGEN_RICH")},
    **{t: ("WHITE_DWARF_CANDIDATE", "WD") for t in ("WHITE_DWARF_DA", "WHITE_DWARF_DB")},
    "PLANETARY_NEBULA": ("NEBULA", "PN"),
}


def tokens(row) -> set[str]:
    s = " ".join(str(row.get(c, "")) for c in LABEL_COLS if str(row.get(c, "")) not in ("", "nan", "None"))
    return {t for t in re.split(r"[^A-Z0-9_]+", s.upper()) if t}


def plan(a):
    ref = pd.read_csv(REF).dropna(subset=["ra", "dec"])
    pick = pd.concat([g.sample(min(len(g), a.per_type), random_state=7) for _, g in ref.groupby("type", sort=True)])
    pick = pick.sample(frac=1, random_state=7).reset_index(drop=True)
    pick["shard"] = np.arange(len(pick)) % a.shards
    pick.to_csv(a.out, index=False)
    print(len(pick), "objects,", pick.type.nunique(), "types,", a.shards, "shards")


def sep_arcsec(ra, dec, ra0, dec0):
    dra = ((ra - ra0 + 180) % 360 - 180) * math.cos(math.radians(dec0))
    return 3600 * np.hypot(dra, dec - dec0)


def nearest(work: Path, ra0, dec0, tol):
    f = work / "classified_objects.csv"
    if not f.exists():
        return None, np.nan
    d = pd.read_csv(f, low_memory=False)
    if not len(d) or "ra" not in d:
        return None, np.nan
    if "parent_object_id" in d:  # a grouped fragment speaks through its parent
        d = d.copy()
    s = sep_arcsec(pd.to_numeric(d.ra, errors="coerce").to_numpy(float), pd.to_numeric(d.dec, errors="coerce").to_numpy(float), ra0, dec0)
    i = int(np.nanargmin(s)) if np.isfinite(s).any() else None
    if i is None or s[i] > tol:
        return None, float(np.nanmin(s)) if np.isfinite(s).any() else np.nan
    row = d.iloc[i].to_dict()
    pid = row.get("parent_object_id")
    if isinstance(pid, str) and pid and "object_id" in d:
        par = d[d.object_id.astype(str) == pid]
        if len(par):
            row = {**row, **{c: par.iloc[0].get(c) for c in LABEL_COLS if c in par}}
    return row, float(s[i])


def run_pipeline(args, timeout=900):
    t = time.time()
    p = subprocess.run([sys.executable, "-u", str(V2 / "pipeline.py"), *map(str, args)], text=True, capture_output=True, timeout=timeout)
    return p.returncode, time.time() - t, (p.stdout + p.stderr)[-600:]


def run(a):
    pl = pd.read_csv(a.plan)
    pl = pl[pl.shard == a.shard]
    out = []
    a.out.mkdir(parents=True, exist_ok=True)
    for r in pl.itertuples():
        tol = MATCH_EXTENDED_ARCSEC if r.type in EXTENDED_TYPES else MATCH_ARCSEC
        rec = dict(code=r.code, catalog_name=r.catalog_name, type=r.type, coarse_class=r.coarse_class, ra=r.ra, dec=r.dec)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            try:
                rc, sec, tail = run_pipeline(["--ra", r.ra, "--dec", r.dec, "--radius", RADIUS_ARCMIN, "--work", td / "full"])
            except subprocess.TimeoutExpired:
                rc, sec, tail = -1, 900.0, "timeout"
            rec.update(full_rc=rc, full_seconds=round(sec, 1))
            row, s = nearest(td / "full", r.ra, r.dec, tol)
            rec["full_sep"] = s
            for c in KEEP:
                rec[f"full_{c}"] = (row or {}).get(c)
            raws = sorted((td / "full" / "raw").glob("*/")) if (td / "full" / "raw").exists() else []
            if raws:
                blind = td / "blindraw"
                blind.mkdir()
                for f in raws[0].glob("*.csv"):
                    if not f.name.startswith(BLIND_DROP):
                        shutil.copy(f, blind / f.name)
                try:
                    rc2, sec2, _ = run_pipeline(["--raw-dir", blind, "--ra", r.ra, "--dec", r.dec, "--radius", RADIUS_ARCMIN, "--work", td / "blind"])
                except subprocess.TimeoutExpired:
                    rc2, sec2 = -1, 900.0
                rec.update(blind_rc=rc2, blind_seconds=round(sec2, 1))
                row, s = nearest(td / "blind", r.ra, r.dec, tol)
                rec["blind_sep"] = s
                for c in KEEP:
                    rec[f"blind_{c}"] = (row or {}).get(c)
            if rc != 0:
                rec["error"] = tail
            if a.keep:
                k = a.keep / f"{r.type}_{str(r.code).replace('/', '_')}"
                k.mkdir(parents=True, exist_ok=True)
                for mode in ("full", "blind"):
                    for f in ("source_association.csv", "classified_objects.csv"):
                        if (td / mode / f).exists():
                            shutil.copy(td / mode / f, k / f"{mode}_{f}")
        print(f"{r.type:28s} {r.catalog_name} {r.code}: full {rec.get('full_primary_class')} / blind {rec.get('blind_primary_class')} ({rec['full_seconds']} s)", flush=True)
        out.append(rec)
        pd.DataFrame(out).to_csv(a.out / f"shard_{a.shard:02d}.csv", index=False)


def score(a):
    src = Path(a.inp)
    files = [src] if src.is_file() else sorted(src.glob("shard_*.csv"))
    d = pd.concat([pd.read_csv(f, low_memory=False) for f in files], ignore_index=True)
    a.out.mkdir(parents=True, exist_ok=True)
    d.to_csv(a.out / "reference_validation_objects.csv.gz", index=False)
    rows = []
    for mode in ("full", "blind"):
        for typ, g in d.groupby("type", sort=False):
            m = g[f"{mode}_primary_class"].notna()
            coarse = g.coarse_class.iloc[0]
            pc = g[f"{mode}_primary_class"].astype(str)
            sc = g.get(f"{mode}_secondary_class", pd.Series("", index=g.index)).astype(str)
            tok = [tokens({c: rr.get(f"{mode}_{c}") for c in LABEL_COLS}) for rr in g.to_dict("records")]
            exp = set(EXPECT.get(typ, ()))
            hit = pd.Series([bool(t & exp) for t in tok], index=g.index)
            r = dict(mode=mode, type=typ, coarse=coarse, n=len(g), matched=int(m.sum()))
            if coarse in ("STAR", "GALAXY", "QSO"):
                r["coarse_ok"] = int((m & (pc == coarse)).sum())
                r["coarse_either"] = int((m & ((pc == coarse) | (sc == coarse))).sum())
                r["unknown"] = int((m & (pc == "UNKNOWN")).sum())
            if exp:
                r["type_ok"] = int((m & hit).sum())
                par = exp | set(PARENT.get(typ, ()))
                r["type_or_parent_ok"] = int((m & pd.Series([bool(t & par) for t in tok], index=g.index)).sum())
            r["labels"] = "; ".join(f"{k}:{v}" for k, v in pc[m].value_counts().head(3).items())
            rows.append(r)
    res = pd.DataFrame(rows)
    res.to_csv(a.out / "reference_validation_summary.csv", index=False)
    print(res.to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--per-type", type=int, default=10)
    p.add_argument("--shards", type=int, default=26)
    p.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("run")
    r.add_argument("--plan", type=Path, required=True)
    r.add_argument("--shard", type=int, required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--keep", type=Path, help="copy each object's association and classified tables here")
    s = sub.add_parser("score")
    s.add_argument("--in", dest="inp", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    {"plan": plan, "run": run, "score": score}[a.mode](a)


if __name__ == "__main__":
    main()
