"""ZTF light-curve variability features (IRSA ZTF light-curve API, 2.27.0).
No classification here.

Queries the IRSA ZTF light-curve service (Masci et al. 2019, PASP 131,
018003) for every ZTF object in the cone (g and r band PSF-fit light curves,
public data releases), and reduces each light curve to the aperiodic
variability statistics used to separate quasars from stars:

* ``n``: good epochs (catflags == 0, magerr < 0.3);
* ``mag``: median magnitude;
* ``rms``: robust scatter (1.4826 MAD);
* ``chi2r``: reduced chi^2 about the weighted mean (variability significance);
* ``exvar``: normalised excess variance, (var - <err^2>) / mean^2 of the
  fluxes (Nandra et al. 1997; ALeRCE ``ExcessVar``, Sanchez-Saez et al. 2021,
  AJ 161, 141);
* ``sf_a``, ``sf_gamma``: structure-function amplitude at 1 yr and slope,
  SF(dt) = A (dt / 1 yr)^gamma fitted to the noise-subtracted rms magnitude
  difference of all epoch pairs (Schmidt et al. 2010, ApJ 714, 1194:
  quasars have A > ~0.07 and gamma > ~0.3; most stars A ~ 0, Palanque-
  Delabrouille et al. 2011, A&A 530, A122).

ZTF keeps separate object IDs per field, CCD quadrant and filter; IDs within
1.5" are merged into one source, keeping the best-sampled ID per filter.
"""

from __future__ import annotations

import io
import math
from pathlib import Path

import numpy as np
import pandas as pd

CATALOG = "ZTF light curves"
URL = "https://irsa.ipac.caltech.edu/cgi-bin/ZTF/nph_light_curves"
MERGE_ARCSEC = 1.5
MIN_EPOCHS = 10
TIMEOUT_S = 120
FILTERS = {"zg": "g", "zr": "r"}


def _sf(t, m, e):
    """(A, gamma) of SF(dt) = A (dt/365.25)^gamma; noise-subtracted pair
    variance in log-spaced dt bins from 1 d (Schmidt et al. 2010, Eq. 2)."""
    if len(t) < MIN_EPOCHS:
        return np.nan, np.nan
    if len(t) > 400:  # pair count grows as n^2; keep an even time sample
        idx = np.linspace(0, len(t) - 1, 400).astype(int)
        t, m, e = t[idx], m[idx], e[idx]
    i, j = np.triu_indices(len(t), 1)
    dt = np.abs(t[j] - t[i])
    dm2 = (m[j] - m[i]) ** 2 - e[i] ** 2 - e[j] ** 2
    edges = np.logspace(0, math.log10(max(dt.max(), 2.0)), 9)
    x, y = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        k = (dt >= lo) & (dt < hi)
        if k.sum() >= 10:
            v = float(np.mean(dm2[k]))
            if v > 0:
                x.append(math.log10(np.sqrt(lo * hi) / 365.25))
                y.append(0.5 * math.log10(v))
    if len(x) < 3:
        return 0.0, np.nan  # no variability above the noise
    g, c = np.polyfit(x, y, 1)
    return float(10**c), float(g)


def features(lc: pd.DataFrame) -> dict:
    """Variability statistics of one filter's light curve (mjd, mag, magerr)."""
    t = lc["mjd"].to_numpy(float)
    m = lc["mag"].to_numpy(float)
    e = lc["magerr"].to_numpy(float)
    o = np.argsort(t)
    t, m, e = t[o], m[o], e[o]
    out = {"n": int(len(m))}
    if len(m) < MIN_EPOCHS:
        return out
    w = 1 / e**2
    mean = float(np.sum(w * m) / np.sum(w))
    out["mag"] = float(np.median(m))
    out["rms"] = float(1.4826 * np.median(np.abs(m - np.median(m))))
    out["chi2r"] = float(np.sum(((m - mean) / e) ** 2) / (len(m) - 1))
    f = 10 ** (-0.4 * m)
    fe = f * e * math.log(10) / 2.5
    out["exvar"] = float((np.var(f, ddof=1) - np.mean(fe**2)) / np.mean(f) ** 2)
    out["sf_a"], out["sf_gamma"] = _sf(t, m, e)
    return out


def reduce(raw: pd.DataFrame) -> pd.DataFrame:
    """Per-source g/r variability features from IRSA light-curve rows."""
    cols = ["catalog", "catalog_object_id", "object_name", "ra", "dec"]
    if raw is None or raw.empty:
        return pd.DataFrame(columns=cols)
    d = raw.copy()
    for c in ("mjd", "mag", "magerr", "ra", "dec", "catflags"):
        if c in d:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    good = d.mag.notna() & d.magerr.between(0, 0.3) & d.mjd.notna()
    if "catflags" in d:
        good &= d.catflags.fillna(0).eq(0)
    d = d[good & d.filtercode.isin(FILTERS)]
    if d.empty:
        return pd.DataFrame(columns=cols)
    ids = d.groupby("oid").agg(ra=("ra", "mean"), dec=("dec", "mean"), n=("mag", "size"), f=("filtercode", "first"))
    ids = ids.sort_values("n", ascending=False)
    # Merge IDs of the same source (other fields / quadrants / filters).
    groups = []
    for oid, r in ids.iterrows():
        for g in groups:
            dra = (r.ra - g["ra"]) * math.cos(math.radians(g["dec"])) * 3600
            if math.hypot(dra, (r.dec - g["dec"]) * 3600) < MERGE_ARCSEC:
                g["oids"].append((oid, r.f))
                break
        else:
            groups.append({"ra": r.ra, "dec": r.dec, "oids": [(oid, r.f)]})
    rows = []
    for g in groups:
        row = {"catalog": CATALOG, "catalog_object_id": str(g["oids"][0][0]), "ra": g["ra"], "dec": g["dec"]}
        for code, band in FILTERS.items():
            best = next((oid for oid, f in g["oids"] if f == code), None)  # IDs are sorted by epochs
            if best is None:
                continue
            for k, v in features(d[d.oid == best]).items():
                row[f"ztf_{band}_{k}"] = v
        rows.append(row)
    out = pd.DataFrame(rows)
    out.insert(2, "object_name", out["catalog_object_id"])
    return out


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    import requests

    params = {
        "POS": f"CIRCLE {ra:.7f} {dec:.7f} {radius_arcmin / 60:.6f}",
        "BANDNAME": "g,r",
        "FORMAT": "csv",
    }
    r = requests.get(URL, params=params, timeout=TIMEOUT_S)
    if r.status_code >= 400:
        # IRSA explains refusals (e.g. load limits) in the body; keep it in the error.
        raise RuntimeError(f"IRSA ZTF HTTP {r.status_code}: {r.text[:300]!r}")
    text = r.text
    if not text.strip() or text.lstrip().startswith("<"):
        if "error" in text.lower() or "fault" in text.lower():
            raise RuntimeError(f"IRSA ZTF error: {text[:200]}")
        return reduce(pd.DataFrame())
    return reduce(pd.read_csv(io.StringIO(text), low_memory=False))


def save(df: pd.DataFrame, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("catalog_object_id", keep="last").to_csv(path, index=False)
