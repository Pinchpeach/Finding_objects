#!/usr/bin/env python3
"""Literature-only objects (objects whose rows are all NED / SIMBAD / other annotation rows) and why they did not join a survey object (2.62.4).

    python literature_only.py --raw RAWDIR --out OUT [--env KEY=VALUE ...]

Runs Stage 1 on a stored raw folder and, for every object made only of annotation rows, takes the three nearest objects that hold a survey row and judges the pair the way
``association_model.assess_pair`` does: separation against the match radius (min(cap, max(0.15, 5 sigma, 0.6 psf))), the chance-coincidence probability against 0.25 with the density
Stage 1 uses (the larger of the two catalogues' densities, ``_pair_density``) and with the density of the survey rows alone, the score, and whether the nearest object already holds a
TYPED annotation row of the same catalogue (the rule that two typed entries of one annotation catalogue are two objects, so a SIMBAD "QSO" row never joins an object that already holds a SIMBAD "galaxy" row).
``reason`` is the first failing test in that order; ``accepted`` rows joined nothing only because no candidate was accepted or the typed rule blocked them.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import os
import sys
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]


def load_stage1(env: dict):
    for k, v in env.items():
        os.environ[k] = v
    sys.path.insert(0, str(V2 / "Preprocess"))
    spec = importlib.util.spec_from_file_location("s1_lit", V2 / "Preprocess" / "01_source_association.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["s1_lit"] = mod
    spec.loader.exec_module(mod)
    return mod


def is_typed(v) -> bool:
    """``annotation_type`` is '' in Stage 1 when the row has no physical type; a CSV round trip turns '' into NaN, which is truthy."""
    return v is not None and not (isinstance(v, float) and math.isnan(v)) and str(v).strip() != ""


def as_det(r: pd.Series) -> dict:
    d = r.to_dict()
    d["annotation_type"] = str(d["annotation_type"]).strip() if is_typed(d.get("annotation_type")) else ""
    for k in ("pmra", "pmdec", "pmra_error", "pmdec_error", "ref_epoch", "psf_fwhm_arcsec"):
        if k in d and pd.isna(d[k]):
            d[k] = None
    return d


def analyse(assoc: pd.DataFrame, s1) -> pd.DataFrame:
    ann = s1.ANNOTATION_CATALOGS
    cats = assoc.groupby("object_id").catalog.agg(lambda s: set(s))
    lit_ids = [o for o, c in cats.items() if c <= ann]
    survey_ids = [o for o, c in cats.items() if not c <= ann]
    anch = assoc.drop_duplicates("object_id").set_index("object_id")
    # the anchor detection of a survey object: the row of its anchor catalogue (the group position is that row's)
    rows = []
    sv = anch.loc[survey_ids]
    import numpy as np
    from scipy.spatial import cKDTree

    c = np.cos(np.deg2rad(float(assoc.dec.mean())))
    tree = cKDTree(np.c_[sv.object_ra.to_numpy() * c * 3600, sv.object_dec.to_numpy() * 3600])
    typed = assoc[assoc.annotation_type.map(is_typed)].groupby("object_id").catalog.agg(set) if "annotation_type" in assoc else pd.Series(dtype=object)
    for o in lit_ids:
        det_rows = assoc[assoc.object_id == o]
        det = as_det(det_rows.iloc[0])
        dist, ix = tree.query([[det["ra"] * c * 3600, det["dec"] * 3600]], k=min(3, len(sv)))
        best = None
        for k, (dd, i) in enumerate(zip(np.atleast_1d(dist[0]), np.atleast_1d(ix[0]))):
            oid = sv.index[i]
            members = assoc[assoc.object_id == oid]
            a_row = members[members.catalog == members.object_anchor_catalog.iloc[0]].iloc[0]
            a = as_det(a_row)
            a["ra"], a["dec"] = float(a_row.object_ra), float(a_row.object_dec)
            density = s1._pair_density(det, a)
            res = s1.assess_pair(a, det, density)
            res_survey = s1.assess_pair(a, det, a.get("source_density_arcsec2"))
            blocked = bool(det["annotation_type"]) and det["catalog"] in typed.get(oid, set())
            if res["separation_arcsec"] > res["match_radius_arcsec"]:
                reason = "beyond the match radius"
            elif res["chance_probability"] is not None and res["chance_probability"] > 0.25:
                reason = "chance probability > 0.25 with the density used" + (" (survey-only density would accept)" if res_survey["accepted"] else "")
            elif res["association_score"] < 1e-5:
                reason = "score < 1e-5"
            elif blocked:
                reason = "accepted, but the object holds a typed row of the same catalogue"
            else:
                reason = "accepted (joined later or tie)"
            if best is None or res["separation_arcsec"] < best["sep"]:
                best = dict(sep=res["separation_arcsec"], radius=res["match_radius_arcsec"], pchance_used=res["chance_probability"], pchance_survey_density=res_survey["chance_probability"],
                            density_used=density, density_survey=a.get("source_density_arcsec2"), density_own=det.get("source_density_arcsec2"), normalized=res["normalized_separation"],
                            reason=reason, accepted_with_survey_density=bool(res_survey["accepted"]), typed_block=blocked, anchor_catalog=a_row.catalog)  # fmt: skip
        rows.append(dict(object_id=o, catalogs="|".join(sorted(cats[o])), ra=det["ra"], dec=det["dec"], poserr_arcsec=det["poserr_arcsec"], **(best or {})))
    return pd.DataFrame(rows)


def attach_labels(t: pd.DataFrame, cl: pd.DataFrame) -> pd.DataFrame:
    """Keep the objects that exist in the pipeline's classified table (the cone) and add its label columns; nearest object within 0.5''."""
    import numpy as np
    from scipy.spatial import cKDTree

    c = math.cos(math.radians(float(cl.dec.mean())))
    tree = cKDTree(np.c_[cl.ra.to_numpy() * c * 3600, cl.dec.to_numpy() * 3600])
    d, i = tree.query(np.c_[t.ra.to_numpy() * c * 3600, t.dec.to_numpy() * 3600])
    keep = d <= 0.5
    out = t[keep].copy()
    sel = cl.iloc[i[keep]].reset_index(drop=True)
    for col in ("primary_class", "detailed_class", "classification_status", "high_confidence", "catalogs"):
        if col in sel:
            out[("cl_" + col)] = sel[col].to_numpy()
    out["match_sep"] = d[keep]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--env", nargs="*", default=[], help="KEY=VALUE environment switches for Stage 1")
    ap.add_argument("--classified", type=Path, help="classified_objects.csv of the same region: keeps the objects inside its cone and adds its labels (matched by position, 0.5'')")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    s1 = load_stage1(dict(kv.split("=", 1) for kv in a.env))
    s1.run(a.raw, a.out / "source_association.csv")
    assoc = pd.read_csv(a.out / "source_association.csv", low_memory=False)
    t = analyse(assoc, s1)
    if a.classified:
        t = attach_labels(t, pd.read_csv(a.classified, low_memory=False))
    t.to_csv(a.out / "literature_only_objects.csv", index=False)
    print(f"{len(t)} literature-only objects of {assoc.object_id.nunique()}")
    print(t.reason.value_counts().to_string())
    if "cl_primary_class" in t:
        print(pd.crosstab(t.cl_primary_class, t.reason).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
