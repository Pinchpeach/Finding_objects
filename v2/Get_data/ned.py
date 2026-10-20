"""NED cone-search collector. Extragalactic reference metadata."""

from pathlib import Path
import time
import pandas as pd

import sys

if str(Path(__file__).resolve().parent) not in sys.path:  # loaded by file path elsewhere
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import throttle  # noqa: E402

throttle.install()  # 3-5 s before every archive request (2.33.0)

CATALOG = "NED"


def _ned():
    """astroquery's NED client with the cone centre sent in fixed-point notation.

    astroquery sends ``lon`` (FK5 RA, decimal hours) and ``lat`` (degrees) as
    plain floats, and the ICRS->FK5 rotation leaves ~5e-7 where the input is 0,
    so the request carried e.g. ``lat=4.847e-07``.  NED reads such a value
    without its exponent: the RA 20, Dec 0 field came back from Dec +4.85
    (247 NED objects 4.8 deg away, all left unclassified; 2.33.0).  An RA near 0
    is misread the same way.  1e-9 h and 1e-8 deg are below 0.1 mas.
    """
    from astroquery.ipac.ned.core import NedClass

    class FixedPointNed(NedClass):
        def _request(self, method, url, params=None, **kwargs):
            if params and "lon" in params and "lat" in params:
                params = {**params, "lon": f"{float(params['lon']):.9f}", "lat": f"{float(params['lat']):.8f}"}
            return super()._request(method, url, params=params, **kwargs)

    return FixedPointNed()


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    Ned = _ned()
    center = SkyCoord(ra * u.deg, dec * u.deg)
    attempts = 2  # each attempt already has astroquery's 60 s read timeout
    for attempt in range(attempts):
        try:
            t = Ned.query_region(center, radius=radius_arcmin * u.arcmin)
            if t is None:
                return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec"])
            df = t.to_pandas()
            n = "Object Name"
            df.insert(0, "catalog", CATALOG)
            df.insert(1, "catalog_object_id", df[n].astype("string"))
            df.insert(2, "object_name", df[n].astype("string"))
            df.insert(3, "ra", pd.to_numeric(df["RA"], errors="coerce"))
            df.insert(4, "dec", pd.to_numeric(df["DEC"], errors="coerce"))
            return df.drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(2**attempt)


def save(df, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("catalog_object_id", keep="last").to_csv(path, index=False)
