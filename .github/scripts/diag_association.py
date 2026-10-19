"""Diagnostics for two UNKNOWN populations of a field run (no pipeline change).

1. Pan-STARRS1-only objects with a Legacy Surveys detection within 2":
   why the PS1 row did not join the LS object (replays assess_pair).
2. SIMBAD/NED-only objects: NED type, name prefix (originating catalogue),
   position in the field and the nearest survey detection.

usage: python diag_association.py WORK_DIR RA DEC RADIUS_ARCMIN
"""

import re
import sys
from collections import Counter

import numpy as np
import pandas as pd

work, RA0, DEC0, RAD = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
sys.path.insert(0, "v2/Preprocess")
import association_model as am  # noqa: E402

d = pd.read_csv(f"{work}/classified_objects.csv", low_memory=False)
a = pd.read_csv(f"{work}/source_association.csv", low_memory=False, dtype={"catalog_object_id": "string"})
PS1, LS = "Pan-STARRS1 DR2 MeanObject", "DESI Legacy Surveys DR10"
LIT = {"SIMBAD", "NED"}
cosd = np.cos(np.radians(DEC0))
cats_of = a.groupby("object_id").catalog.agg(lambda s: frozenset(s))
anchor_cat = a.groupby("object_id").object_anchor_catalog.first()


def det(r):
    return {k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in r.items()}


def sep(r, rows):
    return np.hypot((rows.ra.to_numpy() - r.ra) * cosd, rows.dec.to_numpy() - r.dec) * 3600


def q(x, ps=(0.1, 0.25, 0.5, 0.75, 0.9)):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return np.round(np.quantile(x, ps), 2).tolist() if len(x) else None


print("\n=== A. PS1-only objects with an LS detection within 2 arcsec ===")
ps_only = set(cats_of[cats_of.map(lambda c: c - LIT == {PS1})].index)
pa = a[a.catalog.eq(PS1) & a.object_id.isin(ps_only)]
la = a[a.catalog.eq(LS)]
ls_type = d.set_index("object_id").get("desi_legacy_surveys_dr10__type", pd.Series(dtype=object))
reasons, rows = Counter(), []
for _, r in pa.iterrows():
    s = sep(r, la)
    if not len(s) or s.min() >= 2.0:
        continue
    j = int(np.argmin(s))
    l = la.iloc[j]
    p, L = det(r.to_dict()), det(l.to_dict())
    res = am.assess_pair(L, p, p.get("source_density_arcsec2"))
    held_ps1 = PS1 in cats_of.get(l.object_id, frozenset())
    if held_ps1:
        other = a[a.object_id.eq(l.object_id) & a.catalog.eq(PS1)].iloc[0]
        why = "LS object already holds another PS1 row"
        extra = f"other PS1 {sep(r, other.to_frame().T)[0]:.2f}\" from this one"
    elif "ambiguous_new" in (r.association_status, l.association_status):
        # Detections are placed in anchor order (smaller poserr first), so the
        # later of the two made the decision; record which one was ambiguous.
        who = "PS1" if r.association_status == "ambiguous_new" else "LS"
        why, extra = f"ambiguous ({who} row, {int(r.candidate_count if who == 'PS1' else l.candidate_count)} candidates)", ""
    elif not res["accepted"]:
        if res["separation_arcsec"] > res["match_radius_arcsec"]:
            why = "beyond match radius"
        elif (res.get("chance_probability") or 0) > 0.25:
            why = "chance probability > 0.25"
        else:
            why = "score < 1e-5"
        extra = ""
    else:
        why, extra = "accepted vs LS row itself", f"LS group anchor {anchor_cat.get(l.object_id)}"
    reasons[why] += 1
    rows.append(
        {
            "why": why,
            "sep": round(float(s[j]), 2),
            "sigma": round(res["combined_sigma_arcsec"], 3),
            "radius": round(res["match_radius_arcsec"], 2),
            "ps1_poserr": p.get("poserr_arcsec"),
            "ls_poserr": round(L.get("poserr_arcsec") or np.nan, 3),
            "ls_type": ls_type.get(l.object_id),
            "nDet": d.set_index("object_id").get("pan_starrs1_dr2_meanobject__nDetections", pd.Series(dtype=float)).get(r.object_id),
            "ps1_r": d.set_index("object_id").get("std_mag__ps1_r", pd.Series(dtype=float)).get(r.object_id),
            "ls_r": d.set_index("object_id").get("std_mag__ls_r", pd.Series(dtype=float)).get(l.object_id),
            "ls_obj_cats": "|".join(sorted(cats_of.get(l.object_id, ()))),
            "extra": extra,
        }
    )
t = pd.DataFrame(rows)
print("rows:", len(t), "| reasons:", dict(reasons))
if len(t):
    t["sep_over_sigma"] = (t.sep / t.sigma).round(1)
    t["dmag_r"] = (t.ps1_r - t.ls_r).round(2)
    for why, g in t.groupby(t.why.str.replace(r" \(.*", "", regex=True)):
        print(f"\n-- {why}: n={len(g)}")
        print("  sep quantiles", q(g.sep), "| sep/sigma", q(g.sep_over_sigma), "| radius", q(g.radius))
        print("  PS1 poserr", q(g.ps1_poserr), "| LS poserr", q(g.ls_poserr))
        print("  LS type", g.ls_type.value_counts(dropna=False).to_dict(), "| nDet", g.nDet.value_counts(dropna=False).to_dict())
        print("  PS1 r - LS r quantiles", q(g.dmag_r), "| PS1 r", q(g.ps1_r))
        print("  LS object catalogues:", g.ls_obj_cats.str.replace("|", ",").value_counts().head(5).to_dict())
    print("\nsample:")
    print(t.sort_values("sep").head(25).to_string(index=False))
    held = t[t.why.str.startswith("LS object already")]
    if len(held):
        print("\nother-PS1 separations:", held.extra.str.extract(r"([0-9.]+)")[0].astype(float).describe().round(2).to_dict())

print("\n=== B. SIMBAD/NED-only objects ===")
lit_only = set(cats_of[cats_of.map(lambda c: bool(c) and c <= LIT)].index)
lo = d[d.object_id.isin(lit_only)]
print("objects:", len(lo), "| status", lo.classification_status.value_counts().to_dict())
print("catalogues:", lo.catalogs.value_counts().to_dict())
print("NED Type:", lo.get("ned__Type", pd.Series(dtype=object)).value_counts(dropna=False).head(20).to_dict())
print("SIMBAD otype:", lo.get("simbad__otype", pd.Series(dtype=object)).value_counts().head(15).to_dict())
la_lit = a[a.object_id.isin(lit_only)]
pref = la_lit.object_name.astype(str).str.extract(r"^([A-Za-z0-9+\-]*?[A-Za-z]+)[ _]?[J0-9+\-]")[0].fillna("?")
print("name prefix (originating catalogue):", Counter(zip(la_lit.catalog, pref)).most_common(30))
r_off = np.hypot((la_lit.object_ra - RA0) * cosd, la_lit.object_dec - DEC0) * 60
print(f"offset from field centre (arcmin, radius {RAD}):", q(r_off), "| beyond 0.95R:", int((r_off > 0.95 * RAD).sum()))
surv = a[~a.catalog.isin(LIT)]
nearest, ncat, nrad = [], [], []
for _, r in la_lit.iterrows():
    s = sep(r, surv)
    if not len(s):
        continue
    j = int(np.argmin(s))
    nearest.append(s[j])
    ncat.append(surv.catalog.iloc[j])
    res = am.assess_pair(det(surv.iloc[j].to_dict()), det(r.to_dict()), None)
    nrad.append(res["match_radius_arcsec"])
nearest, ncat, nrad = np.array(nearest), np.array(ncat), np.array(nrad)
if len(nearest):
    bins = [0, 1, 2, 3, 5, 10, 30, 1e9]
    print("nearest survey detection (arcsec) bins", bins[:-1], np.histogram(nearest, bins)[0].tolist())
    print("nearest within 10\" but beyond match radius:", int(((nearest < 10) & (nearest > nrad)).sum()),
          "| nearest catalogue for those:", Counter(ncat[(nearest < 10) & (nearest > nrad)]).most_common(8))
    print("nearest catalogue overall:", Counter(ncat).most_common(10))
    by = pd.DataFrame({"type": lo.set_index("object_id").get("ned__Type", pd.Series(dtype=object)).reindex(la_lit.object_id).to_numpy(), "sep": nearest})
    print("nearest-sep median by NED Type:", by.groupby("type", dropna=False).sep.agg(["count", "median"]).round(1).sort_values("count", ascending=False).head(12).to_dict("index"))
ned_cols = [c for c in lo.columns if c.startswith("ned__")]
print("NED columns:", ned_cols[:30])
for c in ("ned__Redshift", "ned__Photometry Points", "ned__References", "ned__Separation"):
    if c in lo:
        v = pd.to_numeric(lo[c], errors="coerce")
        print(f"{c}: finite {int(v.notna().sum())} quantiles {q(v)}")
print("\nsample:")
cols = [c for c in ("designation", "catalogs", "ned__Type", "simbad__otype", "ned__Redshift", "ned__Photometry Points") if c in lo]
print(lo[cols].head(30).to_string(index=False))
