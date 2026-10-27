"""Probe the catalogues planned for 2.42.0 (young stars in nebulae).

Prints table/column names and member counts around the ONC, NGC 2024 and M8
for: MYStIX MPCM (Broos et al. 2013), SFiNCs (Getman et al. 2017), Hunt &
Reffert 2023/2024 cluster members, the Rybizki et al. 2022 Gaia astrometric
fidelity (GAVO TAP gedr3spur.main), and the 2MASS PSC flags of the stars the
2.41.0 count prior left unclassified.  Nothing is stored.
"""
import time
import traceback

import astropy.units as u
from astropy.coordinates import SkyCoord
from astroquery.vizier import Vizier

FIELDS = {"onc": (83.82, -5.39), "ngc2024": (85.42, -1.90), "m8": (270.90, -24.38)}


def show(title, fn):
    print(f"\n######## {title}", flush=True)
    try:
        fn()
    except Exception:
        traceback.print_exc()
    time.sleep(4)


def vizier_catalog(cat):
    def run():
        v = Vizier(columns=["**"], row_limit=5)
        tabs = v.get_catalogs(cat)
        for t in tabs:
            print("TABLE", t.meta.get("name"), len(t), "rows (first 5)")
            print("  COLUMNS", list(t.colnames))
            for c in t.colnames:
                d = t[c].description or ""
                print(f"    {c}: {d[:90]}")
        for name, (ra, dec) in FIELDS.items():
            v2 = Vizier(columns=["**"], row_limit=-1)
            res = v2.query_region(SkyCoord(ra * u.deg, dec * u.deg), radius=6 * u.arcmin, catalog=cat)
            print("CONE", name, {t.meta.get("name"): len(t) for t in res})
            time.sleep(4)
    return run


def tap_fidelity():
    import pyvo
    tap = pyvo.dal.TAPService("https://dc.zah.uni-heidelberg.de/tap")
    cols = tap.search("SELECT column_name, description FROM TAP_SCHEMA.columns WHERE table_name='gedr3spur.main'")
    for r in cols:
        print("  ", r["column_name"], ":", str(r["description"])[:100])
    for name, (ra, dec) in FIELDS.items():
        q = (
            "SELECT s.source_id, s.fidelity_v2, g.phot_g_mean_mag FROM gedr3spur.main AS s "
            "JOIN gaia.edr3lite AS g ON g.source_id = s.source_id "
            f"WHERE 1=CONTAINS(POINT('ICRS', g.ra, g.dec), CIRCLE('ICRS', {ra}, {dec}, 0.05))"
        )
        t = tap.search(q).to_table()
        f = t["fidelity_v2"]
        print("CONE", name, len(t), "rows; fidelity_v2 > 0.5:", int((f > 0.5).sum()), "; median", float(f.mean()) if len(t) else None)
        time.sleep(4)


STARS = [(85.38111, -1.92581), (85.41014, -1.84407), (85.41153, -1.93406), (85.41331, -1.90396), (85.41741, -1.89286),
         (85.43803, -1.91308), (85.44258, -1.89634), (85.47454, -1.92126), (83.79232, -5.32551), (83.81411, -5.46318)]


def twomass_flags():
    v = Vizier(columns=["2MASS", "Jmag", "Hmag", "Kmag", "Qflg", "Rflg", "Bflg", "Cflg", "Xflg", "Aflg"], row_limit=-1)
    for ra, dec in STARS:
        res = v.query_region(SkyCoord(ra * u.deg, dec * u.deg), radius=2.5 * u.arcsec, catalog="II/246/out")
        rows = [dict(zip(t.colnames, [str(x) for x in r])) for t in res for r in t]
        print(ra, dec, rows)
        time.sleep(3)


if __name__ == "__main__":
    show("MYStIX MPCM J/ApJS/209/32", vizier_catalog("J/ApJS/209/32"))
    show("SFiNCs J/ApJS/229/28", vizier_catalog("J/ApJS/229/28"))
    show("Hunt & Reffert 2023 J/A+A/673/A114", vizier_catalog("J/A+A/673/A114"))
    show("Hunt & Reffert 2024 J/A+A/686/A42", vizier_catalog("J/A+A/686/A42"))
    show("Rybizki+2022 fidelity (GAVO TAP)", tap_fidelity)
    show("2MASS flags of unclassified nebula stars", twomass_flags)
