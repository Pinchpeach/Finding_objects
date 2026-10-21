#!/usr/bin/env python3
"""Score v2 and other classification systems on independent spectroscopic
truth in many sky fields (2026-10-21; products of the workflow
.github/workflows/v2_independent_truth.yml in benchmark/independent_fields/).

Truth surveys and the reliability cuts their papers recommend:
* LAMOST DR5 (Luo et al. 2015, 2019): Class STAR/GALAXY/QSO; best-band
  S/N >= 6 (the LAMOST pipeline class is unreliable at lower S/N).
* 2QZ/6QZ (Croom et al. 2004): ID1 with identification quality 1 (first
  digit of q_z1, ">= 99 % confident"); QSO -> QSO, NELG/gal -> GALAXY,
  star -> STAR.
* 2SLAQ QSO (Croom et al. 2009): ID2S with q_ID2S = 1, same mapping.
* 2dFGRS (Colless et al. 2001, 2003): q_z >= 3; |z| < 0.002 -> STAR, z <= 0.5
  -> GALAXY (rare higher-z QSO interlopers are dropped).
* 6dFGS (Jones et al. 2004, 2009): q_cz = 3-4 -> GALAXY (cz >= 600 km/s,
  else STAR), q_cz = 6 -> STAR (confirmed Galactic).
* WiggleZ (Drinkwater et al. 2010, 2018): q_z >= 3; comment AGN/QSO -> QSO,
  z < 0.002 -> STAR, else GALAXY (emission-line galaxy targets).
* RAVE DR6 (Steinmetz et al. 2020): S/N >= 10 -> STAR.

An object counts once (1" groups); surveys that disagree drop it.  Truth is
matched to our top-level objects within 1.5" (2" for the bright-star surveys
LAMOST and RAVE, whose J2000 positions differ by proper motion from the
2016 epoch); a matched part of a galaxy is scored with its host's class.
Objects in the SDSS/DESI benchmark truth sets (training data) are excluded.

    python v2/benchmark/score_independent_fields.py [--which blind|full] [--out DIR]
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

B = Path(__file__).resolve().parent
C = ["STAR", "GALAXY", "QSO"]


def _num(d, c):
    return pd.to_numeric(d.get(c, pd.Series(np.nan, index=d.index)), errors="coerce")


def _read(truth_dir, stem):
    f = truth_dir / f"{stem}.csv.gz"
    return pd.read_csv(f, low_memory=False) if f.exists() else None


def _rows(d, cls, survey):
    out = pd.DataFrame({"ra": _num(d, "_RAJ2000"), "dec": _num(d, "_DEJ2000"), "truth": cls, "survey": survey})
    return out[out.truth.isin(C) & out.ra.notna()]


def truth_table(truth_dir):
    t = []
    ID = {"QSO": "QSO", "NELG": "GALAXY", "gal": "GALAXY", "star": "STAR"}
    d = _read(truth_dir, "V_164_dr5")
    if d is not None:
        snr = d[["snrg", "snrr", "snri"]].apply(pd.to_numeric, errors="coerce").max(axis=1)
        t.append(_rows(d[snr >= 6], d.Class.astype(str).str.strip().str.upper(), "LAMOST DR5"))
    d = _read(truth_dir, "VII_241_2qz")
    if d is not None:
        q = _num(d, "q_z1") // 10
        t.append(_rows(d[q.eq(1)], d.ID1.astype(str).str.strip().map(ID), "2QZ/6QZ"))
    d = _read(truth_dir, "J_MNRAS_392_19_2slaqqso")
    if d is not None:
        t.append(_rows(d[_num(d, "q_ID2S").eq(1)], d.ID2S.astype(str).str.strip().map(ID), "2SLAQ"))
    d = _read(truth_dir, "VII_250_2dfgrs")
    if d is not None:
        z = _num(d, "z")
        d = d[_num(d, "q_z").ge(3) & z.le(0.5)]
        z = _num(d, "z")
        t.append(_rows(d, np.where(z.abs() < 0.002, "STAR", "GALAXY"), "2dFGRS"))
    d = _read(truth_dir, "VII_259_6dfgs")
    if d is not None:
        q, cz = _num(d, "q_cz"), _num(d, "cz")
        cls = np.where(q.eq(6), "STAR", np.where(q.isin([3, 4]), np.where(cz >= 600, "GALAXY", "STAR"), None))
        t.append(_rows(d, cls, "6dFGS"))
    d = _read(truth_dir, "J_MNRAS_474_4151_wigglez")
    if d is not None:
        d = d[_num(d, "q_z").ge(3)]
        agn = d.get("Com", pd.Series("", index=d.index)).astype(str).str.contains("AGN|QSO", case=False)
        t.append(_rows(d, np.where(agn, "QSO", np.where(_num(d, "z").abs() < 0.002, "STAR", "GALAXY")), "WiggleZ"))
    d = _read(truth_dir, "III_283_ravedr6")
    if d is not None:
        t.append(_rows(d[_num(d, "S/N").ge(10)], "STAR", "RAVE DR6"))
    t = pd.concat(t, ignore_index=True) if t else pd.DataFrame(columns=["ra", "dec", "truth", "survey"])
    # One object per 1" group; disagreeing surveys drop it.
    key = list(zip((t.ra * 3600).round().astype("int64"), (t.dec * 3600).round().astype("int64")))
    t["key"] = pd.factorize(pd.Series(key))[0] if len(t) else []
    g = t.groupby("key")
    agree = g.truth.nunique().eq(1)
    out = g.agg(ra=("ra", "mean"), dec=("dec", "mean"), truth=("truth", "first"), survey=("survey", lambda s: "+".join(sorted(set(s)))))
    return out[agree].reset_index(drop=True), int((~agree).sum())


def _nearest(ra1, de1, ra2, de2):
    """Index into (ra2, de2) of the nearest neighbour of each (ra1, de1), and its separation in arcsec."""
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    if len(ra2) == 0:
        return np.full(len(ra1), -1), np.full(len(ra1), np.inf)
    i, s, _ = SkyCoord(ra1 * u.deg, de1 * u.deg).match_to_catalog_sky(SkyCoord(ra2 * u.deg, de2 * u.deg))
    return i, s.arcsec


def benchmark_positions():
    p = [pd.read_csv(B / f, usecols=["ra", "dec"]) for f in ("desi_external/truth.csv", "truth_data/ground_truth.csv", "desi_fusion/truth.csv")]
    g = pd.read_csv(B / "desi_gbm_truth/train.csv.gz", usecols=["p_ra", "p_dec"])  # LS-GBM-001 training set
    p.append(g.rename(columns={"p_ra": "ra", "p_dec": "dec"}))
    return pd.concat(p, ignore_index=True).dropna()


def other_labels(m):
    g = lambda c: _num(m, c)
    lab = {}
    ps = g("gaia_dr3__classprob_dsc_combmod_star").fillna(0) + g("gaia_dr3__classprob_dsc_combmod_whitedwarf").fillna(0) + g("gaia_dr3__classprob_dsc_combmod_binarystar").fillna(0)
    dsc = pd.DataFrame({"STAR": ps, "GALAXY": g("gaia_dr3__classprob_dsc_combmod_galaxy"), "QSO": g("gaia_dr3__classprob_dsc_combmod_quasar")})
    lab["Gaia DR3 DSC-Combmod"] = dsc.fillna(-1).idxmax(axis=1).where(g("gaia_dr3__classprob_dsc_combmod_quasar").notna())
    gb = pd.DataFrame({c: g(f"lsgbm_{c}") for c in C})
    lab["LS-GBM (LS photometry only)"] = gb.fillna(-1).idxmax(axis=1).where(gb.notna().any(axis=1))
    typ = m.get("desi_legacy_surveys_dr10__type", pd.Series("", index=m.index)).astype(str).str.upper().str.strip()
    w12 = g("allwise__W1mag") - g("allwise__W2mag")
    ext = typ.isin(["REX", "EXP", "DEV", "SER", "COMP"])
    mw = pd.Series(np.where(ext, "GALAXY", np.where(w12 >= 0.8, "QSO", "STAR")), index=m.index)
    lab["LS morphology + WISE W1-W2>=0.8"] = mw.where((typ.eq("PSF") & w12.notna()) | ext)
    pe = {
        "LS Tractor PSF vs extended": pd.Series(np.where(typ.eq("PSF"), "POINT", np.where(ext, "EXT", None)), index=m.index),
        "PS1 iPSF-iKron>0.05": (g("pan_starrs1_dr2_meanobject__iMeanPSFMag") - g("pan_starrs1_dr2_meanobject__iMeanKronMag")).map(
            lambda x: None if not np.isfinite(x) or abs(x) > 5 else ("EXT" if x > 0.05 else "POINT")
        ),
    }
    return lab, pe


def score(pred, truth):
    m = pred.notna()
    p, t = pred[m], truth[m]
    if not len(p):
        return None
    cls = p.ne("UNKNOWN")
    rec = {c: (round(100 * float((p[t == c] == c).mean()), 1), int((t == c).sum())) for c in C if (t == c).any()}
    return dict(
        n=int(m.sum()),
        acc=round(100 * float((p == t).mean()), 1),
        acc_cls=round(100 * float((p[cls] == t[cls]).mean()), 1) if cls.any() else None,
        unknown=round(100 * float((~cls).mean()), 1),
        bal=round(float(np.mean([r[0] for r in rec.values()])), 1),
        recall=rec,
    )


def field_matches(fdir, which, bench):
    t, conflicts = truth_table(fdir / "truth")
    info = json.loads((fdir / "field.json").read_text())
    src = fdir / ("objects_blind.csv.gz" if which == "blind" else "objects.csv.gz")
    o = pd.read_csv(src, low_memory=False)
    # Truth inside the field only.
    sep0 = np.hypot((t.ra - info["ra"]) * np.cos(np.radians(info["dec"])), t.dec - info["dec"]) * 60
    t = t[sep0 <= info["radius_arcmin"]].reset_index(drop=True)
    bi, bs = _nearest(t.ra.to_numpy(), t.dec.to_numpy(), bench.ra.to_numpy(), bench.dec.to_numpy())
    t["in_benchmark"] = bs < 1.5
    has_parent = "parent_object_id" in o.columns
    top = o[o.parent_object_id.isna()] if has_parent else o
    i, s = _nearest(t.ra.to_numpy(), t.dec.to_numpy(), o.ra.to_numpy(), o.dec.to_numpy())
    lim = np.where(t.survey.str.contains("LAMOST|RAVE"), 2.0, 1.5)
    t["matched"] = s <= lim
    t["sep"] = s
    # The counterpart is the object with the most catalogues inside the match
    # radius, not simply the nearest: a J2000 truth position of a bright star
    # sits closer to a stray single-catalogue fragment (AllWISE or PS1 row the
    # association left apart) than to the Gaia-anchored 2016 position.  The
    # fragments are counted separately (n_fragments) as an association problem.
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    nc = o.catalogs.fillna("").str.count(r"\|").add(1).to_numpy()
    tc = SkyCoord(t.ra.to_numpy() * u.deg, t.dec.to_numpy() * u.deg)
    oc = SkyCoord(o.ra.to_numpy() * u.deg, o.dec.to_numpy() * u.deg)
    ti, oi, d2, _ = oc.search_around_sky(tc, 2.0 * u.arcsec) if len(t) and len(o) else ([], [], [], [])
    t["n_fragments"] = 0
    for k in range(len(t)):
        sel = (np.asarray(ti) == k) & (np.asarray(d2.arcsec if len(ti) else []) <= lim[k])
        if sel.sum() > 1:
            cand = np.asarray(oi)[sel]
            best = cand[np.lexsort((np.asarray(d2.arcsec)[sel], -nc[cand]))[0]]
            i[k], s[k] = best, float(np.asarray(d2.arcsec)[sel][list(cand).index(best)])
            t.loc[k, "n_fragments"] = int((nc[cand] == 1).sum() - (nc[best] == 1))
    t["sep"] = s
    m = o.iloc[np.where(t.matched, i, 0)].reset_index(drop=True)
    m.index = t.index
    cls = m.primary_class.copy()
    if has_parent:
        host = o.set_index("object_id").primary_class
        part = m.parent_object_id.notna()
        cls[part] = m.parent_object_id[part].map(host)
    m["ours"] = cls
    m = pd.concat([t.add_prefix("t_"), m], axis=1)
    m = m[m.t_matched & ~m.t_in_benchmark]
    return m, dict(info=info, n_truth=len(t), conflicts=conflicts, unmatched=int((~t.matched).sum()), in_bench=int(t.in_benchmark.sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=B / "independent_fields")
    ap.add_argument("--which", choices=["blind", "full"], default="blind")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    bench = benchmark_positions()
    allm, rows = [], []
    for fdir in sorted(p for p in a.root.iterdir() if (p / "field.json").exists()):
        if a.which == "blind" and not (fdir / "objects_blind.csv.gz").exists():
            print(f"{fdir.name}: no blind run yet")
            continue
        m, st = field_matches(fdir, a.which, bench)
        m.insert(0, "field", fdir.name)
        allm.append(m)
        info = st["info"]
        print(f"\n=== {fdir.name}: centre ({info['ra']:.4f}, {info['dec']:+.4f}) r={info['radius_arcmin']}' seeing {info.get('seeing')}")
        print(f"single-catalogue fragments next to a truth object: {int(m.t_n_fragments.gt(0).sum())}")
        print(f"truth in field {st['n_truth']} (unmatched {st['unmatched']}, in SDSS/DESI benchmark {st['in_bench']}, survey conflicts {st['conflicts']}); scored {len(m)}")
        print("   by survey:", m.t_survey.value_counts().to_dict(), "| truth mix:", m.t_truth.value_counts().to_dict())
        r = dict(field=fdir.name, ra=info["ra"], dec=info["dec"], n=len(m), ours=score(m.ours, m.t_truth))
        lab, pe = other_labels(m)
        for k, v in lab.items():
            r[k] = score(v, m.t_truth)
            r[k + " | ours same"] = score(m.ours.where(v.notna()), m.t_truth)
        print("   ours:", r["ours"])
        rows.append(r)
    if not allm:
        return
    M = pd.concat(allm, ignore_index=True)
    print(f"\n=== ALL FIELDS ({a.which}): {len(M)} objects; truth mix {M.t_truth.value_counts().to_dict()}")
    print("ours:", score(M.ours, M.t_truth))
    print(pd.crosstab(M.t_truth, M.ours, margins=True).to_string())
    lab, pe = other_labels(M)
    for k, v in lab.items():
        print(f"\n{k}: theirs {score(v, M.t_truth)}\n   ours on same: {score(M.ours.where(v.notna()), M.t_truth)}")
    pt = np.where(M.t_truth.isin(["STAR", "QSO"]), "POINT", "EXT")
    o2 = M.ours.map({"STAR": "POINT", "QSO": "POINT", "GALAXY": "EXT"})
    for k, v in pe.items():
        mm = v.notna().to_numpy()
        print(f"\n{k}: n={mm.sum()} acc {100 * np.mean(v[mm] == pt[mm]):.1f}% | ours collapsed on same {100 * np.mean(o2[mm] == pt[mm]):.1f}%")
    print("\nby survey:")
    for s_, g in M.groupby(M.t_survey.str.split("+").str[0]):
        print(f"   {s_}: {score(g.ours, g.t_truth)}")
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        M.to_csv(a.out / f"matches_{a.which}.csv", index=False)
        (a.out / f"fields_{a.which}.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
