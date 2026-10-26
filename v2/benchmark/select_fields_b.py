#!/usr/bin/env python3
"""Second set of 200 independent validation regions (set B, 2026-10-26).

Every region is >= 3.5 deg from the 200 regions of v2_independent_truth.yml
(set A) and from every other region of set B, so no truth object or field
star is shared between the sets.  The mix follows set A: survey pools where
the independent truth surveys are dense (2dFGRS/2QZ SGP and NGP strips,
Stripe 82, the LAMOST footprint, 6dFGS/RAVE southern sky) plus special
regions (globular and open clusters, star-forming regions, starburst
galaxies, Magellanic Cloud outskirts and Bridge) chosen from objects not in
set A.  Survey positions are drawn from a Fibonacci grid in a fixed order,
so the list is reproducible:

    python v2/benchmark/select_fields_b.py > /tmp/matrix_b.yml
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MIN_SEP = 3.5

# name, ra, dec, radius ('), comment -- objects not in set A, >= 3.5 deg apart
SPECIAL = [
    ("gc_m10", 254.288, -4.100, 6, "globular M10"),
    ("gc_m22", 279.100, -23.905, 6, "globular M22"),
    ("gc_m55", 294.998, -30.962, 6, "globular M55"),
    ("gc_ngc1851", 78.528, -40.047, 6, "globular NGC 1851"),
    ("gc_ngc2808", 138.013, -64.864, 6, "globular NGC 2808"),
    ("gc_ngc6541", 272.010, -43.715, 6, "globular NGC 6541"),
    ("gc_m53", 198.230, 18.168, 6, "globular M53"),
    ("gc_m68", 189.867, -26.744, 6, "globular M68"),
    ("gc_m79", 81.046, -24.525, 6, "globular M79"),
    ("gc_ngc6362", 262.979, -67.048, 6, "globular NGC 6362"),
    ("gc_m71", 298.444, 18.779, 6, "globular M71"),
    ("gc_m56", 289.148, 30.184, 6, "globular M56"),
    ("oc_ic4665", 266.600, 5.700, 12, "open cluster IC 4665"),
    ("oc_ngc6633", 276.850, 6.570, 12, "open cluster NGC 6633"),
    ("oc_ic2602", 160.600, -64.400, 12, "open cluster IC 2602"),
    ("oc_ngc2547", 122.600, -49.200, 12, "open cluster NGC 2547"),
    ("oc_m48", 123.400, -5.750, 12, "open cluster M48"),
    ("oc_m50", 105.700, -8.300, 12, "open cluster M50"),
    ("oc_ngc2243", 97.400, -31.300, 12, "open cluster NGC 2243"),
    ("oc_cr261", 189.500, -68.400, 12, "open cluster Collinder 261"),
    ("oc_ngc7789", 359.300, 56.700, 12, "open cluster NGC 7789"),
    ("oc_m37", 88.100, 32.550, 12, "open cluster M37"),
    ("oc_ngc6819", 295.300, 40.200, 12, "open cluster NGC 6819"),
    ("oc_ngc2477", 118.000, -38.500, 12, "open cluster NGC 2477"),
    ("sfr_serpens", 277.450, 1.250, 12, "Serpens Main"),
    ("sfr_lupus1", 235.600, -34.600, 12, "Lupus 1"),
    ("sfr_chaii", 195.200, -77.300, 12, "Chamaeleon II"),
    ("sfr_cra", 285.400, -36.950, 12, "Corona Australis"),
    ("sfr_ngc2024", 85.420, -1.900, 6, "Orion B / NGC 2024"),
    ("sfr_ic5146", 328.400, 47.300, 12, "IC 5146"),
    ("sfr_ngc7000", 312.900, 44.300, 6, "North America Nebula"),
    ("sfr_ic1805", 38.200, 61.450, 6, "W4 / IC 1805"),
    ("sfr_rosette", 98.000, 4.950, 6, "Rosette / NGC 2244"),
    ("sfr_ngc6334", 260.200, -35.800, 6, "NGC 6334"),
    ("sfr_ngc3603", 168.800, -61.300, 6, "NGC 3603"),
    ("sfr_b59", 257.800, -27.400, 12, "Pipe Nebula B59"),
    ("sfr_w51", 290.900, 14.100, 6, "W51"),
    ("sb_ngc3628", 170.071, 13.589, 12, "starburst edge-on NGC 3628 (Leo triplet)"),
    ("sb_ngc3256", 156.964, -43.904, 12, "starburst merger NGC 3256"),
    ("sb_ngc4945", 196.364, -49.468, 12, "starburst galaxy NGC 4945"),
    ("sb_ngc2146", 94.657, 78.357, 12, "starburst galaxy NGC 2146"),
    ("sb_m51", 202.470, 47.195, 12, "interacting M51"),
    ("lmc_outer_nw", 70.000, -64.500, 6, "LMC outer disc NW"),
    ("lmc_outer_ne", 98.000, -65.500, 6, "LMC outer disc NE"),
    ("lmc_outer_se", 95.000, -73.500, 6, "LMC outer disc SE"),
    ("lmc_outer_sw", 66.500, -71.000, 6, "LMC outer disc SW"),
    ("lmc_outer_s", 80.500, -75.500, 6, "LMC outer disc S"),
    ("smc_outer_s", 1.000, -76.000, 6, "SMC outskirts S"),
    ("mag_bridge_w", 46.000, -71.500, 6, "Magellanic Bridge, north"),
    ("mag_bridge_e", 57.000, -75.500, 6, "Magellanic Bridge, south"),
]


def gal_b(ra, dec):
    a, d = np.radians(ra), np.radians(dec)
    return np.degrees(
        np.arcsin(-0.867666135683 * np.cos(d) * np.cos(a) - 0.198076389613 * np.cos(d) * np.sin(a) + 0.455983794521 * np.sin(d))
    )


def sep(ra1, dec1, ra2, dec2):
    a1, d1, a2, d2 = map(np.radians, (ra1, dec1, ra2, dec2))
    c = np.sin(d1) * np.sin(d2) + np.cos(d1) * np.cos(d2) * np.cos(a1 - a2)
    return np.degrees(np.arccos(np.clip(c, -1, 1)))


def set_a():
    t = (ROOT / ".github/workflows/v2_independent_truth.yml").read_text()
    return [(float(r), float(d)) for r, d in re.findall(r"\{name: \w+, ra: ([-\d.]+), dec: ([-\d.]+)", t)]


def in_ra(ra, lo, hi):
    return (lo <= ra <= hi) if lo <= hi else (ra >= lo or ra <= hi)


# pool, maximum, test(ra, dec, b): where the set-A truth surveys are dense.
# The strips are filled first (as far as the 3.5 deg spacing allows), then
# the southern 6dFGS/RAVE sky, and the LAMOST footprint takes the rest.
POOLS = [
    ("sgp", 40, lambda ra, dec, b: in_ra(ra, 325, 55) and -37.5 <= dec <= -22.5),  # 2dFGRS/2QZ SGP strip
    ("ngp", 15, lambda ra, dec, b: in_ra(ra, 147, 225) and -5.5 <= dec <= 3.0),  # 2dFGRS/2QZ NGP strip
    ("s82", 15, lambda ra, dec, b: in_ra(ra, 300, 60) and -1.3 <= dec <= 1.3),  # Stripe 82 (2SLAQ, WiggleZ)
    ("sth", 15, lambda ra, dec, b: dec <= -20 and abs(b) >= 25),  # 6dFGS / RAVE south
    ("lam", None, lambda ra, dec, b: -5 <= dec <= 60 and abs(b) >= 12),  # LAMOST DR5 footprint
]


def fibonacci(n=40000):
    i = np.arange(n) + 0.5
    dec = np.degrees(np.arcsin(1 - 2 * i / n))
    ra = np.degrees(np.pi * (1 + 5**0.5) * i) % 360
    return ra, dec


def main():
    taken = list(set_a())
    out = []
    for name, ra, dec, r, why in SPECIAL:
        d = min(sep(ra, dec, a, b) for a, b in taken)
        assert d >= MIN_SEP, (name, round(d, 2))
        taken.append((ra, dec))
        out.append((name, ra, dec, r, True, f"{why}, b~{gal_b(ra, dec):+.0f}"))
    ra, dec = fibonacci()
    b = gal_b(ra, dec)
    order = np.argsort((ra * 7919 + dec * 104729) % 1)  # fixed pseudo-random order over the sky
    for pool, quota, test in POOLS:
        quota = 200 - len(out) if quota is None else quota
        n = 0
        for k in order:
            if n == quota:
                break
            if not test(ra[k], dec[k], b[k]):
                continue
            ta = np.array(taken)
            if sep(ra[k], dec[k], ta[:, 0], ta[:, 1]).min() < MIN_SEP:
                continue
            taken.append((ra[k], dec[k]))
            nm = f"b{pool}_{ra[k]:03.0f}{'p' if dec[k] >= 0 else 'm'}{abs(dec[k]):02.0f}"
            out.append((nm, round(float(ra[k]), 2), round(float(dec[k]), 2), None, False, f"{pool} pool, b~{b[k]:+.0f}"))
            n += 1
        assert pool != "lam" or n == quota, (pool, n)
        print(f"# {pool}: {n}", file=sys.stderr)
    assert len(out) == 200 and len({o[0] for o in out}) == 200
    for nm, r_, d_, rad, fixed, why in out:
        extra = f", r: {rad}, fixed: true" if fixed else ""
        print(f"          - {{name: {nm}, ra: {r_}, dec: {d_}{extra}}}    # {why}")


if __name__ == "__main__":
    main()
