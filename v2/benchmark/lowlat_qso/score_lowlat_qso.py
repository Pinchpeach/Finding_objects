#!/usr/bin/env python3
"""Recall of the QSO label on spectroscopically confirmed quasars behind the Galactic plane (2.61.1).  Measurement only.

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
  qso_density.csv           the objects labelled QSO per square degree of the cones, other than the sample quasars
  contaminants.csv          what the 19 non-quasars of the Fu et al. 2022 candidate list were labelled
  regions.csv               one row per region: objects, QSO-labelled objects, truth quasars in the cone, archive status

Causes of a miss, first match wins:
  no_object          no object within ``MATCH_ARCSEC`` of the quasar (not detected in any catalogue, or not resolved)
  rule_decided       ``classification_basis`` is not ``evidence``: a rule other than the fused evidence set the label
                     (Gaia motion, near-infrared star, member rules ...); the basis is named
  abstained          the label is UNKNOWN: ``classification_status`` (LOW_CONFIDENCE, CONFLICT, NO_EVIDENCE ...); split by
                     whether the evidence alone (``p_*_training_prior``) pointed at QSO
  evidence           the fused evidence alone (``p_*_training_prior``) does not point at QSO
  position_prior     the evidence points at QSO and the Galactic position factor (``prior_position`` on GALAXY and QSO) turns it
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
CLASSES = ("STAR", "GALAXY", "QSO")
KEEP = [
    "object_id", "ra", "dec", "catalogs", "std_ebv", "primary_class", "primary_confidence", "primary_margin",
    "classification_status", "classification_basis", "best_candidate_class", "secondary_class", "secondary_class_reason",
    "parent_object_id", "component_role", "high_confidence", "evidence_count", "evidence_conflict",
    "p_star", "p_galaxy", "p_qso", "p_star_training_prior", "p_galaxy_training_prior", "p_qso_training_prior",
    "prior_gaia_density", "prior_position", "prior_qso_magnitude", "prior_qso_veto", "prior_faint_star",
    "prior_faint_galaxy", "prior_layer",
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
    for raw in d.get("evidence_json", pd.Series([""] * len(d))):
        try:
            ev = json.loads(raw) if isinstance(raw, str) else []
        except ValueError:
            ev = []
        per = {c: set() for c in CLASSES}
        for e in ev:
            if e.get("class") in per and e.get("rule_id"):
                per[e["class"]].add(str(e["rule_id"]))
        for c in CLASSES:
            rules[c].append(";".join(sorted(per[c])))
    for c in CLASSES:
        d[f"rules_{c}"] = rules[c]
    d = d.drop(columns=["evidence_json"], errors="ignore")
    d.to_csv(out / "objects.csv.gz", index=False)
    for f in ("collection_summary", "catalog_coverage.json", "pipeline_summary.csv"):
        for p in list(work.glob(f"**/{f}*")) + list(work.glob(f"**/{f}")):
            if p.is_file() and p.stat().st_size < 5_000_000:
                (out / p.name).write_bytes(p.read_bytes())
                break


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
            return name, f"{ev} -> {path[f'class_after_{step}']}"
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


def score_regions(regions: pd.DataFrame, truth: pd.DataFrame, root: Path, radius_arcmin: float) -> dict:
    """Per truth object: label and cause; per region: counts.  ``root/<name>/objects.csv.gz``."""
    uq = truth[(truth.cls == "qso") & (truth.also_in.fillna("") != "huo")].reset_index(drop=True)
    t_all = truth[(truth.cls != "qso") | (truth.also_in.fillna("") != "huo")].reset_index(drop=True)
    rows, reg_rows, dens_rows = [], [], []
    for r in regions.itertuples():
        f = root / r.name / "objects.csv.gz"
        if not f.exists():
            reg_rows.append(dict(name=r.name, stratum=r.stratum, kind=r.kind, status="missing", objects=0))
            continue
        o = pd.read_csv(f, low_memory=False)
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
                row.update(label=str(top.primary_class), object_id=str(top.object_id), basis=str(top.get("classification_basis", "")),
                           status=str(top.get("classification_status", "")), secondary=str(top.get("secondary_class", "")),
                           p_qso=top.get("p_qso"), p_qso_evidence=top.get("p_qso_training_prior"), std_ebv=top.get("std_ebv"),
                           r90=bool(r90_sky(t.ra, t.dec)), r90_rule=("WISE-AGN-R90-001" in str(top.get("rules_QSO", ""))),
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
        reg_rows.append(dict(name=r.name, stratum=r.stratum, kind=r.kind, status="ok", objects=int(in_cone.sum()),
                             qso_labelled=int((top_level[in_cone].primary_class == "QSO").sum()), qso_other=int(within.sum()),
                             truth_in_cone=len(inside), area_deg2=math.pi * (radius_arcmin / 60.0) ** 2))  # fmt: skip
    return dict(per_truth=pd.DataFrame(rows), per_region=pd.DataFrame(reg_rows), unique_quasars=uq)


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


def summarise(res: dict) -> dict[str, pd.DataFrame]:
    T = res["per_truth"]
    q = T[T.cls == "qso"].copy()
    have = q[q.label != "NO_OBJECT"].copy()
    have["ebv_use"] = have.ebv.where(have.ebv.notna(), have.get("std_ebv"))
    rows = []
    n, k = len(have), int((have.label == "QSO").sum())
    a, b = wilson(k, n)
    rows.append(dict(by="all", bin="all", n=n, qso=k, recall=round(k / n, 4) if n else math.nan, lo=round(a, 4), hi=round(b, 4)))
    n2, k2 = len(q), int((q.label == "QSO").sum())
    a2, b2 = wilson(k2, n2)
    rows.append(dict(by="all", bin="all incl. no object", n=n2, qso=k2, recall=round(k2 / n2, 4) if n2 else math.nan, lo=round(a2, 4), hi=round(b2, 4)))
    rows += _bin_table(have, "b", B_BINS, "|b| (deg)", absval=True)
    rows += _bin_table(have, "ebv_use", EBV_BINS, "E(B-V)")
    rows += _bin_table(have, "imag", I_BINS, "PS1 i")
    rows += _bin_table(have, "z", Z_BINS, "redshift")
    for sname, g in have.groupby("sample"):
        n, k = len(g), int((g.label == "QSO").sum())
        a, b = wilson(k, n)
        rows.append(dict(by="sample", bin=sname, n=n, qso=k, recall=round(k / n, 4), lo=round(a, 4), hi=round(b, 4)))
    for flag, g in have.groupby("r90"):
        n, k = len(g), int((g.label == "QSO").sum())
        a, b = wilson(k, n)
        rows.append(dict(by="AllWISE R90 sky", bin="inside" if flag else "outside", n=n, qso=k, recall=round(k / n, 4), lo=round(a, 4), hi=round(b, 4)))
    lab = (q.assign(bbin=pd.cut(q.b.abs(), [0, 5, 10, 15, 20.0001], right=False).astype(str))
            .groupby(["bbin", "label"]).size().unstack(fill_value=0))  # fmt: skip
    missed = q[q.label != "QSO"]
    causes = (missed.assign(bbin=pd.cut(missed.b.abs(), [0, 5, 10, 15, 20.0001], right=False).astype(str))
              .groupby(["bbin", "cause", "label"]).size().rename("n").reset_index())  # fmt: skip
    R = res["per_region"]
    dens = []
    ok = R[R.status == "ok"]
    for s, g in ok[ok.kind == "qso"].groupby("stratum"):
        area, n_o = g.area_deg2.sum(), int(g.qso_other.sum())
        dens.append(dict(stratum=s, regions=len(g), area_deg2=round(area, 4), qso_labelled_other=n_o,
                         per_deg2=round(n_o / area, 2), per_deg2_err=round(math.sqrt(max(n_o, 1)) / area, 2)))  # fmt: skip
    cont = T[T.cls.isin(["star", "galaxy"])][["region", "name", "cls", "b", "imag", "label", "basis", "status"]]
    return dict(recall_summary=pd.DataFrame(rows), labels=lab.reset_index(), missed=missed, causes=causes,
                qso_density=pd.DataFrame(dens), contaminants=cont, regions=R)  # fmt: skip


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
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_rows", 200):
        print(tabs["recall_summary"].to_string(index=False))
        print(tabs["causes"].to_string(index=False))
        print(tabs["qso_density"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
