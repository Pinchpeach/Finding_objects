"""Survey footprints with a documented hard edge (2.54.0).

A collector may declare ``FOOTPRINT``; the controller then skips the query
when the whole search cone lies more than MARGIN_DEG outside it (status
``outside_footprint``, no request).  Only edges that the survey papers state
as limits are used, and the margin keeps every cone near an edge queried:

  dec_min        the survey covers the sky north of this declination
                 (NVSS -40: Condon et al. 1998, AJ 115, 1693; VLASS -40:
                 Lacy et al. 2020, PASP 132, 035001, Gordon et al. 2021,
                 ApJS 255, 30; TGSS ADR1 -53: Intema et al. 2017, A&A 598, A78)
  gal_l_range    Galactic longitude interval (eRASS1 of eROSITA-DE:
                 179.9442 < l < 359.9442 deg, Merloni et al. 2024, A&A 682, A34)
  tiles          the survey's observed pointings (2.59.0): a tile list file of
                 centres (ra, dec in degrees) and the radius around a centre
                 that holds its objects.  DESI DR1: tiles-iron.csv, the
                 public tile list of the DR1 ("iron") reduction, 6,101 tiles
                 at 4,648 distinct centres, -30 < dec < +83
                 (https://data.desi.lbl.gov/public/dr1/spectro/redux/iron/);
                 tile radius 1.7 deg: the focal plane is 3.2 deg across, and
                 the 162,821 DESI objects kept in benchmark/ lie at most
                 1.622 deg from the nearest centre (none beyond 1.7 deg).
                 The Galactic plane at l ~ 30, b ~ -2 is 11 deg from any tile.

A cone outside every DESI tile cost one VizieR request (DESI DR1 redshifts)
and, for the FastSpecFit lines, one Data Lab request, whose stalls took 246 s
in every one of the six outage collections of the 2026-11-15/17/23 probes.
An empty cone costs one VizieR request, ~5-9 s with the 3-5 s pause
(throttle.py), and more when the archive is degraded; a southern search
skips three radio surveys.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

MARGIN_DEG = 1.0
_HERE = Path(__file__).resolve().parent
# ICRS -> Galactic (Hipparcos/ICRS rotation: the north Galactic pole and the
# longitude of the north celestial pole, ESA 1997 Vol. 1 sec. 1.5.3)
_RA_NGP, _DEC_NGP, _L_NCP = math.radians(192.85948), math.radians(27.12825), 122.93192


def galactic(ra: float, dec: float) -> tuple[float, float]:
    """(l, b) in degrees of an ICRS position."""
    r, d = math.radians(ra), math.radians(dec)
    sb = math.sin(d) * math.sin(_DEC_NGP) + math.cos(d) * math.cos(_DEC_NGP) * math.cos(r - _RA_NGP)
    b = math.asin(max(-1.0, min(1.0, sb)))
    y = math.cos(d) * math.sin(r - _RA_NGP)
    x = math.sin(d) * math.cos(_DEC_NGP) - math.cos(d) * math.sin(_DEC_NGP) * math.cos(r - _RA_NGP)
    l = (_L_NCP - math.degrees(math.atan2(y, x))) % 360.0
    return l, math.degrees(b)


@lru_cache(maxsize=4)
def _tile_vectors(name: str):
    """Unit vectors of the tile centres in ``name`` (a csv with ra, dec; next to this file)."""
    import numpy as np
    import pandas as pd

    t = pd.read_csv(_HERE / name)
    a, d = np.radians(t["ra"].to_numpy(float)), np.radians(t["dec"].to_numpy(float))
    return np.c_[np.cos(d) * np.cos(a), np.cos(d) * np.sin(a), np.sin(d)]


def tile_gap_deg(name: str, ra: float, dec: float) -> float:
    """Angular distance in degrees from (ra, dec) to the nearest tile centre of the file ``name``."""
    import numpy as np

    a, d = math.radians(ra), math.radians(dec)
    v = np.array([math.cos(d) * math.cos(a), math.cos(d) * math.sin(a), math.sin(d)])
    return float(np.degrees(np.arccos(np.clip(_tile_vectors(name) @ v, -1.0, 1.0))).min())


def _in_range(l: float, lo: float, hi: float) -> bool:
    return lo <= l <= hi if lo <= hi else (l >= lo or l <= hi)


def outside(fp: dict | None, ra: float, dec: float, radius_arcmin: float, margin_deg: float = MARGIN_DEG) -> bool:
    """True only when the cone is clearly outside the footprint."""
    if not fp:
        return False
    reach = radius_arcmin / 60.0 + margin_deg
    if "dec_min" in fp and dec + reach < float(fp["dec_min"]):
        return True
    if "tiles" in fp:
        # outside when even the nearest tile, widened to its radius, is farther than the cone plus the margin
        if tile_gap_deg(fp["tiles"], ra, dec) - float(fp["tile_radius_deg"]) > reach:
            return True
    if "gal_l_range" in fp:
        lo, hi = (float(v) for v in fp["gal_l_range"])
        l, b = galactic(ra, dec)
        if not _in_range(l, lo, hi):
            # distance to the nearer boundary meridian (a great half-circle
            # through the Galactic poles): asin(|sin(l - l0)| cos b); exact for
            # a range whose ends are 180 deg apart (eRASS1-DE), where the two
            # meridians form one great circle
            dist = min(
                math.degrees(math.asin(min(1.0, abs(math.sin(math.radians(l - l0))) * math.cos(math.radians(b)))))
                for l0 in (lo, hi)
            )
            if dist > reach:
                return True
    return False
