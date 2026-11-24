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

  boxes          RA / Dec boxes ``(ra_lo, ra_hi, dec_lo, dec_hi)`` in degrees that together contain the survey
                 (``ra_lo > ra_hi`` wraps through RA = 0), read from the survey's own coverage products
                 (2.60.2).  FIRST (VIII/92/first14, Helfand et al. 2015, ApJ 801, 26): the official coverage maps
                 of the 2014 December 17 release, https://sundog.stsci.edu/first/catalogs/
                 coverage-north-3arcmin-14dec17.fits (sha256 61b50811...fa) and ...-south-... (559a574c...e9):
                 the pixels with rms > 0 span RA 98.9-266.5, Dec -8.15..+64.75 (north cap, 8,444 deg^2 in the
                 paper) and RA 305.2 -> 59.7 (through 0), Dec -11.45..+15.40 (south cap, 2,131 deg^2).  The box
                 holds the whole map, so it is larger than the footprint (the south cap is ragged).
  regions        discs ``(ra, dec, radius_deg)`` (2.60.2).  MYStIX (J/ApJS/209/32, Broos et al. 2013): the 20
                 star-forming regions of the published ``reg`` table (centres) with the radius that holds every
                 member of the ``mpcm`` table (31,549 rows) of that region plus 0.3 deg, rounded up to 0.1 deg.

LoTSS DR2 (J/A+A/659/A1, Shimwell et al. 2022) is a ``dec_min``: the project's coverage MOC
(https://lofar-surveys.org/public/DR2/catalogues/dr2-moc.moc, sha256 450399d3...90, 13,209 cells, 5,721 deg^2 against
the paper's 5,634) has no covered cell centre south of Dec +16.26 (two regions: RA 90-300 Dec +22.8..+69.7 and RA
300-60 Dec +16.3..+43.2); the limit is 16.0.  The CDS MOCs of these catalogues (MocServer) were not served on
2026-11-24 (HTTP 413) and are built from source positions, which understate a survey's coverage.

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


def _sep_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    a, b, d1, d2 = (math.radians(v) for v in (ra1, ra2, dec1, dec2))
    h = math.sin((d2 - d1) / 2) ** 2 + math.cos(d1) * math.cos(d2) * math.sin((b - a) / 2) ** 2
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(h))))


def _box_overlaps(box, ra: float, dec: float, reach: float) -> bool:
    """True unless the cone (centre, ``reach`` degrees) is clear of the RA / Dec box."""
    ra_lo, ra_hi, dec_lo, dec_hi = (float(v) for v in box)
    if dec + reach < dec_lo or dec - reach > dec_hi:
        return False
    top = abs(dec) + reach
    if top >= 89.5:  # the cone reaches a pole: every RA
        return True
    half = math.degrees(math.asin(min(1.0, math.sin(math.radians(reach)) / math.cos(math.radians(top)))))
    inside = _in_range(ra % 360.0, ra_lo, ra_hi)
    if inside:
        return True
    gap = min(abs((ra - e + 180.0) % 360.0 - 180.0) for e in (ra_lo, ra_hi))
    return gap <= half


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
    if "boxes" in fp:
        if not any(_box_overlaps(b, ra, dec, reach) for b in fp["boxes"]):
            return True
    if "regions" in fp:
        if all(_sep_deg(ra, dec, r_ra, r_dec) - r_rad > reach for r_ra, r_dec, r_rad in fp["regions"]):
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
