#!/usr/bin/env python3
"""Published classifier designs re-trained on our truth, against our pipeline.

Designs (features as in the papers, from the columns our runs keep):
* Clarke et al. 2020 (A&A 639, A84; github informationcake/SDSS-ML):
  random forest on SDSS ugriz + WISE W1-W4 + resolvedness (psf - model r).
  Also the same design with Pan-STARRS grizy (psf - Kron i) where SDSS is
  absent.
* Hughes, Bailer-Jones & Jamal 2022 (A&A 668, A99): boosted trees
  (XGBoost/CatBoost; here sklearn HistGradientBoosting) on Gaia G, BP-RP,
  G - W1, W1 - W2, parallax, proper motion and their significances, sin b.
* Gaia DR3 DSC-Combmod and our LS-only ML are reported by
  score_independent_fields (other_labels).

Train on independent-field set A truth, test on set B (blind runs; objects
in the SDSS/DESI benchmark excluded, as in the scorer).  Each design is
compared with our primary_class on exactly the objects it covers.

    compare_literature_designs.py --a ROOT_A --b ROOT_B [--out DIR]
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier

import score_independent_fields as S


def matches(root, bench, cache):
    if cache.exists():
        return pd.read_csv(cache, low_memory=False)
    rows = []
    for fdir in sorted(p for p in root.iterdir() if (p / "field.json").exists() and (p / "objects_blind.csv.gz").exists()):
        m, _ = S.field_matches(fdir, "blind", bench)
        if not m.empty:
            m.insert(0, "field", fdir.name)
            rows.append(m)
    d = pd.concat(rows, ignore_index=True)
    d.to_csv(cache, index=False)
    return d


def n(d, c):
    return pd.to_numeric(d.get(c, pd.Series(np.nan, index=d.index)), errors="coerce")


def clarke_sdss(d):
    f = pd.DataFrame({b: n(d, f"std_mag__sdss_{b}") for b in "ugriz"})
    for k in range(1, 5):
        f[f"w{k}"] = n(d, f"std_mag__wise_w{k}")
    f["resolved"] = n(d, "std_mag__sdsspsf_r") - n(d, "std_mag__sdss_r")
    return f, f[["g", "r", "i", "resolved"]].notna().all(axis=1)


def clarke_ps1(d):
    f = pd.DataFrame({b: n(d, f"std_mag__ps1_{b}") for b in "grizy"})
    for k in range(1, 5):
        f[f"w{k}"] = n(d, f"std_mag__wise_w{k}")
    f["resolved"] = n(d, "pan_starrs1_dr2_meanobject__iMeanPSFMag") - n(d, "pan_starrs1_dr2_meanobject__iMeanKronMag")
    return f, f[["r", "i", "resolved"]].notna().all(axis=1)


def hughes(d):
    g = n(d, "gaia_dr3__phot_g_mean_mag")
    pmra, pmdec = n(d, "gaia_dr3__pmra"), n(d, "gaia_dr3__pmdec")
    pm = np.hypot(pmra, pmdec)
    pme = np.hypot(n(d, "gaia_dr3__pmra_error"), n(d, "gaia_dr3__pmdec_error"))
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    b = SkyCoord(d.t_ra.to_numpy(float) * u.deg, d.t_dec.to_numpy(float) * u.deg).galactic.b.deg
    w1, w2 = n(d, "allwise__W1mag"), n(d, "allwise__W2mag")
    f = pd.DataFrame({"g": g, "bp_rp": n(d, "gaia_dr3__bp_rp"), "g_w1": g - w1, "w1_w2": w1 - w2,
                      "plx": n(d, "gaia_dr3__parallax"), "plx_snr": n(d, "gaia_dr3__parallax_over_error"),
                      "pm": pm, "pm_snr": pm / pme, "sinb": np.sin(np.radians(b))})
    return f, g.notna()


DESIGNS = {
    "Clarke+2020 RF (SDSS ugriz + WISE + psf-model)": (clarke_sdss, lambda: RandomForestClassifier(300, n_jobs=-1, random_state=1)),
    "Clarke+2020 design, PS1 grizy + WISE + psf-Kron": (clarke_ps1, lambda: RandomForestClassifier(300, n_jobs=-1, random_state=1)),
    "Hughes+2022 boosted trees (Gaia + WISE)": (hughes, lambda: HistGradientBoostingClassifier(max_iter=400, random_state=1)),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=Path, required=True)
    ap.add_argument("--b", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=Path("/tmp"))
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    bench = S.benchmark_positions()
    A = matches(a.a, bench, a.cache / "match_A.csv.gz")
    B = matches(a.b, bench, a.cache / "match_B.csv.gz")
    print(f"train (set A) {len(A)}, test (set B) {len(B)}")
    rows = []
    for name, (feat, model) in DESIGNS.items():
        fa, ca = feat(A)
        fb, cb = feat(B)
        keep = [c for c in fa.columns if fa.loc[ca, c].notna().any()]
        fa, fb = fa[keep], fb[keep]
        clf = model()
        if isinstance(clf, RandomForestClassifier):
            fa, fb = fa.fillna(-99), fb.fillna(-99)
        clf.fit(fa[ca], A.t_truth[ca])
        pred = pd.Series(clf.predict(fb[cb]), index=fb.index[cb])
        t, ours = B.t_truth[cb], B.ours[cb]
        okp, oko = pred == t, ours == t
        r = dict(design=name, train=int(ca.sum()), test=int(cb.sum()), acc_design=round(100 * okp.mean(), 2),
                 acc_ours=round(100 * oko.mean(), 2), design_right_ours_wrong=int((okp & ~oko).sum()),
                 ours_right_design_wrong=int((~okp & oko).sum()))
        for c in S.C:
            k = t == c
            r[f"{c}_design"], r[f"{c}_ours"] = round(100 * okp[k].mean(), 1), round(100 * oko[k].mean(), 1)
        rows.append(r)
        print(r)
        if a.out:
            a.out.mkdir(parents=True, exist_ok=True)
            B.loc[cb, ["field", "t_ra", "t_dec", "t_truth", "t_survey", "ours"]].assign(design=pred).to_csv(
                a.out / f"pred_{name.split()[0].replace('+', '')}_{len(rows)}.csv.gz", index=False)
    # Gaia DSC and LS-only ML on the same test set, from the scorer
    lab, _ = S.other_labels(B)
    for k, v in lab.items():
        m = v.notna()
        okp, oko = v[m] == B.t_truth[m], B.ours[m] == B.t_truth[m]
        rows.append(dict(design=k, train=0, test=int(m.sum()), acc_design=round(100 * okp.mean(), 2), acc_ours=round(100 * oko.mean(), 2),
                         design_right_ours_wrong=int((okp & ~oko).sum()), ours_right_design_wrong=int((~okp & oko).sum())))
    res = pd.DataFrame(rows)
    print(res[["design", "test", "acc_design", "acc_ours", "design_right_ours_wrong", "ours_right_design_wrong"]].to_string(index=False))
    if a.out:
        res.to_csv(a.out / "designs_vs_ours.csv", index=False)


if __name__ == "__main__":
    main()
