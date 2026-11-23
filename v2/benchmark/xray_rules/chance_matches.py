import numpy as np, pandas as pd
import astropy.units as u
from astropy.coordinates import SkyCoord
D="."
def tsv(name, cols):
    d = pd.read_csv(f"{D}/{name}.tsv", sep="\t", comment="#", skiprows=[1, 2], low_memory=False)
    d.columns = [c.strip() for c in d.columns]
    for c in cols: d[c] = pd.to_numeric(d[c], errors="coerce")
    return d.dropna(subset=cols[:2]).reset_index(drop=True)
s = pd.read_csv("sdss_star_qso.csv.gz", low_memory=False)
sub = s.subclass.astype(str).str.upper()
s = s[(s["class"] == "STAR") & ~(sub.str.contains("CV") | sub.str.startswith("WD") | sub.str.contains("WHITE"))]
cats = {"xmm": (tsv("xmm", ["RA_ICRS", "DE_ICRS", "ePos"]), "RA_ICRS", "DE_ICRS", "ePos", 3.0, 10.0, 3.0),
        "ero": (tsv("erass", ["RA_ICRS", "DE_ICRS", "posErr"]), "RA_ICRS", "DE_ICRS", "posErr", 5.0, 15.0, 3.0),
        "csc": (tsv("csc", ["RAICRS", "DEICRS", "r0"]), "RAICRS", "DEICRS", "r0", 2.0, 5.0, 2.0)}
for name, (cat, ra, de, err, floor, cap, k) in cats.items():
    cx = SkyCoord(cat[ra].values * u.deg, cat[de].values * u.deg)
    out = []
    for shift in (0.0, 1.0, -1.0, 2.0):
        co = SkyCoord(s.ra.values * u.deg, (s.dec.values + shift / 60) * u.deg)
        i, sep, _ = co.match_to_catalog_sky(cx)
        r = np.clip(k * cat[err].fillna(floor).values[i], floor, cap)
        ok = sep.arcsec <= r
        # only stars with an X-ray source within 3' (inside the X-ray footprint)
        near = sep.arcsec <= 180
        out.append((shift, int(ok.sum()), int(near.sum())))
    real = out[0][1]; chance = np.mean([o[1] for o in out[1:]])
    print(name, "real matches", real, "shifted (mean of 3)", round(chance, 1), "-> chance fraction", round(chance / real, 3), out)
