#!/usr/bin/env python3
"""Validate the spectroscopic sub-class criteria (Classifier/subclass.py) on
the spectroscopic products of the benchmark objects
(benchmark/spectro_truth, built by build_spectro_truth.py):

* galaxies: BPT / WHAN / Dn4000 from the SDSS emission lines (Portsmouth,
  else MPA-JHU) against the SDSS pipeline subclass (all lines at 10 sigma),
  the Portsmouth BPT label, and, for galaxies without a subclass, the WISE
  W2 - W3 colour (star-forming discs > 3, spheroids < 1.5; independent of the
  spectrum);
* stars: luminosity class from LAMOST LASP log g against the Gaia parallax
  CMD class, and LAMOST [Fe/H] against the GSP-Phot [M/H] metal-poor flag.

    python v2/benchmark/evaluate_spectro.py [--out metrics.json]
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
V2 = BENCH.parent
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(V2 / "Get_data"))
import evaluate_subclass as ev  # noqa: E402
import sdss_spectroscopy as ss  # noqa: E402

P = "sdss_dr18_spectroscopy__"


def _clean_row(r: dict) -> dict:
    return {k: v for k, v in r.items() if not (isinstance(v, float) and v != v)}


def galaxies(sc) -> dict:
    g = pd.read_csv(BENCH / "spectro_truth" / "sdss_galaxy_lines.csv.gz", low_memory=False)
    rows = pd.DataFrame({"benchmark_id": g.benchmark_id})
    for gen, (p, m) in ss.LINES.items():
        pv = ss._clean(g["port_" + p.lower()]) if "port_" + p.lower() in g else pd.Series(np.nan, index=g.index)
        mv = ss._clean(g["mpa_" + m]) if "mpa_" + m in g else pd.Series(np.nan, index=g.index)
        if gen.endswith("_ew"):
            mv = -mv                                  # MPA-JHU EW negative in emission
        rows[P + gen] = pv.where(pv.notna(), mv)
    rows[P + "d4000_n"] = ss._clean(g["mpa_d4000_n"]) if "mpa_d4000_n" in g else np.nan
    res = [sc.galaxy_lines(_clean_row(r)) for r in rows.to_dict("records")]
    g["act"] = [r[0] if r else None for r in res]
    g["rule"] = [r[1] if r else None for r in res]
    w = pd.read_csv(BENCH / "catalog_features" / "allwise_trd.csv.gz", usecols=["benchmark_id", "W2mag", "W3mag"],
                    low_memory=False).drop_duplicates("benchmark_id")
    g = g.merge(w, on="benchmark_id", how="left")
    g["w23"] = g.W2mag - g.W3mag
    sub = g.subclass.fillna("NONE")
    truth = sub.map({"STARFORMING": "STAR_FORMING", "STARBURST": "STAR_FORMING", "AGN": "AGN"})
    m = truth.notna()
    port = g.get("port_bpt", pd.Series(dtype=str)).map({"Star Forming": "STAR_FORMING", "Composite": "COMPOSITE", "LINER": "AGN",
                                                         "Seyfert": "AGN", "Seyfert/LINER": "AGN"})
    k = g.rule.eq("SDSS_LINES_BPT")
    none = sub.eq("NONE")
    by = {}
    for act, x in g[none].groupby(g.act[none].fillna("none")):
        by[act] = {"n": int(len(x)), "w23_median": round(float(x.w23.median()), 2),
                   "w23_gt3": round(float((x.w23 > 3).mean()), 3), "w23_lt1.5": round(float((x.w23 < 1.5).mean()), 3)}
    return {"n": int(len(g)), "coverage": round(float(g.act.notna().mean()), 4),
            "rules": {k_: int(v) for k_, v in g.rule.value_counts().items()},
            "vs_sdss_subclass": pd.crosstab(truth[m], g.act[m].fillna("none")).to_dict(orient="index"),
            "bpt_rule_agrees_with_portsmouth_bpt": round(float((g.act[k] == port[k]).mean()), 4) if k.any() else None,
            "no_subclass": {"n": int(none.sum()), "labelled": int(g.act[none].notna().sum()), "by_label": by}}


def stars(sc) -> dict:
    truth = pd.read_csv(BENCH / "truth_data" / "ground_truth.csv", low_memory=False)
    d = ev.frame(truth[truth.truth_class.eq("STAR")], BENCH / "catalog_features")
    lam = pd.read_csv(BENCH / "spectro_truth" / "star_lamost_stellar5.csv.gz", low_memory=False)
    lam = lam.rename(columns={"Teff": "lamost_dr_catalog__lasp_teff", "logg": "lamost_dr_catalog__lasp_logg",
                              "[Fe/H]": "lamost_dr_catalog__lasp_feh"})
    d = d.merge(lam[["benchmark_id", "lamost_dr_catalog__lasp_teff", "lamost_dr_catalog__lasp_logg", "lamost_dr_catalog__lasp_feh"]],
                on="benchmark_id")
    cmd, spec, phot = [], [], []
    for r in d.to_dict("records"):
        r = _clean_row(r)
        lum, rule, _ = sc.star_luminosity_class(r, None)
        cmd.append(lum if rule == "GAIA_CMD" else None)
        no_plx = {k: v for k, v in r.items() if "parallax" not in k}
        lum2, rule2, _ = sc.star_luminosity_class(no_plx, None)
        spec.append(lum2 if rule2 == "LAMOST_LOGG" else None)
        no_spec = {k: v for k, v in no_plx.items() if not k.startswith("lamost_")}
        lum3, rule3, _ = sc.star_luminosity_class(no_spec, None)
        phot.append(lum3 if rule3 == "GAIA_LOGG" else None)
    d["cmd"], d["spec"], d["phot"] = cmd, spec, phot
    both = d.cmd.notna() & d.spec.notna()
    dw = both & d.cmd.eq("V")
    mh = pd.to_numeric(d.get("gaia_dr3__mh_gspphot"), errors="coerce")
    feh = d.lamost_dr_catalog__lasp_feh
    gi = d.spec.eq("III")
    return {"n_lamost": int(len(d)),
            "lamost_vs_cmd": pd.crosstab(d.cmd[both], d.spec[both]).to_dict(orient="index"),
            "cmd_dwarfs_lamost_dwarf": f"{int((d.spec[dw] == 'V').sum())}/{int(dw.sum())}",
            "lamost_giants_found_by_gspphot_logg": f"{int((d.phot[gi] == 'III').sum())}/{int((gi & d.phot.notna()).sum())}",
            "luminosity_class_without_parallax": int((d.cmd.isna() & d.spec.notna()).sum()),
            "metal_poor": {"lamost_feh_lt_-1": int((feh < -1).sum()), "gspphot_mh_lt_-1": int((mh < -1).sum()),
                           "both": int(((feh < -1) & (mh < -1)).sum())}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    warnings.filterwarnings("ignore")
    sc = ev.load_subclass()
    out = {"galaxies": galaxies(sc), "stars": stars(sc)}
    print(json.dumps(out, indent=1, default=str))
    if a.out:
        a.out.write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
