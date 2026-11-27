#!/usr/bin/env python3
"""Recall of the QSO label on spectroscopically confirmed quasars behind the Galactic plane (2.61.2).  Measurement only.

    python score_lowlat_qso.py compact --work DIR --out DIR
    python score_lowlat_qso.py score --fields DIR/<name>/objects.csv.gz ... --regions fields_lowlat.csv \\
        --truth lowlat_truth.csv.gz --out DIR

``compact`` keeps from a pipeline run (``classified_objects.csv``) the columns needed here, plus the rules that spoke
for each class (``rules_QSO`` ...), so the raw products can be deleted.  ``score`` reads the compact records of the
regions of ``fields_lowlat.csv`` and the truth table of ``build_lowlat_truth.py`` and writes (all in ``--out``):

  recall_summary.csv        QSO recall (primary_class == QSO among the quasars with an object) with the Wilson 95 %
                            interval, overall and by |b|, E(B-V), PS1 i magnitude, redshift, sample and R90 sky
  labels.csv                the label counts of the quasars (QSO / GALAXY / STAR / UNKNOWN / no object) by |b|
  missed.csv                every quasar that did not get the QSO label: the label, the cause (below), the numbers behind it
  causes.csv                the causes counted by |b| and by label
  qso_density.csv           the objects labelled QSO per square degree of the cones, other than the sample quasars (all, and
                            with PS1 i < 19.5, the range of the sample), and qso_other_objects.csv: those objects
  contaminants.csv          what the 19 non-quasars of the Fu et al. 2022 candidate list were labelled (and what the stored
                            factors would have given without a prior)
  counterfactual_recall.csv the QSO recall the stored factors would give without the position prior, the QSO magnitude prior
                            or both (labels set by a rule or an abstention are kept; the confidence gates are ignored): what
                            a prior costs in recall, not a recommendation: the cost in false QSO labels is not measured here
  regions.csv               one row per region: objects, QSO-labelled objects, truth quasars in the cone, archive status
  coverage.json             regions and quasars scored against the list; a run with a missing region is marked INCOMPLETE
                            (its quasars are REGION_MISSING in per_truth.csv and in no recall denominator)
                            and one where a region was classified without a key archive (run_archives_status of the
                            pipeline, or the copied collection summary for a region without rows) is marked DEGRADED

Causes of a miss, first match wins:
  no_object          no object within ``MATCH_ARCSEC`` of the quasar (not detected in any catalogue, or not resolved)
  rule_decided       ``classification_basis`` is not ``evidence``: a rule other than the fused evidence set the label
                     (Gaia motion, near-infrared star, member rules ...); the basis is named
  abstained          the label is UNKNOWN: ``classification_status`` (LOW_CONFIDENCE, CONFLICT, NO_EVIDENCE ...); split by
                     whether the evidence alone (``p_*_training_prior``) pointed at QSO
  evidence           the fused evidence alone (``p_*_training_prior``) does not point at QSO
  position_prior     the evidence points at QSO and the position factor (``prior_position`` on GALAXY and QSO: the local Gaia
                     density where it can be measured, else latitude x Magellanic Clouds; the detail says which) turns it
  qso_magnitude      ... the QSO magnitude prior (``prior_qso_magnitude``) turns it
  qso_veto           ... the veto factor (``prior_qso_veto``) turns it
  faint_star_galaxy  ... the faint STAR:GALAXY prior moves mass out of QSO's neighbours; the QSO label is lost by another factor
  other              none of the above reproduces the decision (the layers are replayed from the stored factors, 2.52.0)
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

MATCH_ARCSEC = 2.0
MISSING = "REGION_MISSING"  # label of a truth object whose region has no compact record
# per_region columns (a run where no region has a record still has them, so the density and coverage code can run)
# qso_other_objects columns (a run without such objects still has them)
OTHER_COLS = ["region", "stratum", "kind", "object_id", "ra", "dec", "ps1_i", "p_qso", "p_qso_evidence", "basis", "n_catalogs"]
REGION_COLS = ["name", "stratum", "kind", "status", "archives_status", "archives_missing", "objects", "qso_labelled",
               "qso_other", "objects_i_lt_195", "qso_other_i_lt_195", "truth_in_cone", "area_deg2"]  # fmt: skip
CLASSES = ("STAR", "GALAXY", "QSO")
KEEP = [
    "object_id", "ra", "dec", "catalogs", "std_ebv", "primary_class", "primary_confidence", "primary_margin",
    "classification_status", "classification_basis", "best_candidate_class", "secondary_class", "secondary_class_reason",
    "parent_object_id", "component_role", "high_confidence", "evidence_count", "evidence_conflict",
    "p_star", "p_galaxy", "p_qso", "p_star_training_prior", "p_galaxy_training_prior", "p_qso_training_prior",
    "prior_gaia_density", "prior_position", "prior_qso_magnitude", "prior_qso_veto", "prior_faint_star",
    "prior_faint_galaxy", "prior_layer", "run_archives_status", "run_archives_missing",
]  # fmt: skip
B_BINS = [(0, 5), (5, 10), (10, 15), (15, 20.0001)]
EBV_BINS = [(0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 99)]
I_BINS = [(0, 17.5), (17.5, 18.5), (18.5, 19.0), (19.0, 19.5), (19.5, 99)]
Z_BINS = [(0, 1), (1, 2), (2, 3), (3, 9)]


def wilson(k: int, n: int, z: float = 1.959964):
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def galactic_bl(ra, dec):
    r, d = np.radians(np.asarray(ra, float)), np.radians(np.asarray(dec, float))
    x, y, z = np.cos(d) * np.cos(r), np.cos(d) * np.sin(r), np.sin(d)
    gx = -0.0548755604 * x - 0.8734370902 * y - 0.4838350155 * z
    gy = +0.4941094279 * x - 0.4448296300 * y + 0.7469822445 * z
    gz = -0.8676661490 * x - 0.1980763734 * y + 0.4559837762 * z
    return np.degrees(np.arctan2(gy, gx)) % 360.0, np.degrees(np.arcsin(np.clip(gz, -1, 1))), np.degrees(np.arccos(np.clip(gx, -1, 1)))


def r90_sky(ra, dec) -> np.ndarray:
    """Assef et al. 2018 R90 footprint as the pipeline uses it (04_build_evidence._r90_sky): |b| > 10 deg and more than
    30 deg from the Galactic Centre."""
    _, b, gc = galactic_bl(ra, dec)
    return (np.abs(b) > 10.0) & (gc > 30.0)


def compact(work: Path, out: Path) -> None:
    work, out = Path(work), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    head = pd.read_csv(work / "classified_objects.csv", nrows=0).columns
    use = [c for c in KEEP if c in head] + (["evidence_json"] if "evidence_json" in head else [])
    d = pd.read_csv(work / "classified_objects.csv", usecols=use, low_memory=False)
    rules = {c: [] for c in CLASSES}
    every = []
    for raw in d.get("evidence_json", pd.Series([""] * len(d))):
        try:
            ev = json.loads(raw) if isinstance(raw, str) else []
        except ValueError:
            ev = []
        per = {c: set() for c in CLASSES}
        allr = set()
        for e in ev:
            if e.get("rule_id"):
                allr.add(f"{e['rule_id']}:{e.get('class', '')}")  # e.g. WISE-AGN-R90-001:EXTRAGALACTIC (a rule can speak for a group)
                if e.get("class") in per:
                    per[e["class"]].add(str(e["rule_id"]))
        for c in CLASSES:
            rules[c].append(";".join(sorted(per[c])))
        every.append(";".join(sorted(allr)))
    for c in CLASSES:
        d[f"rules_{c}"] = rules[c]
    d["rules_all"] = every
    d = d.drop(columns=["evidence_json"], errors="ignore")
    d.to_csv(out / "objects.csv.gz", index=False)
    for f in ("collection_summary", "catalog_coverage.json", "pipeline_summary.csv"):
        for p in list(work.glob(f"**/{f}*")) + list(work.glob(f"**/{f}")):
            if p.is_file() and p.stat().st_size < 5_000_000:
                (out / p.name).write_bytes(p.read_bytes())
                break


def _coverage_module():
    """``v2/catalog_coverage.py`` (which archives are key, which statuses are failures), loaded by path."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("v2_catalog_coverage", Path(__file__).resolve().parents[2] / "catalog_coverage.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def region_archives(o: pd.DataFrame, region_dir: Path) -> tuple[str, str]:
    """(status, missing) of a region's collection, as ``catalog_coverage`` writes them into every result row
    (``run_archives_status``: complete / key_archives_missing / archives_missing / degraded / unknown).  A region without
    rows (no detections) has no value there; then the copied collection summary is read: a failed query (error,
    timeout) is a failure, an empty answer or an archive outside its footprint is not."""
    st = o["run_archives_status"].dropna().astype(str) if "run_archives_status" in o else pd.Series(dtype=str)
    if len(st):
        miss = o["run_archives_missing"].dropna().astype(str) if "run_archives_missing" in o else pd.Series(dtype=str)
        return st.iloc[0], (miss.iloc[0] if len(miss) else "")
    files = sorted(Path(region_dir).glob("collection_summary*.csv"))
    if not files:
        return "unknown", ""
    cc = _coverage_module()
    d = pd.read_csv(files[0], keep_default_na=False)
    failed = d[d.status.isin(cc.FAILED)]
    key = [c for c in failed.collector if cc.IMPACT.get(c, (c, "", False))[2]]
    other = [c for c in failed.collector if c not in key]
    status = cc.KEY_MISSING if key else (cc.OTHER_MISSING if other else cc.COMPLETE)
    return status, "|".join(f"{c}:{t}" for c, t in zip(failed.collector, failed.status))


def _unit(P: np.ndarray) -> np.ndarray:
    s = P.sum(1, keepdims=True)
    return P / np.where(s > 0, s, 1.0)


def decision_path(row: pd.Series) -> dict:
    """The class after each prior factor, replayed from the stored factors (05_likelihood_vectors, class_prior):
    P (training prior) -> x position on GALAXY and QSO -> x QSO magnitude -> x QSO veto -> faint STAR:GALAXY split."""
    P = np.array([row.get(f"p_{c.lower()}_training_prior", np.nan) for c in CLASSES], float)
    out = {"path_ok": False}
    if not np.isfinite(P).all():
        return out
    f = lambda k: float(row[k]) if k in row and pd.notna(row[k]) else 1.0  # noqa: E731
    S = [P.copy()]
    q = P.copy()
    q[1] *= f("prior_position")
    q[2] *= f("prior_position")
    S.append(q.copy())
    q[2] *= f("prior_qso_magnitude")
    S.append(q.copy())
    q[2] *= f("prior_qso_veto")
    S.append(q.copy())
    fs, fg = row.get("prior_faint_star"), row.get("prior_faint_galaxy")
    if pd.notna(fs) and pd.notna(fg) and fs > 0 and fg > 0:
        u = _unit(q[None, :])[0]
        s = u[0] + u[1]
        odds = (u[1] / max(u[0], 1e-12)) * (fg / fs)
        g = s * odds / (1 + odds) if np.isfinite(odds) else s
        u2 = u.copy()
        u2[1], u2[0] = g, s - g
        S.append(u2)
    else:
        S.append(_unit(q[None, :])[0])
    names = ["training", "position", "qso_magnitude", "qso_veto", "faint"]
    for n, s in zip(names, S):
        out[f"class_after_{n}"] = CLASSES[int(np.argmax(s))]
    final = _unit(S[-1][None, :])[0]
    stored = np.array([row.get(f"p_{c.lower()}", np.nan) for c in CLASSES], float)
    out["path_ok"] = bool(np.isfinite(stored).all() and np.allclose(final, _unit(stored[None, :])[0], atol=1e-3))
    return out


def counterfactual(row: pd.Series, drop=()) -> str | None:
    """The class the stored factors give without the factors in ``drop`` ("position", "qso_magnitude", "qso_veto", "faint"),
    ignoring the confidence gates; None when the stored training-prior probabilities are missing."""
    P = np.array([row.get(f"p_{c.lower()}_training_prior", np.nan) for c in CLASSES], float)
    if not np.isfinite(P).all():
        return None
    f = lambda k: float(row[k]) if k in row and pd.notna(row[k]) else 1.0  # noqa: E731
    q = P.copy()
    if "position" not in drop:
        q[1] *= f("prior_position")
        q[2] *= f("prior_position")
    if "qso_magnitude" not in drop:
        q[2] *= f("prior_qso_magnitude")
    if "qso_veto" not in drop:
        q[2] *= f("prior_qso_veto")
    u = _unit(q[None, :])[0]
    fs, fg = row.get("prior_faint_star"), row.get("prior_faint_galaxy")
    if "faint" not in drop and pd.notna(fs) and pd.notna(fg) and fs > 0 and fg > 0:
        sm = u[0] + u[1]
        odds = (u[1] / max(u[0], 1e-12)) * (fg / fs)
        g = sm * odds / (1 + odds) if np.isfinite(odds) else sm
        u[1], u[0] = g, sm - g
    return CLASSES[int(np.argmax(u))]


SCENARIOS = {"cf_no_position": ("position",), "cf_no_qso_magnitude": ("qso_magnitude",),
             "cf_no_position_no_qso_magnitude": ("position", "qso_magnitude"),
             "cf_evidence_only": ("position", "qso_magnitude", "qso_veto", "faint")}  # fmt: skip


def cause(row: pd.Series, has_object: bool) -> tuple[str, str]:
    """(cause, detail) of a quasar that did not get the QSO label."""
    if not has_object:
        return "no_object", ""
    basis = str(row.get("classification_basis", "") or "")
    status = str(row.get("classification_status", "") or "")
    path = decision_path(row)
    ev = path.get("class_after_training")
    if basis and basis != "evidence" and basis != "nan":
        return "rule_decided", basis
    if row["primary_class"] == "UNKNOWN":
        return ("abstained", f"{status}; evidence alone {'QSO' if ev == 'QSO' else ev or 'n/a'}")
    if not path.get("path_ok"):
        return "other", "stored factors do not reproduce p_*"
    if ev != "QSO":
        return "evidence", f"evidence alone: {ev}"
    for step, name in (("position", "position_prior"), ("qso_magnitude", "qso_magnitude"), ("qso_veto", "qso_veto"),
                       ("faint", "faint_star_galaxy")):  # fmt: skip
        if path[f"class_after_{step}"] != "QSO":
            extra = ""
            if step == "position":  # the factor is the local Gaia density where it can be measured, else latitude x Clouds
                dens = row.get("prior_gaia_density")
                extra = "; local Gaia density" if pd.notna(dens) else "; latitude"
            return name, f"{ev} -> {path[f'class_after_{step}']}{extra}"
    return "other", "decision gates"


def _sep_arcsec(ra1, dec1, ra2, dec2):
    a1, d1, a2, d2 = (np.radians(np.asarray(x, float)) for x in (ra1, dec1, ra2, dec2))
    c = np.sin(d1) * np.sin(d2) + np.cos(d1) * np.cos(d2) * np.cos(a1 - a2)
    return np.degrees(np.arccos(np.clip(c, -1, 1))) * 3600.0


def match_truth(objects: pd.DataFrame, t_ra, t_dec) -> int:
    """Index (label position in ``objects``) of the counterpart of one truth position, or -1: among the objects within
    MATCH_ARCSEC the one with the most catalogues (nearest on ties); a grouped object is answered by its parent."""
    s = _sep_arcsec(objects.ra.to_numpy(), objects.dec.to_numpy(), t_ra, t_dec)
    near = np.flatnonzero(s <= MATCH_ARCSEC)
    if not len(near):
        return -1
    ncat = objects.catalogs.fillna("").astype(str).str.count(r"\|").add(1).to_numpy()[near]
    return int(near[np.lexsort((s[near], -ncat))[0]])


def ps1_mags(raw_dir: Path, ra, dec) -> np.ndarray:
    """PS1 mean PSF i magnitude of the nearest PS1 row within 1.5'' of each position (NaN: none); from the raw PS1 csv of a
    region (``<region>/raw/panstarrs1_*.csv``), so the compact record needs no magnitude column."""
    out = np.full(len(ra), np.nan)
    files = sorted(Path(raw_dir).glob("panstarrs1_*.csv"))
    if not files or not len(ra):
        return out
    d = pd.read_csv(files[0], usecols=lambda c: c.lower() in ("ra", "dec", "imeanpsfmag"), low_memory=False)
    d.columns = [c.lower() for c in d.columns]
    if not {"ra", "dec", "imeanpsfmag"} <= set(d.columns) or not len(d):
        return out
    from scipy.spatial import cKDTree

    def xyz(a, b):
        a, b = np.radians(np.asarray(a, float)), np.radians(np.asarray(b, float))
        return np.c_[np.cos(b) * np.cos(a), np.cos(b) * np.sin(a), np.sin(b)]

    dist, idx = cKDTree(xyz(d.ra, d.dec)).query(xyz(ra, dec))
    ok = np.degrees(dist) * 3600.0 <= 1.5
    m = pd.to_numeric(d.imeanpsfmag, errors="coerce").to_numpy(float)
    m = np.where(m > 0, m, np.nan)  # PS1 writes -999 for a missing mean magnitude
    out[ok] = m[idx[ok]]
    return out


def score_regions(regions: pd.DataFrame, truth: pd.DataFrame, root: Path, radius_arcmin: float) -> dict:
    """Per truth object: label and cause; per region: counts.  ``root/<name>/objects.csv.gz``."""
    uq = truth[(truth.cls == "qso") & (truth.also_in.fillna("") != "huo")].reset_index(drop=True)
    t_all = truth[(truth.cls != "qso") | (truth.also_in.fillna("") != "huo")].reset_index(drop=True)
    rows, reg_rows, dens_rows, other_rows = [], [], [], []
    for r in regions.itertuples():
        f = root / r.name / "objects.csv.gz"
        if not f.exists():
            # A region that was not collected or not compacted: its truth objects are listed as REGION_MISSING and kept
            # out of every recall denominator, and the coverage is reported (summarise, main) so an incomplete run is
            # not read as a measurement of the locked list.
            s_m = _sep_arcsec(t_all.ra, t_all.dec, r.ra, r.dec) / 60.0
            for t in t_all[s_m <= radius_arcmin].itertuples():
                rows.append(dict(region=r.name, stratum=r.stratum, sample=t.sample, name=t.name, cls=t.cls, ra=t.ra,
                                 dec=t.dec, b=t.b, l=t.l, ebv=t.ebv, imag=t.imag, z=t.z, label=MISSING, object_id="",
                                 basis="", status="", cause="region_missing" if t.cls == "qso" else ""))  # fmt: skip
            reg_rows.append(dict(name=r.name, stratum=r.stratum, kind=r.kind, status="missing", objects=0))
            continue
        o = pd.read_csv(f, low_memory=False)
        # a region without detections has the pipeline's empty-result schema (no grouping or probability columns)
        o = o.reindex(columns=list(dict.fromkeys([*o.columns, *KEEP, "rules_QSO", "rules_all"])))
        by_id = o.set_index("object_id")
        s_c = _sep_arcsec(t_all.ra, t_all.dec, r.ra, r.dec) / 60.0
        inside = t_all[s_c <= radius_arcmin]
        matched_ids = set()
        for t in inside.itertuples():
            j = match_truth(o, t.ra, t.dec)
            row = dict(region=r.name, stratum=r.stratum, sample=t.sample, name=t.name, cls=t.cls, ra=t.ra, dec=t.dec,
                       b=t.b, l=t.l, ebv=t.ebv, imag=t.imag, z=t.z)  # fmt: skip
            if j < 0:
                row.update(label="NO_OBJECT", object_id="", basis="", status="", cause="no_object" if t.cls == "qso" else "")
            else:
                obj = o.iloc[j]
                top = obj
                par = obj.get("parent_object_id")
                if isinstance(par, str) and par in by_id.index:
                    top = by_id.loc[par]
                    if isinstance(top, pd.DataFrame):
                        top = top.iloc[0]
                matched_ids.add(str(obj.object_id))
                matched_ids.add(str(top.object_id))
                # the label the stored factors would give without a prior; where a rule or an abstention set the label it stays
                evid = str(top.get("classification_basis", "")) == "evidence" and str(top.primary_class) in CLASSES
                for k, drop in SCENARIOS.items():
                    cf = counterfactual(top, drop) if evid else None
                    row[k] = cf if cf is not None else str(top.primary_class)
                cats = str(top.get("catalogs", ""))
                row.update(has_ls="DESI Legacy Surveys DR10" in cats, has_ps1="Pan-STARRS1" in cats, has_wise="AllWISE" in cats,
                           has_gaia="Gaia DR3" in cats, n_catalogs=cats.count("|") + 1 if cats else 0)  # fmt: skip
                row.update(label=str(top.primary_class), object_id=str(top.object_id), basis=str(top.get("classification_basis", "")),
                           status=str(top.get("classification_status", "")), secondary=str(top.get("secondary_class", "")),
                           p_qso=top.get("p_qso"), p_qso_evidence=top.get("p_qso_training_prior"), std_ebv=top.get("std_ebv"),
                           r90=bool(r90_sky(t.ra, t.dec)), r90_rule=("WISE-AGN-R90-001" in str(top.get("rules_all", ""))),
                           rules_QSO=str(top.get("rules_QSO", "")))  # fmt: skip
                if t.cls == "qso" and top.primary_class != "QSO":
                    c, d = cause(top, True)
                    row.update(cause=c, detail=d, **{k: v for k, v in decision_path(top).items() if k.startswith("class_after_")})
                else:
                    row.update(cause="")
            rows.append(row)
        top_level = o[o.parent_object_id.isna()]
        qso_other = top_level[(top_level.primary_class == "QSO") & ~top_level.object_id.astype(str).isin(matched_ids)]
        within = _sep_arcsec(qso_other.ra, qso_other.dec, r.ra, r.dec) / 60.0 <= radius_arcmin
        in_cone = _sep_arcsec(top_level.ra, top_level.dec, r.ra, r.dec) / 60.0 <= radius_arcmin
        qo = qso_other[within.to_numpy() if hasattr(within, "to_numpy") else within]
        qi = ps1_mags(root / r.name / "raw", qo.ra.to_numpy(float), qo.dec.to_numpy(float))
        for k, (_, obj) in enumerate(qo.iterrows()):
            other_rows.append(dict(region=r.name, stratum=r.stratum, kind=r.kind, object_id=obj.object_id, ra=obj.ra, dec=obj.dec,
                                   ps1_i=qi[k], p_qso=obj.get("p_qso"), p_qso_evidence=obj.get("p_qso_training_prior"),
                                   basis=obj.get("classification_basis"), n_catalogs=str(obj.get("catalogs", "")).count("|") + 1))  # fmt: skip
        all_i = ps1_mags(root / r.name / "raw", top_level[in_cone].ra.to_numpy(float), top_level[in_cone].dec.to_numpy(float))
        a_status, a_missing = region_archives(o, root / r.name)
        reg_rows.append(dict(name=r.name, stratum=r.stratum, kind=r.kind, status="ok", archives_status=a_status,
                             archives_missing=a_missing, objects=int(in_cone.sum()),
                             qso_labelled=int((top_level[in_cone].primary_class == "QSO").sum()), qso_other=int(within.sum()),
                             objects_i_lt_195=int(np.sum(all_i < 19.5)), qso_other_i_lt_195=int(np.sum(qi < 19.5)),
                             truth_in_cone=len(inside), area_deg2=math.pi * (radius_arcmin / 60.0) ** 2))  # fmt: skip
    return dict(per_truth=pd.DataFrame(rows), per_region=pd.DataFrame(reg_rows).reindex(columns=REGION_COLS), unique_quasars=uq,
                qso_other=pd.DataFrame(other_rows).reindex(columns=OTHER_COLS))


def _bin_table(df: pd.DataFrame, col: str, bins, label: str, absval=False) -> list[dict]:
    out = []
    v = df[col].abs() if absval else df[col]
    for lo, hi in bins:
        s = df[(v >= lo) & (v < hi)]
        n = len(s)
        k = int((s.label == "QSO").sum())
        a, b = wilson(k, n)
        out.append(dict(by=label, bin=f"{lo:g}-{hi:g}" if hi < 90 else f">={lo:g}", n=n, qso=k,
                        recall=round(k / n, 4) if n else math.nan, lo=round(a, 4), hi=round(b, 4)))  # fmt: skip
    return out


def coverage(res: dict) -> dict:
    """Regions and truth quasars scored against those of the list; ``complete`` is False when a region has no record."""
    R, T = res["per_region"], res["per_truth"]
    q = T[T.cls == "qso"] if len(T) else T
    miss_q = int((q.label == MISSING).sum()) if len(q) else 0
    n_miss = int((R.status == "missing").sum()) if len(R) else 0
    # regions classified without a key archive (Gaia, PS1, Legacy Surveys, AllWISE: a failed query, not an empty answer)
    ast = R["archives_status"] if "archives_status" in R else pd.Series([""] * len(R), index=R.index)
    key_bad = R[(R.status == "ok") & (ast == "key_archives_missing")]
    key_q = int(q.region.isin(set(key_bad.name)).sum()) if len(q) and "region" in q else 0
    return dict(regions=len(R), regions_missing=n_miss, quasars=len(q), quasars_not_scored=miss_q,
                missing_regions=sorted(R.loc[R.status == "missing", "name"].tolist()) if n_miss else [],
                complete=n_miss == 0,
                archive_status_regions={str(k): int(v) for k, v in ast[R.status == "ok"].value_counts().items()},
                regions_key_archive_missing=len(key_bad), quasars_in_those_regions=key_q,
                key_archive_missing={str(n): str(m) for n, m in zip(key_bad.name, key_bad.get("archives_missing", []))},
                degraded=len(key_bad) > 0)  # fmt: skip


# per_truth columns the summary reads; the object columns exist only when some quasar had a counterpart (e.g. not in a
# run whose regions all came back empty), so they are added as missing values before grouping.
SUMMARY_COLS = ["region", "name", "sample", "cls", "b", "ebv", "imag", "z", "label", "basis", "status", "cause", "std_ebv",
                "has_ls", "has_wise", "has_ps1", "r90"]  # fmt: skip


def summarise(res: dict) -> dict[str, pd.DataFrame]:
    T = res["per_truth"]
    T = T.reindex(columns=list(dict.fromkeys([*T.columns, *SUMMARY_COLS])))
    q_all = T[T.cls == "qso"].copy()
    q = q_all[q_all.label != MISSING].copy()  # a quasar of a region without a record is not a miss: it was not measured
    have = q[q.label != "NO_OBJECT"].copy()
    have["ebv_use"] = have.ebv.where(have.ebv.notna(), have.get("std_ebv"))
    rows = []
    n, k = len(have), int((have.label == "QSO").sum())
    a, b = wilson(k, n)
    rows.append(dict(by="all", bin="all", n=n, qso=k, recall=round(k / n, 4) if n else math.nan, lo=round(a, 4), hi=round(b, 4)))
    n2, k2 = len(q), int((q.label == "QSO").sum())
    a2, b2 = wilson(k2, n2)
    rows.append(dict(by="all", bin="all incl. no object", n=n2, qso=k2, recall=round(k2 / n2, 4) if n2 else math.nan, lo=round(a2, 4), hi=round(b2, 4)))
    cov = coverage(res)
    rows.append(dict(by="coverage", bin="quasars in regions without a record (not in any n)", n=cov["quasars_not_scored"],
                     qso=math.nan, recall=math.nan, lo=math.nan, hi=math.nan))  # fmt: skip
    rows.append(dict(by="coverage", bin="quasars in regions that lost a key archive (in the n above)",
                     n=cov["quasars_in_those_regions"], qso=math.nan, recall=math.nan, lo=math.nan, hi=math.nan))  # fmt: skip
    rows += _bin_table(have, "b", B_BINS, "|b| (deg)", absval=True)
    rows += _bin_table(have, "ebv_use", EBV_BINS, "E(B-V)")
    rows += _bin_table(have, "imag", I_BINS, "PS1 i")
    rows += _bin_table(have, "z", Z_BINS, "redshift")
    for sname, g in have.groupby("sample"):
        n, k = len(g), int((g.label == "QSO").sum())
        a, b = wilson(k, n)
        rows.append(dict(by="sample", bin=sname, n=n, qso=k, recall=round(k / n, 4), lo=round(a, 4), hi=round(b, 4)))
    for col, nm in (("has_ls", "Legacy Surveys DR10 row"), ("has_wise", "AllWISE row"), ("has_ps1", "Pan-STARRS1 row")):
        for flag, g in have.groupby(col):
            n, k = len(g), int((g.label == "QSO").sum())
            a, b = wilson(k, n)
            rows.append(dict(by=nm, bin="yes" if flag else "no", n=n, qso=k, recall=round(k / n, 4), lo=round(a, 4), hi=round(b, 4)))
    for flag, g in have.groupby("r90"):
        n, k = len(g), int((g.label == "QSO").sum())
        a, b = wilson(k, n)
        rows.append(dict(by="AllWISE R90 sky", bin="inside" if flag else "outside", n=n, qso=k, recall=round(k / n, 4), lo=round(a, 4), hi=round(b, 4)))
    lab = (q_all.assign(bbin=pd.cut(q_all.b.abs(), [0, 5, 10, 15, 20.0001], right=False).astype(str))
            .groupby(["bbin", "label"]).size().unstack(fill_value=0))  # fmt: skip
    missed = q[q.label != "QSO"]
    causes = (missed.assign(bbin=pd.cut(missed.b.abs(), [0, 5, 10, 15, 20.0001], right=False).astype(str))
              .groupby(["bbin", "cause", "label"]).size().rename("n").reset_index())  # fmt: skip
    R = res["per_region"]
    dens = []
    ok = R[R.status == "ok"]
    for s, g in ok[ok.kind == "qso"].groupby("stratum"):
        area, n_o, n_b = g.area_deg2.sum(), int(g.qso_other.sum()), int(g.qso_other_i_lt_195.sum())
        dens.append(dict(stratum=s, regions=len(g), area_deg2=round(area, 4), objects_i_lt_195=int(g.objects_i_lt_195.sum()),
                         qso_labelled_other=n_o, per_deg2=round(n_o / area, 2), per_deg2_err=round(math.sqrt(max(n_o, 1)) / area, 2),
                         qso_labelled_other_i_lt_195=n_b, per_deg2_i_lt_195=round(n_b / area, 2),
                         per_deg2_i_lt_195_err=round(math.sqrt(max(n_b, 1)) / area, 2)))  # fmt: skip
    g = ok[ok.kind == "qso"]
    area, n_o, n_b = g.area_deg2.sum(), int(g.qso_other.sum()), int(g.qso_other_i_lt_195.sum())
    if not len(g) or not area > 0:  # no quasar region was scored: the density is unavailable, not zero
        dens.append(dict(stratum="all", regions=0, area_deg2=0.0, objects_i_lt_195=0, qso_labelled_other=0,
                         per_deg2=math.nan, per_deg2_err=math.nan, qso_labelled_other_i_lt_195=0,
                         per_deg2_i_lt_195=math.nan, per_deg2_i_lt_195_err=math.nan))  # fmt: skip
    else:
        dens.append(dict(stratum="all", regions=len(g), area_deg2=round(area, 4), objects_i_lt_195=int(g.objects_i_lt_195.sum()),
                         qso_labelled_other=n_o, per_deg2=round(n_o / area, 2), per_deg2_err=round(math.sqrt(max(n_o, 1)) / area, 2),
                         qso_labelled_other_i_lt_195=n_b, per_deg2_i_lt_195=round(n_b / area, 2),
                         per_deg2_i_lt_195_err=round(math.sqrt(max(n_b, 1)) / area, 2)))  # fmt: skip
    cf_rows = []
    for scen in ["label", *SCENARIOS]:
        for name_, g in [("all", have)] + [(f"|b| {lo:g}-{hi:g}", have[(have.b.abs() >= lo) & (have.b.abs() < hi)]) for lo, hi in B_BINS]:
            if scen not in g or not len(g):
                continue
            k = int((g[scen] == "QSO").sum())
            a, b = wilson(k, len(g))
            cf_rows.append(dict(scenario="as run" if scen == "label" else scen, group=name_, n=len(g), qso=k,
                                recall=round(k / len(g), 4), lo=round(a, 4), hi=round(b, 4)))  # fmt: skip
    cont = T[T.cls.isin(["star", "galaxy"])]
    cont = cont[[c for c in ["region", "name", "cls", "b", "imag", "label", "basis", "status", *SCENARIOS] if c in cont]]
    return dict(recall_summary=pd.DataFrame(rows), labels=lab.reset_index(), missed=missed, causes=causes,
                qso_density=pd.DataFrame(dens), contaminants=cont, regions=R,
                counterfactual_recall=pd.DataFrame(cf_rows), qso_other_objects=res["qso_other"])  # fmt: skip


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compact")
    c.add_argument("--work", type=Path, required=True)
    c.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("score")
    s.add_argument("--root", type=Path, required=True, help="folder with <region>/objects.csv.gz")
    s.add_argument("--regions", type=Path, required=True)
    s.add_argument("--truth", type=Path, required=True)
    s.add_argument("--radius", type=float, default=3.0, help="arcmin, as the regions were collected")
    s.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.cmd == "compact":
        compact(a.work, a.out)
        return 0
    a.out.mkdir(parents=True, exist_ok=True)
    res = score_regions(pd.read_csv(a.regions), pd.read_csv(a.truth), a.root, a.radius)
    res["per_truth"].to_csv(a.out / "per_truth.csv", index=False)
    tabs = summarise(res)
    for k, v in tabs.items():
        v.to_csv(a.out / f"{k}.csv", index=False)
    cov = coverage(res)
    (a.out / "coverage.json").write_text(json.dumps(cov, indent=1) + "\n")
    if not cov["complete"]:
        print(f"INCOMPLETE: {cov['regions_missing']} of {cov['regions']} regions have no record "
              f"({cov['quasars_not_scored']} of {cov['quasars']} quasars not scored): {', '.join(cov['missing_regions'])}")  # fmt: skip
    if cov["degraded"]:
        print(f"DEGRADED: {cov['regions_key_archive_missing']} regions were classified without a key archive "
              f"({cov['quasars_in_those_regions']} quasars): "
              + ", ".join(f"{n} ({m})" for n, m in cov["key_archive_missing"].items()))  # fmt: skip
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_rows", 200):
        print(tabs["recall_summary"].to_string(index=False))
        print(tabs["causes"].to_string(index=False))
        print(tabs["qso_density"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
