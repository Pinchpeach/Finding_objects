"""Do the archive queries put the cone where we asked? (2.33.0)

Each collector is queried at centres whose coordinates are 0 or within 1e-4
deg of 0 (where str(float) switches to exponent notation and frame rotations
leave ~5e-7 residuals) and at an ordinary centre.  For every answer the
offset of the returned rows from the requested centre is printed: a correct
query has all rows inside the radius.  NED is also queried with astroquery's
own client to show the 2.32 fault next to the fixed collector.
"""

import importlib.util
import math
import sys
import time

import numpy as np

sys.path.insert(0, "v2/Get_data")
import throttle  # noqa: E402

throttle.install()

RADIUS_ARCMIN = 2.0
CENTRES = [(20.0, 0.0), (20.0, 0.00005), (0.00005, 10.0), (245.0, 43.0)]
COLLECTORS = ["ned", "simbad", "gaia_dr3", "panstarrs1", "sdss_dr18", "allwise", "atnf_pulsar", "desi_legacy"]


def load(name):
    spec = importlib.util.spec_from_file_location(name, f"v2/Get_data/{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def offsets(df, ra, dec):
    r = np.asarray(df["ra"], float)
    d = np.asarray(df["dec"], float)
    dra = (r - ra + 180.0) % 360.0 - 180.0
    return np.hypot(dra * math.cos(math.radians(dec)), d - dec) * 60.0  # arcmin


def report(label, df, ra, dec):
    if df is None or len(df) == 0:
        print(f"  {label:28s} rows=0")
        return
    off = offsets(df, ra, dec)
    off = off[np.isfinite(off)]
    print(
        f"  {label:28s} rows={len(df):5d} offset arcmin min/median/max="
        f"{off.min():.2f}/{np.median(off):.2f}/{off.max():.2f} outside radius: {int((off > RADIUS_ARCMIN * 1.02).sum())}"
    )


for ra, dec in CENTRES:
    print(f"\n== centre RA {ra!r} Dec {dec!r}, radius {RADIUS_ARCMIN}'")
    for name in COLLECTORS:
        t0 = time.monotonic()
        try:
            df = load(name).fetch(ra, dec, RADIUS_ARCMIN)
            report(name, df, ra, dec)
        except Exception as exc:
            print(f"  {name:28s} error {type(exc).__name__}: {str(exc)[:110]}")
        print(f"  {'':28s} ({time.monotonic() - t0:.1f} s)")
    try:  # astroquery's own NED client, for comparison
        from astroquery.ipac.ned import Ned
        from astropy.coordinates import SkyCoord
        import astropy.units as u

        t = Ned.query_region(SkyCoord(ra * u.deg, dec * u.deg), radius=RADIUS_ARCMIN * u.arcmin)
        df = t.to_pandas().rename(columns={"RA": "ra", "DEC": "dec"}) if t is not None else None
        report("ned (astroquery as is)", df, ra, dec)
    except Exception as exc:
        print(f"  {'ned (astroquery as is)':28s} error {type(exc).__name__}: {str(exc)[:110]}")
