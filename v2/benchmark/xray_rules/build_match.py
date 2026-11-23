import sys, numpy as np, pandas as pd
import astropy.units as u
from astropy.coordinates import SkyCoord
D = sys.argv[1]
def tsv(name, cols):
    d = pd.read_csv(f"{D}/{name}.tsv", sep="\t", comment="#", skiprows=[1, 2], skip_blank_lines=True, low_memory=False)
    d.columns = [c.strip() for c in d.columns]
    for c in cols: d[c] = pd.to_numeric(d[c], errors="coerce")
    return d.dropna(subset=cols[:2]).reset_index(drop=True)
xmm = tsv("xmm", ["RA_ICRS", "DE_ICRS", "ePos", "Flux8", "e_Flux8", "F8max", "HR1", "ext", "srcML"])
ero = tsv("erass", ["RA_ICRS", "DE_ICRS", "posErr", "EXT", "DetLike0", "MLFlux1", "e_MLFlux1"])
csc = tsv("csc", ["RAICRS", "DEICRS", "r0", "fe", "Favgb", "S/N"])
print(len(xmm), len(ero), len(csc))
# compact-object truth
rk = pd.read_csv(f"{D}/rk.csv.gz")
c = SkyCoord(rk.RAJ2000.astype(str), rk.DEJ2000.astype(str), unit=(u.hourangle, u.deg))
T = [pd.DataFrame({"name": rk.Name, "ra": c.ra.deg, "dec": c.dec.deg, "truth": "CV", "subtype": rk.Type1, "source": "Ritter&Kolb 7.24"})]
n = pd.read_csv(f"{D}/neumann_hmxb.csv.gz"); T.append(pd.DataFrame({"name": n.Name, "ra": n.RA_ICRS, "dec": n.DE_ICRS, "truth": "HMXB", "subtype": n.XrayType, "source": "Neumann+2023"}))
a = pd.read_csv(f"{D}/avakyan_lmxb.csv.gz"); T.append(pd.DataFrame({"name": a.Name, "ra": a.RA_ICRS, "dec": a.DE_ICRS, "truth": "LMXB", "subtype": a.XrayType, "source": "Avakyan+2023"}))
f = pd.read_csv(f"{D}/fortin_hmxb.csv.gz"); T.append(pd.DataFrame({"name": f.ID, "ra": f.RAJ2000, "dec": f.DEJ2000, "truth": "HMXB", "subtype": f.Class, "source": "Fortin+2023"}))
g = pd.read_csv(f"{D}/fortin_lmxb.csv.gz"); T.append(pd.DataFrame({"name": g.MainID, "ra": g.RAJ2000, "dec": g.DEJ2000, "truth": "LMXB", "subtype": g.Compact, "source": "Fortin+2024"}))
t = pd.concat(T, ignore_index=True)
t["ra"] = pd.to_numeric(t.ra, errors="coerce"); t["dec"] = pd.to_numeric(t.dec, errors="coerce")
t = t.dropna(subset=["ra", "dec"]).reset_index(drop=True)
# one object listed twice (Neumann/Fortin, Avakyan/Fortin): keep the first within 3"
ct = SkyCoord(t.ra.values * u.deg, t.dec.values * u.deg)
i1, i2, sep, _ = ct.search_around_sky(ct, 3 * u.arcsec)
dup = set(j for i, j in zip(i1, i2) if j > i)
t = t.drop(index=list(dup)).reset_index(drop=True)
print("truth", t.truth.value_counts().to_dict(), "dropped duplicates", len(dup))
h = pd.read_csv(f"{D}/hamstar.csv.gz")
h = h[h.CtpRank == 1]
ctl = pd.DataFrame({"name": h.ERO, "ra": h.RAJ2000, "dec": h.DEJ2000, "truth": "CORONAL_STAR", "subtype": h.SOType, "source": "Freund+2024 HamStar",
                    "ham_fx": h.FX, "ham_g": h.Gmag, "ham_bp_rp": h["BP-RP"], "ham_p_coronal": h["p-coronal"], "ham_coronal": h.Coronal, "ham_train": h.TrainSet, "ham_ob": h["OB-Star"], "gaia_id": h.CtpId, "ham_ctp_sep": h.CtpSep})
allo = pd.concat([t, ctl], ignore_index=True)
co = SkyCoord(allo.ra.values * u.deg, allo.dec.values * u.deg)
def nearest(cat, ra, dec, err, floor, cap, k, prefix, cols):
    cx = SkyCoord(cat[ra].values * u.deg, cat[dec].values * u.deg)
    i, sep, _ = co.match_to_catalog_sky(cx)
    r = np.clip(k * cat[err].fillna(floor).values[i], floor, cap)
    ok = sep.arcsec <= r
    allo[prefix + "sep"] = np.where(ok, sep.arcsec, np.nan)
    for c_ in cols:
        allo[prefix + c_] = np.where(ok, cat[c_].values[i], np.nan)
    allo[prefix + "name"] = np.where(ok, cat[cat.columns[0]].astype(str).str.strip().values[i], None)
    print(prefix, "matched", int(ok.sum()), allo[ok].truth.value_counts().to_dict())
nearest(xmm, "RA_ICRS", "DE_ICRS", "ePos", 3.0, 10.0, 3.0, "xmm_", ["Flux8", "e_Flux8", "F8max", "HR1", "ext", "srcML", "ePos"])
nearest(ero, "RA_ICRS", "DE_ICRS", "posErr", 5.0, 15.0, 3.0, "ero_", ["MLFlux1", "e_MLFlux1", "posErr", "EXT", "DetLike0"])
nearest(csc, "RAICRS", "DEICRS", "r0", 2.0, 5.0, 2.0, "csc_", ["Favgb", "S/N", "r0", "fe"])
keep = (allo.truth != "CORONAL_STAR") | allo.xmm_sep.notna() | allo.csc_sep.notna()
allo.to_pickle(f"{D}/all.pkl")
allo[keep].to_csv(f"{D}/need_phot.csv", index=False)
print("need Gaia/2MASS photometry for", int(keep.sum()), allo[keep].truth.value_counts().to_dict())
