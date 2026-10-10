#!/usr/bin/env python3
"""Evaluate the sub-class classifier (v2/Classifier/subclass.py) on the
spectroscopic benchmarks, and record per-rule precision.

Truth:
  * SDSS DR18 (truth_data/ground_truth.csv): STAR subclass (MK template type,
    WD, carbon, CV) and GALAXY subclass (STARFORMING / STARBURST / AGN /
    BROADLINE; empty = no emission line strong enough to classify).
  * DESI DR1 (desi_external/truth.csv): STAR spectral letter.

The catalogue features are the preserved benchmark cross-matches
(``catalog_features/*.csv.gz``), renamed to the namespaced columns the
pipeline produces. Spectroscopic catalogue columns are NOT given to the
classifier (they are the truth). The coarse class is the true one, so this
measures the sub-class step alone.

Writes ``subclass_metrics.json`` and, with ``--write-precision``, the
per-rule precision measured on the train split into
``v2/Classifier/subclass_rule_precision.json`` (used as rule confidence).
"""
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[1]
BENCH = V2 / "benchmark"
FEATURES = {
    "gaia_dr3": ("gaia_dr3", {"bp_rp": "bp_rp", "E(BP-RP)": "ebpminrp_gspphot", "teff_gspphot": "teff_gspphot",
                              "logg_gspphot": "logg_gspphot", "parallax": "parallax", "parallax_error": "parallax_error",
                              "phot_g_mean_mag": "phot_g_mean_mag"}),
    "desi_legacy": ("desi_legacy_surveys_dr10", {c: c for c in ("type", "flux_g", "flux_r", "flux_i", "flux_z",
                                                                "mw_transmission_g", "mw_transmission_r", "mw_transmission_z")}),
    "panstarrs1": ("pan_starrs1_dr2_meanobject", {c: c for c in ("gMeanPSFMag", "rMeanPSFMag", "iMeanPSFMag", "zMeanPSFMag",
                                                                 "rMeanKronMag")}),
    "allwise": ("allwise", {c: c for c in ("W1mag", "W2mag", "W3mag", "e_W1mag", "e_W2mag", "e_W3mag")}),
    "galex": ("galex_ais", {"NUVmag": "NUVmag", "E(B-V)": "E(B-V)"}),
}


def load_subclass():
    sys.path.insert(0, str(V2 / "Classifier"))
    spec = importlib.util.spec_from_file_location("v2_subclass", V2 / "Classifier" / "subclass.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def frame(truth: pd.DataFrame, feature_dir: Path) -> pd.DataFrame:
    d = truth.copy()
    for f, (pre, cols) in FEATURES.items():
        p = feature_dir / f"{f}_trd.csv.gz"
        if not p.exists():
            continue
        x = pd.read_csv(p, low_memory=False)
        keep = {c: f"{pre}__{v}" for c, v in cols.items() if c in x}
        x = x[["benchmark_id", *keep]].drop_duplicates("benchmark_id").rename(columns=keep)
        d = d.merge(x, on="benchmark_id", how="left")
    return d


def sdss_activity(sub) -> str:
    s = str(sub).upper()
    if s in ("", "NAN"):
        return "QUIESCENT"          # no emission line strong enough to classify
    if "AGN" in s or "BROADLINE" in s:
        return "AGN"
    return "STAR_FORMING"           # STARFORMING or STARBURST


def load_physical():
    spec = importlib.util.spec_from_file_location("v2_axis_physical", V2 / "Classifier" / "axes" / "physical.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def evaluate(rows: pd.DataFrame, sc, label: str) -> tuple[dict, pd.DataFrame]:
    recs = rows.to_dict("records")
    phys = load_physical()
    for r in recs:                     # the physical axis (WD locus) reads bare Gaia names
        for k in ("parallax", "parallax_error", "phot_g_mean_mag", "bp_rp", "teff_gspphot", "logg_gspphot"):
            r.setdefault(k, r.get(f"gaia_dr3__{k}"))
        if r.get("primary_class") == "STAR":
            ph = phys.classify(r)
            r["physical_class"], r["physical_confidence"] = ph.get("label"), ph.get("confidence")
    res = [sc.classify(r) for r in recs]
    out = rows.assign(rule=[r.get("rule") for r in res], subclass=[r.get("subclass") for r in res],
                      spectral_type=[r.get("spectral_type") for r in res], lum=[r.get("luminosity_class") for r in res],
                      activity=[r.get("activity") for r in res], profile=[r.get("profile") for r in res])
    metrics = {"sample": label, "n": int(len(out))}
    stars = out[out.primary_class.eq("STAR")].copy()
    if len(stars):
        stars["truth_num"] = stars.truth_spt.map(sc.spt_number)
        stars["pred_num"] = stars.spectral_type.map(sc.spt_number)
        ok = stars.truth_num.notna() & stars.pred_num.notna()
        dl = (stars.truth_num // 10 - stars.pred_num // 10)
        metrics["star"] = {
            "with_mk_truth": int(stars.truth_num.notna().sum()), "typed": int(ok.sum()),
            "coverage": round(float(ok.sum() / max(stars.truth_num.notna().sum(), 1)), 4),
            "letter_accuracy": round(float((dl[ok] == 0).mean()), 4) if ok.any() else None,
            "within_one_letter": round(float((dl[ok].abs() <= 1).mean()), 4) if ok.any() else None,
            "median_abs_subtypes": round(float((stars.truth_num - stars.pred_num)[ok].abs().median()), 2) if ok.any() else None,
            "by_rule": {}, "by_truth_letter": {},
        }
        for rule, g in stars[ok].groupby("rule"):
            d = (g.truth_num // 10 - g.pred_num // 10)
            metrics["star"]["by_rule"][rule] = {"n": int(len(g)), "letter_accuracy": round(float((d == 0).mean()), 4),
                                                "within_one_letter": round(float((d.abs() <= 1).mean()), 4)}
        for letter, g in stars[ok].groupby(stars.truth_num[ok] // 10):
            d = (g.truth_num // 10 - g.pred_num // 10)
            metrics["star"]["by_truth_letter"][sc.LETTERS[int(letter)]] = {
                "n": int(len(g)), "letter_accuracy": round(float((d == 0).mean()), 4),
                "median_abs_subtypes": round(float((g.truth_num - g.pred_num).abs().median()), 2)}
        km = ok & (stars.truth_num >= 50)
        if km.any():
            d = (stars.truth_num - stars.pred_num)[km]
            metrics["star"]["K_M_truth"] = {"n": int(km.sum()), "median_abs_subtypes": round(float(d.abs().median()), 2),
                                            "within_2_subtypes": round(float((d.abs() <= 2).mean()), 4)}
        metrics["star"]["luminosity_class_counts"] = stars.lum.value_counts(dropna=False).rename(str).to_dict()
        wd = stars.truth_spt.astype(str).str.upper().eq("WD")
        if wd.any():
            metrics["star"]["wd_truth_typed_as_wd"] = round(float(stars.subclass[wd].astype(str).str.startswith("White dwarf").mean()), 4)
    gals = out[out.primary_class.eq("GALAXY") & out.truth_activity.notna()].copy()
    if len(gals):
        act = gals.activity.notna()
        metrics["galaxy"] = {"n": int(len(gals)), "activity_coverage": round(float(act.mean()), 4),
                             "activity_accuracy": round(float((gals.activity[act] == gals.truth_activity[act]).mean()), 4)
                             if act.any() else None, "by_rule": {},
                             "truth_mix": gals.truth_activity.value_counts().to_dict(),
                             "confusion": pd.crosstab(gals.truth_activity[act], gals.activity[act]).to_dict()}
        for rule, g in gals[act].groupby("rule"):
            metrics["galaxy"]["by_rule"][rule] = {"n": int(len(g)), "precision": round(float((g.activity == g.truth_activity).mean()), 4)}
        metrics["galaxy"]["profile_counts"] = gals.profile.value_counts(dropna=False).rename(str).to_dict()
    return metrics, out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, help="benchmark_manifest.csv (validate_catalog_truth.py) for train/test splits")
    p.add_argument("--out", type=Path, default=Path("/tmp/subclass_eval"))
    p.add_argument("--write-precision", action="store_true")
    a = p.parse_args()
    sc = load_subclass()
    a.out.mkdir(parents=True, exist_ok=True)

    t = pd.read_csv(BENCH / "truth_data" / "ground_truth.csv")
    sdss = frame(t, BENCH / "catalog_features")
    sdss["primary_class"] = sdss["class"]
    sdss["truth_spt"] = np.where(sdss["class"].eq("STAR"), sdss.subclass, None)
    sdss["truth_activity"] = np.where(sdss["class"].eq("GALAXY"), sdss.subclass.map(sdss_activity), None)
    if a.manifest and a.manifest.exists():
        sdss = sdss.merge(pd.read_csv(a.manifest)[["benchmark_id", "split"]], on="benchmark_id", how="left")
    else:
        sdss["split"] = "all"
    report = {}
    tables = []
    for split in ("train", "test"):
        part = sdss[sdss.split.eq(split)] if split in set(sdss.split) else sdss
        m, tab = evaluate(part, sc, f"SDSS {split}")
        report[f"sdss_{split}"] = m; tables.append(tab.assign(sample=f"sdss_{split}"))

    dt = pd.read_csv(BENCH / "desi_external" / "truth.csv")
    desi = frame(dt, BENCH / "desi_external" / "catalog_features")
    desi["primary_class"] = desi.truth_class
    desi["truth_spt"] = np.where(desi.truth_class.eq("STAR"), desi.truth_subclass, None)
    desi["truth_activity"] = None
    m, tab = evaluate(desi, sc, "DESI DR1 (independent)")
    report["desi"] = m; tables.append(tab.assign(sample="desi"))

    (a.out / "subclass_metrics.json").write_text(json.dumps(report, indent=2, default=str))
    keep = ["benchmark_id", "sample", "primary_class", "truth_spt", "truth_activity", "rule", "subclass", "spectral_type", "lum", "activity", "profile"]
    pd.concat(tables)[keep].to_csv(a.out / "subclass_predictions.csv", index=False)
    print(json.dumps({k: {kk: v.get(kk) for kk in ("star", "galaxy") if kk in v} for k, v in report.items()}, indent=1, default=str)[:6000])
    if a.write_precision:
        tr = report["sdss_train"]
        prec = {r: v["letter_accuracy"] for r, v in tr.get("star", {}).get("by_rule", {}).items() if v["n"] >= 30}
        prec.update({r: v["precision"] for r, v in tr.get("galaxy", {}).get("by_rule", {}).items() if v["n"] >= 30})
        path = V2 / "Classifier" / "subclass_rule_precision.json"
        path.write_text(json.dumps({"source": "SDSS DR18 benchmark train split (evaluate_subclass.py)", "precision": prec}, indent=2) + "\n")
        print("wrote", path)


if __name__ == "__main__":
    main()
