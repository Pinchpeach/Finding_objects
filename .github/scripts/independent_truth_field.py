"""Independent-truth field validation (2026-10-21): spectroscopic classes from
surveys that were never used to train or tune v2 (LAMOST, 2QZ/6QZ, 2dFGRS,
6dFGS, 2SLAQ, WiggleZ, RAVE ...), fetched from VizieR around a sky region.

  probe                       list candidate VizieR catalogues and columns
  truth  RA DEC R_ARCMIN OUT  every row of every candidate catalogue in the cone
  centre TRUTH RA DEC R_SEARCH R_FIELD   print "ra dec n" of the R_FIELD cone,
                              centred on a truth object within R_SEARCH, that
                              holds the most truth objects
  compact WORK RA DEC R OUT   field products for local scoring: objects.csv.gz
                              (classes + the columns other classifiers need),
                              field.json (LS PSF size = seeing, counts)

Every archive request waits 3-5 s first (v2/Get_data/throttle.py).
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "v2/Get_data")
import throttle  # noqa: E402

throttle.install()

# VizieR identifiers; all tables under each prefix are kept.  Classes and
# quality flags are parsed later (benchmark/score_independent_fields.py),
# because the column sets differ per survey.
CATALOGUES = {
    "LAMOST DR5 (Luo+2019)": "V/164",
    "2QZ/6QZ (Croom+2004)": "VII/241",
    "2dFGRS (Colless+2003)": "VII/250",
    "6dFGS DR3 (Jones+2009)": "VII/259",
    "2SLAQ QSO (Croom+2009)": "J/MNRAS/392/19",
    "WiggleZ final (Drinkwater+2018)": "J/MNRAS/474/4151",
    "RAVE DR6 (Steinmetz+2020)": "III/283",
}
SEARCH_WORDS = ["LAMOST", "2SLAQ", "WiggleZ", "GAMA redshift", "6dF", "2QZ", "VIPERS", "zCOSMOS", "DEEP2", "VVDS"]


def _vizier(row_limit=-1):
    from astroquery.vizier import Vizier

    v = Vizier(columns=["**", "_RAJ2000", "_DEJ2000"], row_limit=row_limit)
    v.TIMEOUT = 300
    return v


def probe():
    from astroquery.vizier import Vizier

    for w in SEARCH_WORDS:
        try:
            found = Vizier.find_catalogs(w)
            print(f"== find '{w}':")
            for k, c in list(found.items())[:15]:
                print(f"   {k}: {c.description}")
        except Exception as exc:
            print(f"== find '{w}' failed: {exc!r}")
    for name, cat in CATALOGUES.items():
        try:
            meta = _vizier(3).get_catalogs(cat)
            for t in meta:
                print(f"== {name} {t.meta.get('name')} cols={list(t.colnames)}")
                print(t[:2])
        except Exception as exc:
            print(f"== {name} {cat} failed: {exc!r}")


def truth(ra, dec, radius, out):
    import astropy.units as u
    from astropy.coordinates import SkyCoord

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    c = SkyCoord(ra * u.deg, dec * u.deg)
    log = {}
    for name, cat in CATALOGUES.items():
        try:
            res = _vizier().query_region(c, radius=radius * u.arcmin, catalog=cat)
        except Exception as exc:
            log[name] = f"failed: {type(exc).__name__}: {str(exc)[:120]}"
            continue
        log[name] = {}
        for t in res:
            tab = t.meta.get("name", cat)
            df = t.to_pandas()
            for col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].map(lambda x: x.decode() if isinstance(x, bytes) else x)
            df.insert(0, "truth_catalogue", name)
            df.insert(1, "truth_table", tab)
            df.to_csv(out / (re.sub(r"[^A-Za-z0-9]+", "_", tab).strip("_") + ".csv.gz"), index=False)
            log[name][tab] = len(df)
    print(json.dumps(log, indent=1))
    (out / "truth_log.json").write_text(json.dumps(log, indent=1))


def _positions(truth_dir):
    pos = []
    for f in Path(truth_dir).glob("*.csv.gz"):
        d = pd.read_csv(f, low_memory=False)
        if {"_RAJ2000", "_DEJ2000"} <= set(d.columns):
            pos.append(d[["_RAJ2000", "_DEJ2000"]].astype(float).dropna().to_numpy())
    if not pos:
        return np.empty((0, 2))
    p = np.vstack(pos)
    # One object measured by several surveys counts once (1" grid).
    return np.unique(np.round(p * 3600).astype(np.int64), axis=0) / 3600.0


def centre(truth_dir, ra, dec, r_search, r_field):
    p = _positions(truth_dir)

    def sep(a, b, ra0, de0):
        return np.hypot((a - ra0) * np.cos(np.radians(de0)), b - de0) * 60

    best = (ra, dec, int((sep(p[:, 0], p[:, 1], ra, dec) <= r_field).sum()) if len(p) else 0)
    for ra0, de0 in p[sep(p[:, 0], p[:, 1], ra, dec) <= r_search - r_field] if len(p) else []:
        n = int((sep(p[:, 0], p[:, 1], ra0, de0) <= r_field).sum())
        if n > best[2]:
            best = (float(ra0), float(de0), n)
    print(f"{best[0]:.5f} {best[1]:.5f} {best[2]}")


KEEP = re.compile(
    r"^(object_id|designation|ra|dec|catalogs|primary_class|primary_confidence|classification_status|"
    r"parent_object_id|component_role|unknown_reason|subclass|gaia_dr3__classprob_dsc_combmod_\w+|"
    r"desi_legacy_surveys_dr10__(type|shape_r|sersic|maskbits)|allwise__W[12]mag|"
    r"pan_starrs1_dr2_meanobject__(iMeanPSFMag|iMeanKronMag|nDetections)|std_mag__\w+|gaia_dr3__phot_g_mean_mag|"
    r"gaia_dr3__(pmra|pmdec|parallax|parallax_over_error|ruwe))$"
)


def compact(work, ra, dec, radius, out):
    work, out = Path(work), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(work / "classified_objects.csv", low_memory=False)
    keep = [c for c in d.columns if KEEP.match(c)]
    o = d[keep].copy()
    f = work / "features.csv"
    if f.exists():
        ft = pd.read_csv(f, low_memory=False)
        extra = [c for c in ft.columns if KEEP.match(c) and c not in o.columns]
        if extra:
            o = o.merge(ft[["object_id"] + extra].drop_duplicates("object_id"), on="object_id", how="left")
    lv = work / "likelihood_vectors.csv"
    if lv.exists():  # LS-GBM-001 class scores, the LS-only ML used for comparison
        lt = pd.read_csv(lv, usecols=lambda c: c in ("object_id", "evidence_json"), low_memory=False)
        rows = []
        for oid, raw in zip(lt.object_id, lt.evidence_json):
            r = {"object_id": oid}
            try:
                ev = json.loads(raw) if isinstance(raw, str) else []
            except Exception:
                ev = []
            for e in ev:
                if e.get("rule_id") == "LS-GBM-001" and e.get("class") in ("STAR", "GALAXY", "QSO"):
                    r[f"lsgbm_{e['class']}"] = e.get("raw_score", e.get("score"))
            rows.append(r)
        o = o.merge(pd.DataFrame(rows).drop_duplicates("object_id"), on="object_id", how="left")
    o.to_csv(out / "objects.csv.gz", index=False)
    info = {"ra": ra, "dec": dec, "radius_arcmin": radius, "n_objects": int(len(o))}
    summ = work / "pipeline_summary.csv"
    if summ.exists():
        info["seconds"] = pd.read_csv(summ).set_index("stage").seconds.round(1).to_dict()
    info["catalog_rows"] = {}
    a = work / "source_association.csv"
    if a.exists():
        info["catalog_rows"] = pd.read_csv(a, usecols=["catalog"]).catalog.value_counts().to_dict()
    info["seeing"] = seeing(ra, dec, radius)
    (out / "field.json").write_text(json.dumps(info, indent=1, default=str))
    print(json.dumps(info, indent=1, default=str))


def seeing(ra, dec, radius):
    """Median Legacy Surveys PSF FWHM (arcsec, psfsize_*: Dey+2019 sec. 6) of
    point sources in the field, i.e. the image quality the classification used."""
    try:
        import desi_legacy as ls

        q = f"""SELECT psfsize_g, psfsize_r, psfsize_z FROM {ls.TABLE}
                WHERE type = 'PSF' AND 't' = Q3C_RADIAL_QUERY(ra, dec, {ra:.10f}, {dec:.10f}, {radius / 60:.10f})"""
        t = ls._query_with_retries(lambda: ls._service().search(q).to_table().to_pandas())
        return {b: round(float(t[f"psfsize_{b}"].replace(0, np.nan).median()), 2) for b in "grz"} | {"n_psf": int(len(t))}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}


if __name__ == "__main__":
    mode, args = sys.argv[1], sys.argv[2:]
    if mode == "probe":
        probe()
    elif mode == "truth":
        truth(float(args[0]), float(args[1]), float(args[2]), args[3])
    elif mode == "centre":
        centre(args[0], float(args[1]), float(args[2]), float(args[3]), float(args[4]))
    elif mode == "compact":
        compact(args[0], float(args[1]), float(args[2]), float(args[3]), args[4])
    sys.stdout.flush()
