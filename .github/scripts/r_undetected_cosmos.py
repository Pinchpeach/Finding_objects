"""r-undetected Legacy Surveys sources in COSMOS against COSMOS2020 (2.55.0).

The deep-field A/B truth (score_independent_fields: HST/ACS F814W < 24.5 with
ACS and LePhare agreeing) holds almost none of the faint sources seen only in
z, so this matches those sources directly to COSMOS2020 (Weaver et al. 2022,
ApJS 258, 11): the LePhare SED type from 30+ bands (lptype 0 galaxy, 1 star,
2 X-ray AGN) for every one, and the ACS point-source class where F814W
exists.

    python r_undetected_cosmos.py RA DEC RADIUS RAW_DIR OLD_WORK NEW_WORK
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

LS = "desi_legacy_surveys_dr10__"


def cosmos2020(ra, dec, radius):
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    from astroquery.vizier import Vizier

    for host in ("vizier.cds.unistra.fr", "vizier.cfa.harvard.edu", "vizier.idia.ac.za"):
        v = Vizier(columns=["_RAJ2000", "_DEJ2000", "ACSF814Wmag", "ACSmuClass", "lptype", "HSCimagAuto"], row_limit=-1)
        v.VIZIER_SERVER = host
        v.TIMEOUT = 300
        try:
            res = v.query_region(SkyCoord(ra * u.deg, dec * u.deg), radius=radius * u.arcmin, catalog="J/ApJS/258/11/classic")
            if len(res):
                print("COSMOS2020 from", host, len(res[0]), "rows")
                return res[0].to_pandas()
        except Exception as exc:  # noqa: BLE001
            print("mirror failed", host, exc)
    raise RuntimeError("COSMOS2020 not reachable")


def r_undetected(d):
    top = d[d.parent_object_id.isna()] if "parent_object_id" in d else d
    num = lambda c: pd.to_numeric(top[c], errors="coerce") if c in top else pd.Series(np.nan, index=top.index)
    u = (num(LS + "flux_r") <= 0) & (num(LS + "flux_z") > 0) & (num(LS + "flux_ivar_r") > 0)
    return top[u]


def main():
    ra, dec, radius = map(float, sys.argv[1:4])
    old, new = Path(sys.argv[5]), Path(sys.argv[6])
    c = cosmos2020(ra, dec, radius)
    a = pd.read_csv(old / "classified_objects.csv", low_memory=False)
    b = pd.read_csv(new / "classified_objects.csv", low_memory=False).set_index("object_id")
    x = r_undetected(a).set_index("object_id").copy()
    x["new"] = b.primary_class.reindex(x.index)
    x["new_status"] = b.classification_status.reindex(x.index)
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    oc = SkyCoord(x.ra.to_numpy() * u.deg, x.dec.to_numpy() * u.deg)
    cc = SkyCoord(c._RAJ2000.to_numpy() * u.deg, c._DEJ2000.to_numpy() * u.deg)
    i, sep, _ = oc.match_to_catalog_sky(cc)
    m = sep.arcsec <= 1.0
    x["sep"] = sep.arcsec
    for col in ("lptype", "ACSmuClass", "ACSF814Wmag", "HSCimagAuto"):
        x[col] = np.where(m, c[col].to_numpy()[i], np.nan)
    x["zmag"] = 22.5 - 2.5 * np.log10(pd.to_numeric(x[LS + "flux_z"], errors="coerce"))
    seen = x[[k for k in ("gaia_dr3__phot_g_mean_mag", "std_mag__ps1_r", "std_mag__sdss_r") if k in x]].apply(pd.to_numeric, errors="coerce").notna().any(axis=1)
    x["group"] = np.where(seen | (x.zmag < 20), "seen elsewhere / bright z", "faint z-only")
    sed = x.lptype.map({0: "SED galaxy", 1: "SED star", 2: "SED X-ray AGN"}).fillna("no COSMOS2020 match")
    print(f"\nr-undetected top-level sources: {len(x)}; matched to COSMOS2020 within 1\": {int(m.sum())}")
    for g, s in x.groupby("group"):
        print(f"\n== {g}: {len(s)}")
        print("LS type:", s[LS + "type"].value_counts().to_dict(), "| z mag quartiles:", s.zmag.quantile([0.25, 0.5, 0.75]).round(2).to_dict())
        print("2.54 (old) label x COSMOS2020 SED type:")
        print(pd.crosstab(s.primary_class, sed[s.index]))
        print("2.55 (new) label x COSMOS2020 SED type:")
        print(pd.crosstab(s.new, sed[s.index]))
        acs = s.ACSmuClass.map({1: "ACS galaxy", 2: "ACS point", 3: "ACS spurious"}).fillna("no ACS")
        print("ACS class x SED type:")
        print(pd.crosstab(acs, sed[s.index]))
    x.reset_index()[["object_id", "ra", "dec", "group", LS + "type", "zmag", "primary_class", "new", "new_status", "lptype", "ACSmuClass", "ACSF814Wmag", "sep"]].to_csv(
        "r_undetected_cosmos.csv", index=False
    )


if __name__ == "__main__":
    main()
