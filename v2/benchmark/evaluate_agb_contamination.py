#!/usr/bin/env python3
"""How often does the AGB chemistry label non-AGB stars?

Sample: Gaia DR3 LPV stars in random 1-degree cones
(agb_truth/agb_gate_sample.csv.gz, build_agb_contamination.py).  SIMBAD is
not independent here (most types are the Gaia LPV import "LP?"), so the
truth is the Gaia luminosity for stars with a good parallax (S/N >= 5,
RUWE < 1.4), M_Ks = Ks + 5 log10(plx) - 10:

* M_Ks > -1        fainter than the red clump (M_Ks = -1.61; Alves 2000):
                   not AGB (dwarfs, subgiants, clump / low RGB);
* -6.2 < M_Ks <= -1 below the RGB tip (M_Ks = -6.2; Nikolaev & Weinberg
                   2000): red giants or early AGB, cannot be told apart
                   photometrically;
* M_Ks <= -6.2      above the tip: thermally pulsing AGB (or red supergiant
                   when M_bol = M_Ks - BC_K < -8, BC_K ~ 2.6 for M giants,
                   Bessell & Wood 1984 / Wagenhuber & Groenewegen 1998).

The classifier gets the pipeline columns of each star (Gaia, 2MASS, AllWISE,
Gaia LPV) and the AGB label it gives is counted per luminosity group.
"""
from __future__ import annotations
import json, sys, warnings
from pathlib import Path
import numpy as np
import pandas as pd

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
import evaluate_subclass as ev  # noqa: E402

MAP = {"g_bp": "gaia_dr3__phot_bp_mean_mag", "g_rp": "gaia_dr3__phot_rp_mean_mag", "g_gmag": "gaia_dr3__phot_g_mean_mag",
       "g_plx": "gaia_dr3__parallax", "g_eplx": "gaia_dr3__parallax_error", "g_ruwe": "gaia_dr3__ruwe",
       "tm_j": "2mass_psc__Jmag", "tm_ks": "2mass_psc__Kmag", "aw_w1": "allwise__W1mag", "aw_w2": "allwise__W2mag",
       "aw_w3": "allwise__W3mag", "aw_w4": "allwise__W4mag", "lpv_is_cstar": "gaia_lpv_is_cstar",
       "lpv_frequency": "gaia_lpv_frequency", "lpv_amplitude": "gaia_lpv_amplitude"}


def main() -> None:
    warnings.filterwarnings("ignore")
    sc = ev.load_subclass()
    d = pd.read_csv(BENCH / "agb_truth" / "agb_gate_sample.csv.gz", low_memory=False)
    good = (d.g_plx > 0) & (d.g_eplx > 0) & (d.g_plx / d.g_eplx >= 5) & (d.g_ruwe < 1.4)
    mk = d.tm_ks + 5 * np.log10(d.g_plx.where(d.g_plx > 0)) - 10
    d["group"] = np.select([~good | mk.isna(), mk > -1, mk > -6.2, mk + 2.6 < -8.0],
                           ["no good parallax", "below red clump", "below RGB tip", "RSG luminosity"], "above RGB tip")
    # M_bol = M_Ks + BC_K: RSG luminosity M_bol < -8 means M_Ks < -10.6
    rows = d.rename(columns=MAP)[list(MAP.values())]
    codes = []
    for r in rows.to_dict("records"):
        r = {k: v for k, v in r.items() if not (isinstance(v, float) and v != v)}
        r["primary_class"] = "STAR"
        codes.append(sc.classify(r)["code"])
    d["code"] = codes
    d["agb"] = d.code.astype(str).str.endswith(":AGB")
    out = {"n": int(len(d)), "cones": int(d.cone.nunique()),
           "simbad_types": {k: int(v) for k, v in d.simbad_otype.value_counts().head(12).items()}, "groups": {}}
    for gname, x in d.groupby("group"):
        out["groups"][gname] = {"n": int(len(x)), "agb_label": int(x.agb.sum()),
                                "codes": {k: int(v) for k, v in x.code.value_counts().head(6).items()}}
    print(json.dumps(out, indent=1))
    (BENCH / "agb_truth" / "agb_contamination_metrics.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
