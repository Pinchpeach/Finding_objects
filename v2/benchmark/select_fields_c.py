#!/usr/bin/env python3
"""Locked test set C (2026-11-11, 2.51.0): 60 regions never used for development.

Why: every headline number since 2.40.2 comes from fields that were looked at
while the pipeline was tuned (sets A, B, the 520 reference objects, COSMOS);
the only clean number was the first set-B score (SCIENTIFIC_REVIEW_2026-11-11
sec. 3.3).  Set C is selected here, locked by the SHA-256 of its list, and
scored once per release under the protocol in benchmark/LOCKED_TEST_SET_C.md
(aggregate metrics only; no per-object outputs are kept).

Every region is >= 3.5 deg from sets A and B, the COSMOS deep fields and the
other set-C regions.  Fibonacci grid as set B (different fixed order), plus a
low-latitude pool (5 < |b| < 15 deg in the LAMOST footprint): the review found
no |b| < 20 deg objects in the benchmarks, so the plane was never measured.

    python v2/benchmark/select_fields_c.py --csv v2/benchmark/fields_c.csv --yml /tmp/matrix_c.yml
"""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MIN_SEP = 3.5
POOLS = [
    # The SGP / NGP / Stripe 82 pools of set B are already filled by sets A+B
    # at 3.5 deg spacing (0, 1 and 0 free regions), so set C draws from the
    # wider sky in the same surveys' reach.
    ("csth", 18, lambda ra, dec, b: dec <= -20 and abs(b) >= 25),          # DES / LS-south
    ("cpln", 12, lambda ra, dec, b: -5 <= dec <= 60 and 5 <= abs(b) < 15),  # low latitude, never measured
    ("clam", 30, lambda ra, dec, b: -5 <= dec <= 60 and abs(b) >= 15),     # LAMOST / PS1 / LS-north
]


def gal_b(ra, dec):
    a, d = np.radians(ra), np.radians(dec)
    return np.degrees(np.arcsin(-0.867666135683 * np.cos(d) * np.cos(a) - 0.198076389613 * np.cos(d) * np.sin(a) + 0.455983794521 * np.sin(d)))


def sep(ra1, dec1, ra2, dec2):
    a1, d1, a2, d2 = map(np.radians, (ra1, dec1, ra2, dec2))
    c = np.sin(d1) * np.sin(d2) + np.cos(d1) * np.cos(d2) * np.cos(a1 - a2)
    return np.degrees(np.arccos(np.clip(c, -1, 1)))


def used():
    pts = []
    for f in ("v2_independent_truth.yml", "v2_independent_truth_b.yml", "experiment-ab-fields.yml"):
        t = (ROOT / ".github/workflows" / f).read_text()
        pts += [(float(r), float(d)) for r, d in re.findall(r"\{name: [\w]+, ra: ([-\d.]+), dec: ([-\d.]+)", t)]
    return pts


def fibonacci(n=40000):
    i = np.arange(n) + 0.5
    dec = np.degrees(np.arcsin(1 - 2 * i / n))
    ra = np.degrees(np.pi * (1 + 5**0.5) * i) % 360
    return ra, dec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--yml", type=Path)
    a = ap.parse_args()
    taken = used()
    ra, dec = fibonacci()
    b = gal_b(ra, dec)
    # a different fixed order from set B, so set C is not the next B candidates
    order = np.argsort((ra * 15485863 + dec * 32452843) % 1)
    out = []
    for pool, quota, test in POOLS:
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
            out.append((f"{pool}_{ra[k]:03.0f}{'p' if dec[k] >= 0 else 'm'}{abs(dec[k]):02.0f}", round(float(ra[k]), 2), round(float(dec[k]), 2), round(float(b[k]), 1), pool))
            n += 1
        print(f"# {pool}: {n}/{quota}")
    lines = ["name,ra,dec,b,pool"] + [",".join(map(str, o)) for o in out]
    text = "\n".join(lines) + "\n"
    a.csv.write_text(text)
    print("fields", len(out), "sha256", hashlib.sha256(text.encode()).hexdigest())
    if a.yml:
        a.yml.write_text("\n".join(f"          - {{name: {o[0]}, ra: {o[1]}, dec: {o[2]}, r: 12, setc: true}}" for o in out) + "\n")


if __name__ == "__main__":
    main()
