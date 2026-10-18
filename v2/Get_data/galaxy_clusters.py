"""Galaxy cluster catalogues (2.32.0): context for cluster membership, not detections.

* Wen & Han 2024 (ApJS 272, 39; VizieR J/ApJS/272/39): 1.58 million clusters
  from DESI Legacy Surveys DR9/DR10 photometric redshifts, z < 1.5; position
  of the BCG, cluster redshift (photometric ~0.010, or spectroscopic), r500
  in Mpc, M500.
* eRASS1 clusters (Bulbul et al. 2024, A&A 685, A106; VizieR J/A+A/685/A106):
  12,247 extended X-ray sources with optical redshifts (Kluge et al. 2024),
  R500 in kpc; P_cont < 0.5 keeps a 95 %-pure sample (their Table 1).

The cone is widened by ``MAX_EXTRA_ARCMIN`` because a cluster centred outside
the field can still cover it (r500 ~ 1 Mpc is ~16' at z = 0.05).  Stage 1
does not read this file (classification context, like a mask); the pipeline's
last step (``v2/clusters.py``) uses it.  Column names are picked from known
alternatives, case-insensitively.
"""

from __future__ import annotations
import pandas as pd
from _catalog_utils import coordinates, empty_frame, numeric, pick, save_csv, vizier_query

CATALOG = "Galaxy clusters"
MAX_EXTRA_ARCMIN = 20.0
CACHE_FILTER_MARGIN_ARCMIN = MAX_EXTRA_ARCMIN
SOURCES = (
    # (label, VizieR id, id cols, z cols, z-spec flag cols, r500 cols, r500 unit (Mpc per value), extra cols)
    (
        "WH24",
        "J/ApJS/272/39",
        ["Name", "ID", "WHL", "Seq"],
        ["zcl", "z", "zCl", "z_cl"],
        ["f_zcl", "zFlag", "z-flag", "f_z"],
        ["r500", "R500"],
        1.0,
        {"m500": ["M500"], "richness": ["Rich", "lambda500", "l500", "Richness"]},
    ),
    (
        "eRASS1",
        "J/A+A/685/A106",
        ["Name", "eRASS1", "DETUID"],
        ["zBest", "z", "BEST_Z", "zbest"],
        [],
        ["R500"],
        1e-3,
        {"m500": ["M500"], "pcont": ["Pcont", "PCONT", "P_cont"], "lext": ["Lext", "EXT_LIKE", "EXTLike"]},
    ),
)
COLUMNS = ["cluster_source", "cluster_z", "cluster_z_spec", "cluster_r500_mpc", "m500", "richness", "pcont", "lext"]


def _one(label, vizier_id, idcols, zcols, zflag, rcols, runit, extra, ra, dec, radius):
    tabs = vizier_query(vizier_id, ra, dec, radius)
    if not tabs:
        return None
    frames = [t.to_pandas() for t in tabs]
    # The cluster table is the one with an r500 column (member/auxiliary tables lack it).
    df = next((f for f in frames if pick(f, rcols) is not None), None)
    if df is None:
        raise KeyError(f"{label}: no table with r500 ({rcols}); tables have {[list(f.columns)[:12] for f in frames]}")
    rv, dv = coordinates(
        df, ["RAJ2000", "RA_ICRS", "_RAJ2000", "RAdeg", "RA"], ["DEJ2000", "DE_ICRS", "_DEJ2000", "DEdeg", "DE", "Dec"]
    )
    idc, zc, fc, rc = pick(df, idcols), pick(df, zcols), pick(df, zflag), pick(df, rcols)
    if zc is None:
        raise KeyError(f"{label}: redshift column missing (tried {zcols}); got {list(df.columns)}")
    out = pd.DataFrame(
        {
            "catalog": CATALOG,
            "catalog_object_id": (
                (label + " " + df[idc].astype("string").str.strip())
                if idc
                else [f"{label} J{a:.4f}{b:+.4f}" for a, b in zip(rv, dv)]
            ),
            "ra": rv,
            "dec": dv,
            "cluster_source": label,
            "cluster_z": numeric(df[zc]),
            "cluster_z_spec": (numeric(df[fc]) == 1) if fc else False,
            "cluster_r500_mpc": numeric(df[rc]) * runit,
        }
    )
    out["object_name"] = out["catalog_object_id"]
    for k, cands in extra.items():
        c = pick(df, cands)
        out[k] = numeric(df[c]) if c else pd.NA
    return out


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    parts, errors = [], []
    for s in SOURCES:
        try:
            p = _one(*s, ra, dec, float(radius_arcmin) + MAX_EXTRA_ARCMIN)
        except Exception as exc:  # noqa: BLE001 - one catalogue failing keeps the other
            errors.append(f"{s[0]}: {exc}"[:300])
            print(f"[galaxy_clusters] {errors[-1]}", flush=True)
            continue
        if p is not None and len(p):
            parts.append(p)
    if errors and not parts:
        raise RuntimeError("; ".join(errors))
    if not parts:
        return empty_frame(*COLUMNS)
    out = pd.concat(parts, ignore_index=True).dropna(subset=["ra", "dec", "cluster_z", "cluster_r500_mpc"])
    return out.drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)


def save(df: pd.DataFrame, path) -> None:
    save_csv(df, path, "Galaxy clusters")
