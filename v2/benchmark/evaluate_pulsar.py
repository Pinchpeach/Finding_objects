#!/usr/bin/env python3
"""Radio pulsar-candidate rule (Classifier/axes/compact.py) on ATNF pulsars vs
random NVSS sources (pulsar_truth/radio_sample.csv.gz, build_pulsar_truth.py).
All quantities are measured around the NVSS position for both samples.

    python v2/benchmark/evaluate_pulsar.py
"""

from __future__ import annotations
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

BENCH = Path(__file__).resolve().parent
V2 = BENCH.parent


def galactic_b(ra, dec):
    ra, dec = np.radians(ra), np.radians(dec)
    dg, ag = np.radians(27.12825), np.radians(192.85948)  # NGP (J2000)
    return np.degrees(np.arcsin(np.sin(dec) * np.sin(dg) + np.cos(dec) * np.cos(dg) * np.cos(ra - ag)))


def main() -> None:
    spec = importlib.util.spec_from_file_location("compact", V2 / "Classifier" / "axes" / "compact.py")
    c = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c)
    d = pd.read_csv(BENCH / "pulsar_truth" / "radio_sample.csv.gz", low_memory=False)
    # One row per radio source: globular-cluster pulsars share one NVSS source
    # (33 Terzan 5 pulsars -> one source), which would count one hit 33 times.
    n_rows = int(d.is_pulsar.eq(1).sum())
    d = d.sort_values("is_pulsar", ascending=False).drop_duplicates("nvss_NVSS").reset_index(drop=True)
    rows = d.rename(
        columns={
            "nvss_S1.4": "nvss__S1.4",
            "nvss_polFlux": "nvss__polFlux",
            "nvss_e_polFlux": "nvss__e_polFlux",
            "tgss_Stotal": "tgss_adr1__Stotal",
            "tgss_Speak": "tgss_adr1__Speak",
        }
    )
    ev = [
        c.radio_pulsar_evidence({k: v for k, v in r.items() if v == v})
        for r in rows[
            ["nvss__S1.4", "nvss__polFlux", "nvss__e_polFlux", "tgss_adr1__Stotal", "tgss_adr1__Speak"]
        ].to_dict("records")
    ]
    hit = pd.Series([e is not None for e in ev])
    pol = pd.Series([bool(e and e["significantly_polarised"]) for e in ev])
    p = d.is_pulsar.eq(1)
    alpha = np.log10(d.tgss_Stotal / d["nvss_S1.4"]) / np.log10(150 / 1400)
    fpol = d.nvss_polFlux / d["nvss_S1.4"]
    absb = np.abs(galactic_b(d.ra, d.dec))
    out = {
        "pulsar_rows": n_rows,
        "pulsars_nvss": int(p.sum()),
        "control_nvss": int((~p).sum()),
        "pulsars_with_tgss": int((p & d.tgss_Stotal.notna()).sum()),
        "median_alpha": {"pulsar": round(float(alpha[p].median()), 2), "control": round(float(alpha[~p].median()), 2)},
        "median_fractional_pol": {
            "pulsar": round(float(fpol[p].median()), 3),
            "control": round(float(fpol[~p].median()), 3),
        },
        "gaia_within_5arcsec": {
            "pulsar": round(float(d.gaia_Gmag[p].notna().mean()), 3),
            "control": round(float(d.gaia_Gmag[~p].notna().mean()), 3),
        },
        "rule_recall": round(float(hit[p].mean()), 3),
        "rule_false_positive_rate": round(float(hit[~p].mean()), 5),
        "rule_hits": {"pulsar": int(hit[p].sum()), "control": int(hit[~p].sum())},
        "significantly_polarised_hits": {"pulsar": int(pol[p].sum()), "control": int(pol[~p].sum())},
        "rule_hits_abs_b_lt_10": {
            "pulsar": int((hit & p & (absb < 10)).sum()),
            "control": int((hit & ~p & (absb < 10)).sum()),
        },
    }
    # Sky-level posterior of the candidates (compact.pulsar_posterior) by group.
    post = []
    for i, e in enumerate(ev):
        if e is not None:
            post.append(
                {
                    "pulsar": bool(p.iloc[i]),
                    "posterior": c.pulsar_posterior({"ra": d.ra.iloc[i], "dec": d.dec.iloc[i]}, dict(e)),
                    "plane": bool(absb.iloc[i] < 10),
                    "polarised": bool(e["significantly_polarised"]),
                }
            )
    pp = pd.DataFrame(post)
    out["candidate_posterior"] = {
        f"plane={pl},polarised={po}": {
            "pulsars": int(g.pulsar.sum()),
            "controls": int((~g.pulsar).sum()),
            "posterior": float(g.posterior.iloc[0]),
        }
        for (pl, po), g in pp.groupby(["plane", "polarised"])
    }
    print(json.dumps(out, indent=1))
    (BENCH / "pulsar_truth" / "pulsar_metrics.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
