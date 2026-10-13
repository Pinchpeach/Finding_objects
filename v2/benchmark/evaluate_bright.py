#!/usr/bin/env python3
"""Validate the spectroscopic star rules on bright stars (2.6.2), using the
truth built by build_bright_truth.py:

* APOGEE DR17 (high resolution) log g / [Fe/H] against the luminosity class
  and metal-poor flags from Gaia GSP-Spec, LAMOST LASP and Gaia GSP-Phot as
  Classifier/subclass.py applies them;
* Gaia ESP-ELS classes against SIMBAD main types, per class and flag value;
* field Gaia LPVs: AGB chemistry (C / O) from the photometric models against
  LAMOST spectral classes (Carbon vs M-type).

    python v2/benchmark/evaluate_bright.py [--out metrics.json]
"""
from __future__ import annotations
import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
import evaluate_subclass as ev  # noqa: E402
from evaluate_agb_contamination import MAP as LPV_MAP  # noqa: E402

YSO = {"Y*O", "TT*", "Or*", "Ae*", "Y*?", "TT?", "Ae?", "out", "HH", "YSO"}
BE = {"Be*", "Be?"}
EMISSION = {"Em*", "EmO"}


def _clean(r: dict) -> dict:
    return {k: v for k, v in r.items() if not (isinstance(v, float) and v != v)}


def flags41(v) -> str | None:
    """VizieR gives flags_gspspec as a number: restore the leading zeros."""
    if v is None or (isinstance(v, float) and v != v):
        return None
    s = str(v).strip().split(".")[0]
    return s.zfill(41) if s.isdigit() else None


def apogee(sc) -> dict:
    d = pd.read_csv(BENCH / "bright_truth" / "apogee.csv.gz", low_memory=False, dtype={"ap_Flags": str})
    lim = np.where(d.apo_teff <= 4250, 4.0, np.where(d.apo_teff < 6000, 5.2 - 2.8e-4 * d.apo_teff, 3.5))
    d["truth_lum"] = np.where(d.apo_logg <= lim, "III", "V")
    out = {"n": int(len(d)), "truth_giants": int((d.truth_lum == "III").sum())}
    rules = {}
    for name, cols in {
        "GSPSPEC": {"gaia_dr3__teff_gspspec": "ap_Teff-S", "gaia_dr3__logg_gspspec": "ap_logg-S",
                    "gaia_dr3__mh_gspspec": "ap_[M/H]-S", "gaia_dr3__flags_gspspec": "ap_Flags"},
        "LAMOST": {"lamost_dr_catalog__lasp_teff": "lam_Teff", "lamost_dr_catalog__lasp_logg": "lam_logg",
                   "lamost_dr_catalog__lasp_feh": "lam_[Fe/H]"},
        "GSPPHOT": {"gaia_dr3__teff_gspphot": "ap_Teff", "gaia_dr3__logg_gspphot": "ap_logg"},
    }.items():
        x = d.rename(columns={v: k for k, v in cols.items()})
        if "gaia_dr3__flags_gspspec" in x:
            x["gaia_dr3__flags_gspspec"] = x["gaia_dr3__flags_gspspec"].map(flags41)
        pred = []
        for r in x[list(cols)].to_dict("records"):
            lum, rule, _ = sc.star_luminosity_class(_clean(r), None)
            pred.append(lum if rule in (f"{name}_LOGG", "GAIA_LOGG") else None)
        p = pd.Series(pred, index=d.index)
        m = p.notna()
        gi = d.truth_lum.eq("III")
        rules[name] = {"n": int(m.sum()), "accuracy": round(float((p[m] == d.truth_lum[m]).mean()), 4) if m.any() else None,
                       "giant_recall": round(float((p[m & gi] == "III").mean()), 4) if (m & gi).any() else None,
                       "giant_precision": round(float((d.truth_lum[m & p.eq("III")] == "III").mean()), 4) if (m & p.eq("III")).any() else None}
    out["luminosity_class"] = rules
    out["luminosity_class_strict"] = strict_giants(sc, d)
    # metal-poor ([Fe/H] < -1) by source
    mp = {}
    flags = d["ap_Flags"].map(flags41)
    ok_mh = flags.map(lambda f: f is not None and sc._gspspec_ok(f, "mh"))
    # GSP-Spec [M/H] as subclass.spectro_params returns it (calibrated since
    # 2.17.0, Recio-Blanco et al. 2023 Eq. 2).
    d["gsp_mh_used"] = [
        (sc.gspspec_mh_calibrated(mh, lg) if hasattr(sc, "gspspec_mh_calibrated") else mh)
        if mh == mh and lg == lg else np.nan for mh, lg in zip(d["ap_[M/H]-S"], d["ap_logg-S"])]
    for name, col, sel in (("GSPSPEC", "gsp_mh_used", ok_mh), ("LAMOST", "lam_[Fe/H]", d["lam_[Fe/H]"].notna()),
                           ("GSPPHOT", "ap_[Fe/H]", d["ap_[Fe/H]"].notna())):
        m = sel & d[col].notna() & d.apo_feh.notna()
        flag = d[col] < -1
        t = d.apo_feh < -1
        mp[name] = {"n": int(m.sum()), "flagged": int((flag & m).sum()),
                    "precision": round(float(t[m & flag].mean()), 4) if (m & flag).any() else None,
                    "recall": round(float(flag[m & t].mean()), 4) if (m & t).any() else None,
                    "median_offset": round(float((d[col] - d.apo_feh)[m].median()), 3) if m.any() else None}
    out["metal_poor"] = mp
    return out


def strict_giants(sc, d) -> dict:
    """Giants proper (APOGEE log g < 3.5 and below the Ciardi boundary)
    against the class-III call of each route, including the Gaia CMD route
    (2.17.0).  APOGEE stars carry no extinction here, so the CMD route runs
    on observed BP-RP and G (reddening moves stars down and to the red)."""
    lim = np.where(d.apo_teff <= 4250, 4.0, np.where(d.apo_teff < 6000, 5.2 - 2.8e-4 * d.apo_teff, 3.5))
    truth = pd.Series(np.where((d.apo_logg <= lim) & (d.apo_logg < 3.5), "III",
                               np.where(d.apo_logg <= lim, "IV", "V")), index=d.index)
    routes = {
        "GAIA_CMD": {"gaia_dr3__parallax": "g_Plx", "gaia_dr3__parallax_error": "g_e_Plx",
                     "gaia_dr3__phot_g_mean_mag": "g_Gmag", "gaia_dr3__bp_rp": None},
        "GSPSPEC_LOGG": {"gaia_dr3__teff_gspspec": "ap_Teff-S", "gaia_dr3__logg_gspspec": "ap_logg-S",
                         "gaia_dr3__mh_gspspec": "ap_[M/H]-S", "gaia_dr3__flags_gspspec": "ap_Flags"},
        "LAMOST_LOGG": {"lamost_dr_catalog__lasp_teff": "lam_Teff", "lamost_dr_catalog__lasp_logg": "lam_logg"},
        "GAIA_LOGG": {"gaia_dr3__teff_gspphot": "ap_Teff", "gaia_dr3__logg_gspphot": "ap_logg"},
    }
    out = {}
    for name, cols in routes.items():
        x = pd.DataFrame({k: (d[v] if v else d.g_BPmag - d.g_RPmag) for k, v in cols.items()})
        if "gaia_dr3__flags_gspspec" in x:
            x["gaia_dr3__flags_gspspec"] = x["gaia_dr3__flags_gspspec"].map(flags41)
        pred = []
        for r in x.to_dict("records"):
            lum, rule, _ = sc.star_luminosity_class(_clean(r), None)
            pred.append(lum if rule == name else None)
        p = pd.Series(pred, index=d.index)
        m = p.notna()
        gi = truth.eq("III")
        called = m & p.eq("III")
        out[name] = {"n": int(m.sum()), "called_III": int(called.sum()),
                     "III_precision": round(float(gi[called].mean()), 4) if called.any() else None,
                     "III_recall": round(float(p[m & gi].eq("III").mean()), 4) if (m & gi).any() else None,
                     "truth_of_III_calls": {k: int(v) for k, v in truth[called].value_counts().items()}}
    return out


def els() -> dict:
    d = pd.read_csv(BENCH / "bright_truth" / "els.csv.gz", low_memory=False)
    d["simbad_otype"] = d.simbad_otype.astype(str).str.strip()
    has = d.simbad_otype.notna() & ~d.simbad_otype.isin(["nan", "None", ""])
    out = {}
    for lab, g in d.groupby("ClassELS"):
        truth = YSO if lab in ("TTauri", "HerbigStar") else BE if lab == "beStar" else set()
        res = {"n": int(len(g)), "with_simbad": int(has[g.index].sum()),
               "top_simbad_types": {k: int(v) for k, v in g.simbad_otype[has[g.index]].value_counts().head(8).items()}}
        by_flag = {}
        for f, h in g[has[g.index]].groupby("f_ClassELS"):
            hit = h.simbad_otype.isin(truth)
            by_flag[str(int(f))] = {"n": int(len(h)), "class_match": round(float(hit.mean()), 3),
                                    "emission_or_match": round(float((hit | h.simbad_otype.isin(EMISSION | BE | YSO)).mean()), 3)}
        res["by_flag"] = by_flag
        out[lab] = res
    return out


def lpv_lamost(sc) -> dict:
    d = pd.read_csv(BENCH / "bright_truth" / "lpv_lamost.csv.gz", low_memory=False)
    sub = d.lam_SubClass.astype(str).str.strip()
    truth = pd.Series(np.where(sub.str.upper().str.startswith("CARBON"), "C",
                               np.where(sub.str.match(r"^(d|g|s)?M\d"), "O", None)), index=d.index)
    m = truth.notna()
    x = d[m].rename(columns=LPV_MAP)
    pred = []
    for r in x[list(LPV_MAP.values())].to_dict("records"):
        r = _clean(r); r["primary_class"] = "STAR"
        code = sc.classify(r)["code"] or ""
        letter = code.split(":")[1] if code.count(":") >= 1 else None
        pred.append({"C": "C", "M": "O"}.get(letter))
    p = pd.Series(pred, index=x.index)
    t = truth[m]
    dec = p.notna()
    return {"lamost_matched": int(d.lam_SubClass.notna().sum()), "with_C_or_M_type": int(m.sum()),
            "true_C_fraction": round(float((t == "C").mean()), 4), "decided": int(dec.sum()),
            "accuracy": round(float((p[dec] == t[dec]).mean()), 4) if dec.any() else None,
            "C_precision": round(float((t[p.eq("C")] == "C").mean()), 4) if p.eq("C").any() else None,
            "C_recall": round(float((p[t.eq("C") & dec] == "C").mean()), 4) if (t.eq("C") & dec).any() else None,
            "predicted_C_fraction": round(float((p[dec] == "C").mean()), 4) if dec.any() else None,
            "is_cstar_precision": round(float((t[d.lpv_is_cstar[m].eq(1)] == "C").mean()), 4),
            "lamost_subclasses": {k: int(v) for k, v in sub[d.lam_SubClass.notna()].value_counts().head(12).items()}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=BENCH / "bright_truth" / "bright_metrics.json")
    a = ap.parse_args()
    warnings.filterwarnings("ignore")
    sc = ev.load_subclass()
    out = {"apogee": apogee(sc), "esp_els": els(), "field_lpv_lamost": lpv_lamost(sc)}
    print(json.dumps(out, indent=1))
    a.out.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
