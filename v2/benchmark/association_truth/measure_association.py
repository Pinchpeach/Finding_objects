#!/usr/bin/env python3
"""Association-stage measurement against COSMOS2020 positions (2.60.9, work order 2026-11-25, task 4 step 1).

What the stage can be judged on.  Until now the only measurement of the association was the shifted-catalogue test
(NWAY, Salvato et al. 2018: move AllWISE / 2MASS by 2', count the rows that still join an object).  It measures chance
coincidence, not whether a real row joined the right object, and it never saw GALEX.  Here the same stage is run on the
26 deep COSMOS fields and judged against COSMOS2020 (Weaver et al. 2022): resolved positions and, for the blend, the
catalogue's own IRAC ch1 / Ks / u fluxes.

    python measure_association.py --fields-root DIR --truth-flux DIR --assoc-dir DIR --out DIR [--variant NAME]

``--assoc-dir`` holds ``<field>/source_association.csv`` of one variant (stage 1 only, from ``run_variant.py``); the
objects table ``<field>/objects_summary.csv`` (top-level objects after the fragment grouping) is used when present.

Definitions (written down before any number was looked at; the field split is ``fields_split.csv``):

  truth reference set R   COSMOS2020 sources with HSC i < 25 (the Legacy Surveys / PS1 / SDSS rows can only see these).
  detection truth id      a row of a resolving catalogue (Legacy Surveys, PS1, SDSS, Gaia, SGA, Galaxy Zoo) takes the
                          nearest source of R within 0.6'' (COSMOS2020 astrometry is ~0.1''); none -> unidentified.
  object truth ids T(O)   the ids of the resolving rows of the object O; when O has none, the nearest source of R to the
                          object's anchor position within 0.6''.
  expected counterpart    for a low-resolution row d (AllWISE: IRAC ch1 flux, PSF FWHM 6.1''; 2MASS: Ks, 2.5''; GALEX:
                          u flux as the NUV proxy, 5.3''): every truth source k within 3 FWHM gets the weight
                          w_k = F_k exp(-r_k^2 / 2 s^2), s = FWHM / 2.355 (the flux it puts into the PSF at the row).
                          dominant = argmax w; acceptable set A(d) = {k : w_k >= 0.25 max w} (the row is a blend of
                          those).  A row without a positive flux source within 3 FWHM has no expected counterpart.
  correct / false / missed
                          row d joined to O: correct when T(O) meets A(d); false when T(O) is known and misses A(d);
                          unknown when T(O) is empty.  Row d not joined (own object or ambiguous_new): missed when some
                          other object has a truth id in A(d), "rightly alone" otherwise.
  strict version          the same with A(d) = {dominant} (shown beside the lenient one).
  merge                   an object whose resolving rows carry two truth ids more than 2'' apart (1'' also listed).
  fragments               truth sources of R with i < 23 that have, within 1.5'', a one-catalogue top-level object
                          besides their best object (best = most catalogues, then nearest).  Top-level objects only
                          (rows grouped under a parent are not counted), unlike ``score_independent_fields``, which
                          counts every row (2.60.9 review).  Needs ``objects_summary.csv``.
  shifted-catalogue test  the pipeline run on a copy with AllWISE moved +2' in Dec, 2MASS -2' in Dec and GALEX +2' in RA
                          (``run_variant.py --shift``): false rate = shifted rows joined to an object anchored by an
                          unshifted catalogue / shifted rows (the 2.49.0 definition).

Everything is per field first, then pooled, with Wilson 95 % intervals and a field-bootstrap interval (fields are the
unit of independence); the calibration and the test half are always shown apart.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
LOWRES = {
    # catalogue: (truth flux column, PSF FWHM arcsec)
    "AllWISE": ("FIRACCH1", 6.1),
    "2MASS PSC": ("FUVISTAKs", 2.5),
    "GALEX AIS": ("FCFHTu", 5.3),
}
RESOLVING = (
    "DESI Legacy Surveys DR10",
    "Pan-STARRS1 DR2 MeanObject",
    "SDSS DR18 PhotoObj",
    "Gaia DR3",
    "SGA-2020",
    "Galaxy Zoo DESI",
)
SHIFTED_CATS = ("AllWISE", "2MASS PSC", "GALEX AIS")
ID_RADIUS = 0.6  # arcsec
REF_MAG = 25.0  # HSC i of the reference set
BLEND_REACH = 3.0  # FWHM
ACCEPT_FRACTION = 0.25
FRAG_MAG = 23.0
FRAG_RADIUS = 1.5


# ------------------------------------------------------------------------------------------ small geometry helpers
def _xyz(ra, dec):
    a, d = np.radians(np.asarray(ra, float)), np.radians(np.asarray(dec, float))
    return np.column_stack([np.cos(d) * np.cos(a), np.cos(d) * np.sin(a), np.sin(d)])


class Sky:
    """Nearest-neighbour / radius queries on the sphere (cKDTree on unit vectors; chord -> arcsec)."""

    def __init__(self, ra, dec):
        from scipy.spatial import cKDTree

        self.tree = cKDTree(_xyz(ra, dec)) if len(ra) else None

    @staticmethod
    def _chord(arcsec):
        return 2.0 * np.sin(np.radians(arcsec / 3600.0) / 2.0)

    @staticmethod
    def _arcsec(chord):
        return np.degrees(2.0 * np.arcsin(np.clip(chord / 2.0, 0, 1))) * 3600.0

    def nearest(self, ra, dec, max_arcsec):
        """(index or -1, separation arcsec) of the nearest point within ``max_arcsec``."""
        n = len(ra)
        if self.tree is None or n == 0:
            return np.full(n, -1), np.full(n, np.inf)
        d, i = self.tree.query(_xyz(ra, dec), distance_upper_bound=self._chord(max_arcsec))
        ok = np.isfinite(d)
        return np.where(ok, i, -1), np.where(ok, self._arcsec(np.where(ok, d, 0)), np.inf)

    def within(self, ra, dec, arcsec):
        """List (per query point) of (indices, separations arcsec) inside the radius."""
        if self.tree is None:
            return [(np.array([], int), np.array([])) for _ in range(len(ra))]
        q = _xyz(ra, dec)
        idx = self.tree.query_ball_point(q, self._chord(arcsec))
        out = []
        for k, ii in enumerate(idx):
            ii = np.asarray(ii, int)
            sep = self._arcsec(np.linalg.norm(self.tree.data[ii] - q[k], axis=1)) if len(ii) else np.array([])
            out.append((ii, sep))
        return out


# ------------------------------------------------------------------------------------------ truth
FIELD_ARCMIN = 6.0  # the fields are 6' cones; the truth file may reach 0.35' further (collect_truth_flux.py --radius)


def load_truth(path: Path, centre=None) -> pd.DataFrame:
    """One field's COSMOS2020 flux table (collect_truth_flux.py): ra, dec, imag, fluxes.

    With ``centre`` = (ra, dec) of the field a column ``r_arcmin`` (distance from it) is added.  The sources beyond the
    field are kept for the search of a low-resolution row's flux-dominant counterpart (3 FWHM, up to 18.3'' around a row
    at the edge) and are left out of every count of truth sources (``inside``)."""
    t = pd.read_csv(path, low_memory=False)
    t = t.rename(columns={"RAJ2000": "ra", "DEJ2000": "dec", "_RAJ2000": "ra", "_DEJ2000": "dec"})
    for c in t.columns:
        if c not in ("ra", "dec"):
            t[c] = pd.to_numeric(t[c], errors="coerce")
    t = t.dropna(subset=["ra", "dec"]).reset_index(drop=True)
    if centre is not None:
        t["r_arcmin"] = np.hypot((t.ra - centre[0]) * np.cos(np.radians(centre[1])), t.dec - centre[1]) * 60.0
    return t


def inside(truth: pd.DataFrame) -> pd.Series:
    """The truth sources inside the field (all of them when the table has no ``r_arcmin``)."""
    return truth["r_arcmin"].le(FIELD_ARCMIN) if "r_arcmin" in truth else pd.Series(True, index=truth.index)


def expected_counterparts(rows: pd.DataFrame, truth: pd.DataFrame, sky: Sky, col: str, fwhm: float):
    """Per low-resolution row: (dominant truth index or -1, acceptable set as a tuple)."""
    s = fwhm / 2.355
    flux = truth[col].to_numpy(float)
    hits = sky.within(rows.ra.to_numpy(float), rows.dec.to_numpy(float), BLEND_REACH * fwhm)
    dom, acc = [], []
    for ii, sep in hits:
        w = (
            np.where(np.isfinite(flux[ii]) & (flux[ii] > 0), flux[ii], 0.0) * np.exp(-0.5 * (sep / s) ** 2)
            if len(ii)
            else np.array([])
        )
        if not len(ii) or not (w > 0).any():
            dom.append(-1)
            acc.append(())
            continue
        top = w.max()
        dom.append(int(ii[int(w.argmax())]))
        acc.append(tuple(int(x) for x in ii[w >= ACCEPT_FRACTION * top]))
    return dom, acc


# ------------------------------------------------------------------------------------------ one field
def measure_field(assoc: pd.DataFrame, truth: pd.DataFrame, shifted_from: pd.DataFrame | None = None) -> dict:
    ref = truth[truth["HSCimagAuto"] < REF_MAG]  # keeps the index of ``truth``: one id space for every truth id
    ref_ids = ref.index.to_numpy()
    ref_sky = Sky(ref.ra, ref.dec)
    full_sky = Sky(truth.ra, truth.dec)

    a = assoc.copy()
    res = a.catalog.isin(RESOLVING)
    a["truth_id"] = -1
    if res.any():
        i, _ = ref_sky.nearest(a.loc[res, "ra"].to_numpy(float), a.loc[res, "dec"].to_numpy(float), ID_RADIUS)
        a.loc[res, "truth_id"] = np.where(i >= 0, ref_ids[np.maximum(i, 0)], -1)

    # object truth ids
    obj = a.groupby("object_id")
    T = {}
    for oid, g in obj:
        ids = set(int(x) for x in g.truth_id[(g.catalog.isin(RESOLVING)) & (g.truth_id >= 0)])
        T[oid] = ids
    anchors = a.drop_duplicates("object_id").set_index("object_id")[["object_ra", "object_dec"]]
    empty = [oid for oid, ids in T.items() if not ids]
    if empty:
        i, _ = ref_sky.nearest(
            anchors.loc[empty, "object_ra"].to_numpy(float), anchors.loc[empty, "object_dec"].to_numpy(float), ID_RADIUS
        )
        for oid, k in zip(empty, i):
            if k >= 0:
                T[oid] = {int(ref_ids[k])}
    by_truth: dict[int, set] = {}
    for oid, ids in T.items():
        for k in ids:
            by_truth.setdefault(k, set()).add(oid)

    out: dict = {"n_rows": int(len(a)), "n_objects": int(a.object_id.nunique())}
    detail: list = []
    members = {
        cat: {oid: g[["ra", "dec"]].to_numpy(float) for oid, g in a[a.catalog == cat].groupby("object_id")}
        for cat in LOWRES
    }
    # low-resolution rows
    for cat, (col, fwhm) in LOWRES.items():
        d = a[a.catalog == cat]
        if not len(d) or col not in truth:
            continue
        dom, acc = expected_counterparts(d, truth, full_sky, col, fwhm)
        matched = (d.association_status == "matched").to_numpy()
        rec = dict(rows=len(d), matched=int(matched.sum()), no_expected=0, correct=0, false=0, unknown=0, missed=0, rightly_alone=0,
                   s_correct=0, s_false=0, s_missed=0)  # fmt: skip
        for (_, r), dm, ac, m in zip(d.iterrows(), dom, acc, matched):
            if dm < 0:
                # no truth source with a positive flux within reach: there is nothing to join, so a join is false
                rec["no_expected"] += 1
                rec["no_expected_joined"] = rec.get("no_expected_joined", 0) + int(m)
                detail.append(dict(catalog=cat, outcome="no_counterpart", nsep=r.normalized_separation if m else np.nan,
                                   conf=r.association_confidence, any_holder=False, joined=bool(m),
                                   lr=getattr(r, "likelihood_ratio", np.nan), lr_sum=getattr(r, "lr_sum_candidates", np.nan),
                                   sep_dom=np.nan, n_acc=0, poserr=r.poserr_arcsec,
                                   sigma=r.combined_sigma_arcsec if m else np.nan, density=r.source_density_arcsec2,
                                   cand=r.candidate_count, field_row=r.detection_id, ra=r.ra, dec=r.dec,
                                   status=r.association_status, blocked=False, blocker_sep=np.nan))  # fmt: skip
                continue
            acc_set = set(ac)
            own = r.object_id
            holders = set()  # objects that hold a truth source of the acceptable set (the row's own object included)
            for k in acc_set:
                holders |= by_truth.get(k, set())
            if m:
                ids = T.get(r.object_id, set())
                if not ids:
                    outcome = "unknown"
                    rec["unknown"] += 1
                elif ids & acc_set:
                    outcome = "correct"
                    rec["correct"] += 1
                else:
                    outcome = "false"
                    rec["false"] += 1
                if ids:
                    rec["s_correct" if dm in ids else "s_false"] += 1
            else:
                others = holders - {own}
                if others:
                    outcome = "missed"
                    rec["missed"] += 1
                else:
                    outcome = "rightly_alone"
                    rec["rightly_alone"] += 1
                if {o for o in by_truth.get(dm, ()) if o != own}:
                    rec["s_missed"] += 1
            dra = (truth.ra.iat[dm] - r.ra) * np.cos(np.radians(r.dec)) * 3600.0
            ddec = (truth.dec.iat[dm] - r.dec) * 3600.0
            # an unjoined row whose counterpart's object already holds a row of the same catalogue was blocked by the
            # one-row-per-catalogue rule; how far is that other row from the truth source?
            blocked, bsep = False, np.nan
            if not m:
                # every blocking object, in a fixed order; the closest blocking row counts (2.60.9 review: the first
                # member of a set depended on the hash seed)
                for o in sorted(holders - {own}, key=str):
                    pos = members[cat].get(o)
                    if pos is not None and len(pos):
                        bd = (
                            np.hypot(
                                (truth.ra.iat[dm] - pos[:, 0]) * np.cos(np.radians(r.dec)),
                                truth.dec.iat[dm] - pos[:, 1],
                            )
                            * 3600.0
                        )
                        blocked, bsep = True, float(np.fmin(bsep, bd.min()))
            detail.append(dict(catalog=cat, outcome=outcome, nsep=r.normalized_separation if m else np.nan,
                               # an unjoined row's own object is no association opportunity (as for "missed")
                               conf=r.association_confidence, any_holder=bool(holders if m else holders - {own}), joined=bool(m),
                               sep_dom=float(np.hypot(dra, ddec)), n_acc=len(acc_set), poserr=r.poserr_arcsec,
                               sigma=r.combined_sigma_arcsec if m else np.nan, density=r.source_density_arcsec2,
                               cand=r.candidate_count, field_row=r.detection_id, lr=getattr(r, 'likelihood_ratio', np.nan),
                               lr_sum=getattr(r, 'lr_sum_candidates', np.nan), ra=r.ra, dec=r.dec, status=r.association_status,
                               blocked=blocked, blocker_sep=bsep))  # fmt: skip
        out[cat] = rec
    # merges
    merges1 = merges2 = 0
    for oid, g in obj:
        ids = sorted(int(x) for x in g.truth_id[(g.catalog.isin(RESOLVING)) & (g.truth_id >= 0)].unique())
        if len(ids) < 2:
            continue
        p = truth.loc[ids, ["ra", "dec"]].to_numpy(float)
        v = _xyz(p[:, 0], p[:, 1])
        ch = np.linalg.norm(v[:, None, :] - v[None, :, :], axis=2).max()
        sep = float(Sky._arcsec(ch))
        merges1 += sep > 1.0
        merges2 += sep > 2.0
    out["merged_objects_gt1"], out["merged_objects_gt2"] = int(merges1), int(merges2)
    out["objects_with_resolved_rows"] = int(sum(1 for v in T.values() if v))
    out["_detail"] = pd.DataFrame(detail)
    # shifted-catalogue test: needs the stage-1 table of the shifted run
    if shifted_from is not None:
        s = shifted_from
        for cat in SHIFTED_CATS:
            d = s[s.catalog == cat]
            if not len(d):
                continue
            m = (d.association_status == "matched") & ~d.object_anchor_catalog.isin(SHIFTED_CATS)
            any_unshifted = d.object_id.isin(set(s.object_id[~s.catalog.isin(SHIFTED_CATS)]))  # the object holds a row of an unshifted catalogue, whoever anchors it (METRICS.md)
            out.setdefault(cat, {}).update(shift_rows=int(len(d)), shift_false=int(m.sum()), shift_any=int(any_unshifted.sum()))
            out.setdefault("_shift_nsep", {})[cat] = (
                int(len(d)),
                pd.to_numeric(d.normalized_separation[m], errors="coerce").dropna().to_numpy(),
            )
    return out


def fragments(summary: pd.DataFrame, truth: pd.DataFrame) -> dict:
    """Fragment count of ``score_independent_fields.field_matches`` on COSMOS2020 sources of R with i < FRAG_MAG, and
    what the extra single-catalogue objects are: the same truth source again (a duplicate or shred of it), another
    truth source (a real neighbour, not a fragment) or no truth source within ID_RADIUS (a spurious row)."""
    ref = truth[(truth["HSCimagAuto"] < FRAG_MAG) & inside(truth)].reset_index(drop=True)  # 2.60.11: inside 6' only
    top = summary
    nc = top.catalogs.fillna("").str.count(r"\|").add(1).to_numpy()
    sky = Sky(top.ra.to_numpy(float), top.dec.to_numpy(float))
    full = Sky(truth.ra, truth.dec)
    obj_truth, _ = full.nearest(top.ra.to_numpy(float), top.dec.to_numpy(float), ID_RADIUS)
    ref_in_full = full.nearest(ref.ra.to_numpy(float), ref.dec.to_numpy(float), 0.05)[0]
    hits = sky.within(ref.ra.to_numpy(float), ref.dec.to_numpy(float), FRAG_RADIUS)
    n_with = n_extra = n_matched = same = other = none = 0
    by_cat: dict[str, int] = {}
    for k, (ii, sep) in enumerate(hits):
        if not len(ii):
            continue
        n_matched += 1
        order = np.lexsort((sep, -nc[ii]))
        best = ii[order[0]]
        extra_idx = [j for j in ii if j != best and nc[j] == 1]
        if nc[best] == 1:  # the best one is a single-catalogue object too: the others still count, as in the score
            pass
        n_with += bool(extra_idx)
        n_extra += len(extra_idx)
        for j in extra_idx:
            t = obj_truth[j]
            if t < 0:
                none += 1
            elif t == ref_in_full[k]:
                same += 1
            else:
                other += 1
            c = str(top.catalogs.iloc[j])
            by_cat[c] = by_cat.get(c, 0) + 1
    return dict(truth_sources=int(len(ref)), truth_with_object=n_matched, truth_with_fragments=int(n_with),
                extra_fragment_objects=int(n_extra), extra_same_truth=same, extra_other_truth=other, extra_no_truth=none,
                top_level_objects=int(len(top)), by_catalog=by_cat)  # fmt: skip


# ------------------------------------------------------------------------------------------ pooling
def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (100 * (c - h), 100 * (c + h))


def boot(per_field: list[dict], num, den, n=2000, seed=0):
    """Field-bootstrap 95 % interval of sum(num)/sum(den) in percent."""
    rng = np.random.default_rng(seed)
    a = np.array([[f.get(num, 0), f.get(den, 0)] for f in per_field], float)
    if not len(a) or a[:, 1].sum() == 0:
        return (np.nan, np.nan)
    idx = rng.integers(0, len(a), (n, len(a)))
    s = a[idx].sum(axis=1)
    ok = s[:, 1] > 0
    r = 100 * s[ok, 0] / s[ok, 1]
    return (float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5)))


def pool(rows: list[dict], split: pd.DataFrame, label: str) -> pd.DataFrame:
    """One line per catalogue and half: counts and rates with intervals."""
    out = []
    for half in ("calibration", "test", "all"):
        names = set(split.name) if half == "all" else set(split[split.split == half].name)
        sel = [r for r in rows if r["field"] in names]
        for cat in LOWRES:
            f = [r[cat] for r in sel if cat in r]
            if not f:
                continue
            tot = {k: sum(x.get(k, 0) for x in f) for k in f[0]}
            decided_m = tot["correct"] + tot["false"]
            expected = tot["rows"] - tot["no_expected"]
            rec = dict(variant=label, half=half, catalog=cat, fields=len(f), rows=tot["rows"], with_expected=expected,
                       matched=tot["matched"], correct=tot["correct"], false=tot["false"], unknown=tot["unknown"],
                       missed=tot["missed"], rightly_alone=tot["rightly_alone"])  # fmt: skip
            rec["false_pct_of_matched_known"] = round(100 * tot["false"] / decided_m, 2) if decided_m else np.nan
            lo, hi = wilson(tot["false"], decided_m)
            rec["false_wilson"] = f"{lo:.1f}-{hi:.1f}"
            bl, bh = boot([dict(n=x["false"], d=x["correct"] + x["false"]) for x in f], "n", "d")
            rec["false_boot"] = f"{bl:.1f}-{bh:.1f}"
            alone = tot["missed"] + tot["rightly_alone"]
            rec["missed_pct_of_unjoined"] = round(100 * tot["missed"] / alone, 2) if alone else np.nan
            rec["missed_pct_of_expected"] = round(100 * tot["missed"] / expected, 2) if expected else np.nan
            sd = tot["s_correct"] + tot["s_false"]
            rec["strict_false_pct"] = round(100 * tot["s_false"] / sd, 2) if sd else np.nan
            if "shift_rows" in tot and tot["shift_rows"]:
                rec["shifted_false_pct"] = round(100 * tot["shift_false"] / tot["shift_rows"], 2)
            # 2.62.7 (METRICS.md): columns that do not depend on who anchors an object; appended, the order of the old columns is unchanged
            rec["right_object"] = tot["correct"] + tot["rightly_alone"]
            rec["right_object_pct_of_expected"] = round(100 * rec["right_object"] / expected, 2) if expected else np.nan
            if "shift_rows" in tot and tot["shift_rows"] and "shift_any" in tot:
                rec["shifted_any_pct"] = round(100 * tot["shift_any"] / tot["shift_rows"], 2)
            out.append(rec)
    return pd.DataFrame(out)


def curves(details: pd.DataFrame, shifts: list[dict], split: pd.DataFrame, grid=None) -> pd.DataFrame:
    """False / recall / shifted-catalogue false rate as the cut on the normalised separation k moves (static cut: the
    rows of a run without a cut that lie beyond k are taken as not joined).  ``details`` has one line per low-resolution
    row (field, catalog, outcome, nsep, any_holder, joined); ``shifts`` one dict per field with the shifted rows' nsep.
    """
    grid = grid if grid is not None else [round(x, 2) for x in np.arange(0.5, 6.01, 0.25)]
    out = []
    for half in ("calibration", "test", "all"):
        names = set(split.name) if half == "all" else set(split[split.split == half].name)
        d = details[details.field.isin(names)]
        for cat in LOWRES:
            x = d[d.catalog == cat]
            if x.empty:
                continue
            n_assoc = int(x.any_holder.sum())  # rows whose expected counterpart has an object to join
            sh_rows = sum(f[cat][0] for f in shifts if f["field"] in names and cat in f)
            sh_n = [f[cat][1] for f in shifts if f["field"] in names and cat in f]
            sh_n = np.concatenate(sh_n) if sh_n else np.array([])
            for k in grid + [float("inf")]:
                j = x[x.joined & (x.nsep <= k)]
                c, f = int((j.outcome == "correct").sum()), int((j.outcome == "false").sum())
                out.append(dict(half=half, catalog=cat, k=k, joined=len(j), correct=c, false=f,
                                false_pct=round(100 * f / (c + f), 2) if c + f else np.nan,
                                recall_pct=round(100 * c / n_assoc, 2) if n_assoc else np.nan,
                                shifted_false_pct=round(100 * int((sh_n <= k).sum()) / sh_rows, 2) if sh_rows else np.nan))  # fmt: skip
    return pd.DataFrame(out)


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--truth-flux", type=Path, required=True, help="DIR/<field>.csv.gz from collect_truth_flux.py")
    ap.add_argument("--assoc-dir", type=Path, required=True, help="DIR/<field>/source_association.csv of the variant")
    ap.add_argument("--shifted-dir", type=Path, help="same for the shifted-catalogue run")
    ap.add_argument("--variant", default="base")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    split = pd.read_csv(HERE / "fields_split.csv")
    a.out.mkdir(parents=True, exist_ok=True)
    rows, frag, details, shifts = [], [], [], []
    for name in split.name:
        f_assoc = a.assoc_dir / name / "source_association.csv"
        f_truth = a.truth_flux / f"{name}.csv.gz"
        if not f_assoc.exists() or not f_truth.exists():
            print("skip", name, f_assoc.exists(), f_truth.exists(), file=sys.stderr)
            continue
        assoc = pd.read_csv(f_assoc, low_memory=False, dtype={"catalog_object_id": "string"})
        truth = load_truth(f_truth, (split.set_index("name").ra[name], split.set_index("name").dec[name]))
        sh = None
        if a.shifted_dir and (a.shifted_dir / name / "source_association.csv").exists():
            sh = pd.read_csv(a.shifted_dir / name / "source_association.csv", low_memory=False)
        r = measure_field(assoc, truth, sh)
        r["field"] = name
        det = r.pop("_detail")
        det["field"] = name
        details.append(det)
        shifts.append({"field": name, **r.pop("_shift_nsep", {})})
        f_sum = a.assoc_dir / name / "objects_summary.csv"
        if f_sum.exists():
            fr = fragments(pd.read_csv(f_sum, low_memory=False), truth)
            fr["field"] = name
            frag.append(fr)
            r["summary_rows"] = fr["top_level_objects"]
        rows.append(r)
        print(name, {k: v for k, v in r.items() if not isinstance(v, dict)}, flush=True)
    table = pool(rows, split, a.variant)
    cv = curves(pd.concat(details, ignore_index=True), shifts, split)
    cv.insert(0, "variant", a.variant)
    cv.to_csv(a.out / f"cut_curves_{a.variant}.csv", index=False)
    pd.concat(details, ignore_index=True).to_csv(a.out / f"rows_{a.variant}.csv.gz", index=False)
    table.to_csv(a.out / f"false_missed_{a.variant}.csv", index=False)
    (a.out / f"per_field_{a.variant}.json").write_text(json.dumps(rows, indent=1, default=int))
    pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, dict)} for r in rows]).to_csv(
        a.out / f"structure_{a.variant}.csv", index=False
    )
    if frag:
        fr = pd.DataFrame(frag).merge(split[["name", "split"]], left_on="field", right_on="name").drop(columns="name")
        fr.to_csv(a.out / f"fragments_{a.variant}.csv", index=False)
        print(
            fr.groupby("split")[
                [
                    "truth_sources",
                    "truth_with_object",
                    "truth_with_fragments",
                    "extra_fragment_objects",
                    "top_level_objects",
                ]
            ].sum()
        )
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(table)
    RI.write_args(a, ('truth_flux', 'assoc_dir', 'shifted_dir'), t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
