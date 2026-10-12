#!/usr/bin/env python3
"""RR Lyrae / eclipsing-binary agreement between ASAS-SN and ZTF (2.11.1),
with the ZTF g/r amplitude ratio as a physical arbiter
(rr_ew_truth/asassn_ztf.csv.gz, build_rr_ew_truth.py).

A pulsator's amplitude grows towards the blue (temperature change over the
cycle); a contact binary's amplitude is nearly achromatic.  Reports the type
cross-table, the A_g/A_r distribution per (ASAS-SN type, ZTF type), and what a
consistency veto at several thresholds would reject.

    python v2/benchmark/evaluate_rr_ew.py
"""
from __future__ import annotations
import json
from pathlib import Path

import pandas as pd

BENCH = Path(__file__).resolve().parent
PULS, ECL, RR = {"RR", "RRc"}, {"EW", "EA"}, {"RRAB", "RRC"}


def main() -> None:
    d = pd.read_csv(BENCH / "rr_ew_truth" / "asassn_ztf.csv.gz", low_memory=False)
    d = d[d.ztf_Type.notna() & (d.ztf_gAmp > 0) & (d.ztf_rAmp > 0)].copy()
    d["ratio"] = d.ztf_gAmp / d.ztf_rAmp
    d["pratio"] = d.ztf_Per / d.Per
    groups = {}
    for (t, z), g in d.groupby(["Type", "ztf_Type"]):
        if len(g) >= 10:
            groups[f"{t}->{z}"] = {"n": int(len(g)), "ratio_median": round(float(g.ratio.median()), 3),
                                   "ratio_p10_p90": [round(float(g.ratio.quantile(.1)), 3), round(float(g.ratio.quantile(.9)), 3)],
                                   "period_ratio_median": round(float(g.pratio.median()), 3)}
    test = d[d.rid % 2 == 1]
    veto = {}
    for lo, hi in ((1.15, 1.25), (1.18, 1.22), (1.20, 1.20)):
        rp = test.ztf_Type.isin(PULS) & (test.ratio < lo)
        re = test.ztf_Type.isin(ECL) & (test.ratio > hi)
        veto[f"{lo}/{hi}"] = {"pulsator_labels_rejected": int(rp.sum()), "of_which_asassn_agrees": int((rp & test.Type.isin(RR)).sum()),
                              "eclipsing_labels_rejected": int(re.sum()), "of_which_asassn_RR": int((re & test.Type.isin(RR)).sum())}
    out = {"n_matched": int(len(d)), "crosstab": pd.crosstab(d.Type, d.ztf_Type).to_dict(orient="index"),
           "groups": groups, "veto_on_odd_half": veto}
    print(json.dumps(out, indent=1))
    (BENCH / "rr_ew_truth" / "rr_ew_metrics.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
