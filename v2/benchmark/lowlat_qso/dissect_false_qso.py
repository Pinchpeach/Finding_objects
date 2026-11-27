#!/usr/bin/env python3
"""What the objects labelled QSO are that are not a sample quasar (2.61.2; calibration sample of the low-latitude measurement).

    python dissect_false_qso.py --others results_2026-11-27/qso_other_objects.csv --work ROOT --out DIR

``--work`` holds ``<region>/classified_objects.csv`` of the regions that contain such objects (classified again from the
saved blind raw files, ``pipeline.py --raw-dir``).  One row per object with the evidence that spoke for QSO, the way it got the
label (path), the AllWISE colours against the Young Stellar Object, AGB and AGN colour regions of Koenig & Leisawitz (2014,
ApJ 791, 131; arXiv:1407.2262, Sec. 4: equations 9-20, 34-37) and Stern et al. (2012), the Gaia motion against the cut of Fu et
al. (2021, Sec. 5.3), and the sky: |b|, E(B-V), the local Gaia density, the region.  Tables: ``false_qso_objects.csv``,
``summary_*.csv`` (paths, rules, regions, colours).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

QSO_CLASSES = ("QSO", "EXTRAGALACTIC")


def kl14_regions(w1, w2, w3) -> dict:
    """Colour regions of Koenig & Leisawitz (2014), Sec. 4.  ``w3`` may be NaN (then only the W1-W2 tests apply)."""
    c12, c23 = w1 - w2, w2 - w3
    out = dict(w12=c12, w23=c23)
    ok = np.isfinite(c12) and np.isfinite(c23)
    # Class I protostars (eq. 12-15), Class II (eq. 16-20)
    out["yso_class1"] = bool(ok and c23 > 2.0 and c12 > -0.42 * c23 + 2.2 and c12 > 0.46 * c23 - 0.9 and c23 < 4.5)
    out["yso_class2"] = bool(ok and c12 > 0.25 and c12 < 0.9 * c23 - 0.25 and c12 > -1.5 * c23 + 2.1
                             and c12 > 0.46 * c23 - 0.9 and c23 < 4.5)  # fmt: skip
    # AGB cut on the YSO candidates (eq. 34-35): bright in W1 for the W1-W2 colour
    out["agb_bright"] = bool(np.isfinite(c12) and (w1 < (-10.0 / 3.0) * c12 + 9.0 or w1 < (6.0 / 7.0) * c12 + 5.5))
    # K&L's AGN candidates (eq. 9-11): faint in W1 for the W1-W3 colour
    c13 = w1 - w3
    out["kl_agn"] = bool(np.isfinite(c13) and ((w1 > 1.8 * c13 + 4.1 and w1 > 13.0) or w1 > c13 + 11.0))
    out["stern12"] = bool(np.isfinite(c12) and c12 >= 0.8)  # Stern et al. 2012 (W1-W2 >= 0.8); their W2 < 15.05 cut is not applied
    return out


def log_fpm0(row, sigma_s_bright=0.032, sigma_s_faint=0.066, k=1.08) -> float:
    """log10 of the density of zero proper motion of Fu et al. (2021), Eq. 10 (Gaia DR2 constants; the logarithm's base is not
    stated in the text read: natural log is also given as ``ln_fpm0``).  NaN without a Gaia proper motion."""
    a, d = row.get("gaia_dr3__pmra"), row.get("gaia_dr3__pmdec")
    ea, ed = row.get("gaia_dr3__pmra_error"), row.get("gaia_dr3__pmdec_error")
    rho = row.get("gaia_dr3__pmra_pmdec_corr")
    g = row.get("gaia_dr3__phot_g_mean_mag")
    if any(pd.isna(v) for v in (a, d, ea, ed)):
        return math.nan
    ss = sigma_s_bright if (pd.notna(g) and g < 13) else sigma_s_faint
    sx, sy = math.sqrt((k * ea) ** 2 + ss**2), math.sqrt((k * ed) ** 2 + ss**2)
    r = 0.0 if pd.isna(rho) else float(rho)
    q = (a / sx) ** 2 - 2 * r * a * d / (sx * sy) + (d / sy) ** 2
    ln = -math.log(2 * math.pi * sx * sy * math.sqrt(1 - r * r)) - q / (2 * (1 - r * r))
    return ln / math.log(10.0)


def dissect(others: pd.DataFrame, work: Path) -> pd.DataFrame:
    rows = []
    for region, g in others.groupby("region"):
        f = work / region / "classified_objects.csv"
        if not f.exists():
            continue
        d = pd.read_csv(f, low_memory=False).set_index("object_id")
        for r in g.itertuples():
            if r.object_id not in d.index:
                continue
            x = d.loc[r.object_id]
            try:
                ev = json.loads(x.evidence_json) if isinstance(x.evidence_json, str) else []
            except ValueError:
                ev = []
            voters = {}
            for e in ev:
                if e.get("class") in QSO_CLASSES and e.get("rule_id"):
                    voters[e["rule_id"]] = round(float(e.get("score", np.nan)), 3)
            against = sorted({e["rule_id"] for e in ev if e.get("class") in ("STAR", "GALAXY") and e.get("rule_id")
                              and e.get("kind") != "linear_feature"})  # fmt: skip
            w1, w2, w3 = (x.get(f"allwise__W{i}mag", np.nan) for i in (1, 2, 3))
            cat = str(x.catalogs)
            n = cat.count("|") + 1
            path = ("only AllWISE" if cat == "AllWISE" else "only Legacy Surveys" if cat == "DESI Legacy Surveys DR10"
                    else "only Gaia" if cat == "Gaia DR3" else "one other survey" if n == 1
                    else "AllWISE + one other" if (n == 2 and "AllWISE" in cat) else "two or more surveys")  # fmt: skip
            kl = kl14_regions(w1, w2, w3) if pd.notna(w1) and pd.notna(w2) else {}
            lf = log_fpm0(x)
            rows.append(dict(region=region, stratum=r.stratum, object_id=r.object_id, ra=r.ra, dec=r.dec, catalogs=cat,
                             n_catalogs=n, path=path, p_qso=x.p_qso, p_qso_evidence=x.p_qso_training_prior,
                             basis=x.classification_basis, status=x.classification_status, ebv=x.std_ebv,
                             gaia_density=x.prior_gaia_density, prior_position=x.prior_position,
                             prior_qso_magnitude=x.prior_qso_magnitude, ps1_i=r.ps1_i,
                             gaia_g=x.get("gaia_dr3__phot_g_mean_mag"), w1=w1, w2=w2, w3=w3,
                             w1_snr=x.get("allwise__snr1"), w2_snr=x.get("allwise__snr2"), w3_snr=x.get("allwise__snr3"),
                             **kl, qso_voters=";".join(f"{k}={v}" for k, v in sorted(voters.items())),
                             qso_voter_ids=";".join(sorted(voters)), against=";".join(against),
                             parallax_snr=(abs(x.get("gaia_dr3__parallax", np.nan)) / x.get("gaia_dr3__parallax_error", np.nan)
                                           if pd.notna(x.get("gaia_dr3__parallax_error", np.nan)) else np.nan),
                             pm_mas_yr=math.hypot(x.get("gaia_dr3__pmra", np.nan), x.get("gaia_dr3__pmdec", np.nan))
                             if pd.notna(x.get("gaia_dr3__pmra", np.nan)) else np.nan,
                             log10_fpm0=lf, has_gaia="Gaia DR3" in cat, ruwe=x.get("gaia_dr3__ruwe", np.nan),
                             dsc_qso=x.get("gaia_dr3__classprob_dsc_combmod_quasar", np.nan)))  # fmt: skip
    return pd.DataFrame(rows)


def summaries(d: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {}
    out["paths"] = d.groupby("path").agg(n=("object_id", "size"), median_p_qso=("p_qso", "median"),
                                         median_ps1_i=("ps1_i", "median"), median_ebv=("ebv", "median")).round(3)  # fmt: skip
    out["paths"]["share"] = (out["paths"].n / len(d)).round(3)
    out["rules"] = d.groupby("qso_voter_ids").agg(n=("object_id", "size"), median_p_qso=("p_qso", "median")).sort_values("n", ascending=False).head(25)
    reg = d.groupby("region").size().sort_values(ascending=False).rename("n").to_frame()
    reg["cum_share"] = (reg.n.cumsum() / reg.n.sum()).round(3)
    out["regions"] = reg
    out["strata"] = d.groupby("stratum").size().rename("n").to_frame()
    wise = d[d.w1.notna() & d.w2.notna()]
    rows = []
    for name, m in {
        "all with AllWISE W1,W2": pd.Series(True, index=wise.index),
        "W1-W2 >= 0.8 (Stern 2012)": wise.stern12,
        "K&L14 Class I colours": wise.yso_class1.fillna(False).astype(bool),
        "K&L14 Class II colours": wise.yso_class2.fillna(False).astype(bool),
        "K&L14 Class I or II colours": (wise.yso_class1.fillna(False) | wise.yso_class2.fillna(False)).astype(bool),
        "  ... and bright in W1 (AGB cut)": ((wise.yso_class1.fillna(False) | wise.yso_class2.fillna(False)) & wise.agb_bright.fillna(False)).astype(bool),
        "K&L14 AGN-candidate colour-magnitude": wise.kl_agn.fillna(False).astype(bool),
    }.items():
        rows.append(dict(selection=name, n=int(m.sum()), share=round(float(m.mean()), 3)))
    out["wise_colours"] = pd.DataFrame(rows)
    gaia = d[d.has_gaia]
    out["gaia"] = pd.DataFrame([
        dict(group="with a Gaia DR3 row", n=len(gaia), share=round(len(gaia) / len(d), 3)),
        dict(group="  log10 fPM0 < -4 (fails the Fu et al. 2021 cut)", n=int((gaia.log10_fpm0 < -4).sum()),
             share=round(float((gaia.log10_fpm0 < -4).mean()), 3) if len(gaia) else math.nan),
        dict(group="  parallax S/N > 3", n=int((gaia.parallax_snr > 3).sum()),
             share=round(float((gaia.parallax_snr > 3).mean()), 3) if len(gaia) else math.nan),
        dict(group="  DSC quasar probability > 0.5", n=int((gaia.dsc_qso > 0.5).sum()),
             share=round(float((gaia.dsc_qso > 0.5).mean()), 3) if len(gaia) else math.nan),
    ])  # fmt: skip
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--others", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    o = pd.read_csv(a.others)
    d = dissect(o[o.stratum != "contaminant"], a.work)
    d.to_csv(a.out / "false_qso_objects.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 80):
        for k, v in summaries(d).items():
            v.to_csv(a.out / f"summary_{k}.csv")
            print(f"== {k}\n{v.to_string()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
