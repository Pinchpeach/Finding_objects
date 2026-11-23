"""Build the X-ray rule test sample: compact-object truth, HamStar coronal controls, SDSS spectroscopic
stars (independent control) and QSOs, each with 4XMM / eRASS1 / CSC fluxes, Gaia DR3 and 2MASS (GAVO TAP)."""
import sys, numpy as np, pandas as pd, pyvo
import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.table import Table
D = sys.argv[1]
allo = pd.read_pickle(f"{D}/all.pkl")
t = allo[allo.truth != "CORONAL_STAR"].copy()
h = allo[allo.truth == "CORONAL_STAR"].copy()
h_x = h[h.xmm_sep.notna() | h.csc_sep.notna()]
h_e = h[h.ero_sep.notna() & h.xmm_sep.isna() & h.csc_sep.isna()].sample(20000, random_state=1)
h = pd.concat([h_x, h_e]); h["truth"] = "CORONAL_STAR_HAMSTAR"
# SDSS DR18 spectroscopic stars (no CV / WD) and QSOs, zWarning = 0
s = pd.read_csv(f"{D}/sdss_star_qso.csv.gz", low_memory=False)
sub = s.subclass.astype(str).str.upper()
s = s[(s["class"] == "QSO") | ~(sub.str.contains("CV") | sub.str.startswith("WD") | sub.str.contains("WHITE"))]
s = pd.DataFrame({"name": "SDSS " + s.index.astype(str), "ra": s.ra, "dec": s.dec,
                  "truth": np.where(s["class"] == "STAR", "STAR_SDSS_SPEC", "QSO_SDSS_SPEC"), "subtype": s.subclass, "source": "SDSS DR18 spec", "z": s.z})
# drop SDSS objects that are compact-object truth (3")
cs, ct = SkyCoord(s.ra.values * u.deg, s.dec.values * u.deg), SkyCoord(t.ra.values * u.deg, t.dec.values * u.deg)
i, sep, _ = cs.match_to_catalog_sky(ct); s = s[sep.arcsec > 3].reset_index(drop=True)
def tsv(name, cols):
    d = pd.read_csv(f"{D}/{name}.tsv", sep="\t", comment="#", skiprows=[1, 2], low_memory=False)
    d.columns = [c.strip() for c in d.columns]
    for c in cols: d[c] = pd.to_numeric(d[c], errors="coerce")
    return d.dropna(subset=cols[:2]).reset_index(drop=True)
cats = {"xmm_": (tsv("xmm", ["RA_ICRS", "DE_ICRS", "ePos", "Flux8", "e_Flux8", "F8max", "HR1", "ext", "srcML"]), "RA_ICRS", "DE_ICRS", "ePos", 3.0, 10.0, 3.0, ["Flux8", "e_Flux8", "F8max", "HR1", "ext", "srcML", "ePos"]),
        "ero_": (tsv("erass", ["RA_ICRS", "DE_ICRS", "posErr", "EXT", "DetLike0", "MLFlux1", "e_MLFlux1"]), "RA_ICRS", "DE_ICRS", "posErr", 5.0, 15.0, 3.0, ["MLFlux1", "e_MLFlux1", "posErr", "EXT", "DetLike0"]),
        "csc_": (tsv("csc", ["RAICRS", "DEICRS", "r0", "fe", "Favgb", "S/N"]), "RAICRS", "DEICRS", "r0", 2.0, 5.0, 2.0, ["Favgb", "S/N", "r0", "fe"])}
co = SkyCoord(s.ra.values * u.deg, s.dec.values * u.deg)
for p, (cat, ra, de, err, floor, cap, k, cols) in cats.items():
    cx = SkyCoord(cat[ra].values * u.deg, cat[de].values * u.deg)
    i, sep, _ = co.match_to_catalog_sky(cx)
    ok = sep.arcsec <= np.clip(k * cat[err].fillna(floor).values[i], floor, cap)
    s[p + "sep"] = np.where(ok, sep.arcsec, np.nan)
    for c in cols: s[p + c] = np.where(ok, cat[c].values[i], np.nan)
s = s[s.xmm_sep.notna() | s.ero_sep.notna() | s.csc_sep.notna()]
print("SDSS spectra with an X-ray match:", s.truth.value_counts().to_dict())
m = pd.concat([t, h, s], ignore_index=True).reset_index(drop=True)
m["k"] = np.arange(len(m))
m.to_pickle(f"{D}/sample_pre.pkl")
svc = pyvo.dal.TAPService("https://dc.zah.uni-heidelberg.de/tap")
def xmatch(table, cols, ra, de, r):
    out = []
    for st in range(0, len(m), 5000):
        up = Table({"k": m.k.values[st:st + 5000], "ra": m.ra.values[st:st + 5000], "dec": m.dec.values[st:st + 5000]})
        q = (f"SELECT u.k, {', '.join('x.' + c for c in cols)}, DISTANCE(POINT(u.ra,u.dec), POINT(x.{ra},x.{de}))*3600 AS sep "
             f"FROM TAP_UPLOAD.u AS u JOIN {table} AS x ON DISTANCE(POINT(u.ra,u.dec), POINT(x.{ra},x.{de})) < {r}/3600.")
        for attempt in range(4):
            try:
                out.append(svc.run_sync(q, uploads={"u": up}, maxrec=10**6).to_table().to_pandas()); break
            except Exception as e:
                print("retry", type(e).__name__, str(e)[:120], flush=True); __import__("time").sleep(20)
        else:
            raise RuntimeError(table)
        print(table, st, len(out[-1]), flush=True)
    x = pd.concat(out).sort_values("sep").drop_duplicates("k")
    return x
gcols = ["source_id", "ra", "dec", "parallax", "parallax_error", "pmra", "pmra_error", "pmdec", "pmdec_error", "ruwe",
         "phot_g_mean_mag", "phot_bp_mean_mag", "phot_rp_mean_mag", "phot_g_mean_flux_over_error", "phot_bp_mean_flux_over_error",
         "phot_rp_mean_flux_over_error", "phot_bp_rp_excess_factor"]
g = xmatch("gaia.dr3lite", gcols, "ra", "dec", 3.0).add_prefix("g_").rename(columns={"g_k": "k"})
k2 = xmatch("twomass.data", ["mainid", "kmag", "e_kmag", "qflg"], "raj2000", "dej2000", 3.0).add_prefix("t_").rename(columns={"t_k": "k"})
m = m.merge(g, on="k", how="left").merge(k2, on="k", how="left")
# HamStar: use its own Gaia counterpart (exact source_id) when the nearest Gaia star is another one
m.to_pickle(f"{D}/sample.pkl")
print(m.groupby("truth").agg(n=("k", "size"), gaia=("g_source_id", lambda x: x.notna().sum()), tmass=("t_kmag", lambda x: x.notna().sum())))
