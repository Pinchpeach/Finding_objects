#!/usr/bin/env python3
"""Photometric association prior (NWAY; Salvato et al. 2018, MNRAS 473, 4937).

NWAY's magnitude prior (nwaylib/magnitudeweights.py) compares a property of
secure counterparts (h_sel) with the same property over the field (h_all) in
adaptive bins (15 quantiles of the secure sample) and uses the normalised
ratio as a weight on the positional Bayes factor.  Here the property is the
colour between the optical anchor and a low-resolution catalogue:

  AllWISE: G - W1      2MASS PSC: G - Ks

* h_sel: objects of the independent fields (set A, blind runs) that hold both
  the Gaia row and the catalogue row (the associations made by position).
* h_all: chance pairs: the catalogue magnitude of one object with the Gaia G
  of another object 6-30" away (unrelated sources at a typical candidate
  distance).

Output: Preprocess/phot_prior.csv (catalog, lo, hi, weight, n_sel, n_all).
Usage: build_phot_prior.py FIELDS_DIR [FIELDS_DIR ...]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "Preprocess" / "phot_prior.csv"
BANDS = {"AllWISE": "allwise__W1mag", "2MASS PSC": "2mass_psc__Kmag"}
G = "gaia_dr3__phot_g_mean_mag"


def pairs(fields):
    sel = {c: [] for c in BANDS}
    alln = {c: [] for c in BANDS}
    for d in fields:
        for f in sorted(Path(d).glob("*/objects_blind.csv.gz")):
            o = pd.read_csv(f, low_memory=False)
            if G not in o:
                continue
            ra, dec = o.ra.to_numpy(float), o.dec.to_numpy(float)
            g = pd.to_numeric(o[G], errors="coerce").to_numpy()
            cosd = np.cos(np.radians(np.nanmedian(dec)))
            for cat, col in BANDS.items():
                if col not in o:
                    continue
                m = pd.to_numeric(o[col], errors="coerce").to_numpy()
                both = np.isfinite(m) & np.isfinite(g)
                sel[cat].append(g[both] - m[both])
                hosts = np.flatnonzero(np.isfinite(m))
                gs = np.flatnonzero(np.isfinite(g))
                if not len(hosts) or not len(gs):
                    continue
                for i in hosts:
                    sep = np.hypot((ra[gs] - ra[i]) * cosd, dec[gs] - dec[i]) * 3600
                    j = gs[(sep > 6) & (sep < 30)]
                    alln[cat].append(g[j] - m[i])
    return {c: np.concatenate(v) if v else np.array([]) for c, v in sel.items()}, {
        c: np.concatenate(v) if v else np.array([]) for c, v in alln.items()
    }


def weights(s, a):
    # nwaylib.magnitudeweights.adaptive_histograms + fraction
    x = np.unique(np.quantile(s, np.linspace(0, 1, 15)))
    lo, hi = min(a.min(), s.min()), max(a.max(), s.max())
    x = np.r_[lo - 1, x[1:-1], hi + 1]
    hs, _ = np.histogram(s, bins=x, density=True)
    ha, _ = np.histogram(a, bins=x, density=True)
    ok = ha > 0
    w = np.ones(len(hs))
    delta = np.diff(x)
    avg = (hs[ok] / ha[ok] * ha[ok] * delta[ok]).sum() / (ha[ok] * delta[ok]).sum()
    w[ok] = hs[ok] / ha[ok] / avg
    ns, _ = np.histogram(s, bins=x)
    na, _ = np.histogram(a, bins=x)
    return x, w, ns, na


def main():
    sel, alln = pairs(sys.argv[1:])
    rows = []
    for cat in BANDS:
        s, a = sel[cat], alln[cat]
        print(f"{cat}: secure {len(s)}, chance pairs {len(a)}")
        x, w, ns, na = weights(s, a)
        for k in range(len(w)):
            rows.append(dict(catalog=cat, lo=round(x[k], 3), hi=round(x[k + 1], 3), weight=round(float(w[k]), 4), n_sel=int(ns[k]), n_all=int(na[k])))
    t = pd.DataFrame(rows)
    t.to_csv(OUT, index=False)
    print(t.to_string(index=False))


if __name__ == "__main__":
    main()
