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

An empty cone costs one VizieR request, ~5-9 s with the 3-5 s pause
(throttle.py), and more when the archive is degraded; a southern search
skips three radio surveys.
"""

from __future__ import annotations

import math

MARGIN_DEG = 1.0
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


def _in_range(l: float, lo: float, hi: float) -> bool:
    return lo <= l <= hi if lo <= hi else (l >= lo or l <= hi)


def outside(fp: dict | None, ra: float, dec: float, radius_arcmin: float, margin_deg: float = MARGIN_DEG) -> bool:
    """True only when the cone is clearly outside the footprint."""
    if not fp:
        return False
    reach = radius_arcmin / 60.0 + margin_deg
    if "dec_min" in fp and dec + reach < float(fp["dec_min"]):
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
