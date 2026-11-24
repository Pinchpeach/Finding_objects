"""MYStIX Probable Complex Members (Broos et al. 2013, ApJS 209, 32; VizieR J/ApJS/209/32/mpcm).

Young stars of 20 massive star-forming regions (ONC, Flame/NGC 2024, Lagoon/M8,
NGC 2264, Rosette, Carina, Eagle, M17, NGC 6334, NGC 3603, ...): the union of
X-ray sources classified as members by a naive-Bayes classifier (X-ray
median energy, variability, J magnitude, [4.5], IR excess, local density)
and infrared-excess sources (Povich et al. 2013), plus published OB stars.

Only X-ray- or IR-excess-selected members are kept (``Xind`` or ``Iind``
set): the OB stars come from published spectral types, i.e. from
spectroscopy, which the blind validation must not see (2.42.0).  Positions
(``rPos`` = X-ray, NIR or MIR origin) carry a 1-sigma error ``ePos``.
"""

import pandas as pd
from _catalog_utils import empty_frame, numeric, pick, save_csv, vizier_cone, with_base

save = save_csv  # collector API: save(df, path)

CATALOG = "MYStIX MPCM"
VIZIER_CATALOG = "J/ApJS/209/32/mpcm"
# 2.60.2: the 20 regions of the published ``reg`` table (centres) and the radius that holds all their members
# (``mpcm``, 31,549 rows: the farthest member 0.18-1.20 deg from the centre, plus 0.3 deg, rounded up to 0.1 deg);
# nothing is asked for a cone that is not within the radius of a region (footprint.py).
FOOTPRINT = {
    "regions": [
        (161.0792, -59.8892, 0.9),  # Carina Nebula
        (309.7567, 42.3272, 0.6),  # DR 21
        (274.7, -13.8067, 0.8),  # Eagle Nebula
        (85.4279, -1.9122, 0.5),  # Flame Nebula
        (270.9042, -24.3867, 0.7),  # Lagoon Nebula
        (275.1958, -16.1717, 0.8),  # M 17
        (80.6833, 33.4117, 0.6),  # NGC 1893
        (100.2417, 9.895, 0.9),  # NGC 2264
        (109.6708, -24.955, 0.5),  # NGC 2362
        (167.9575, -61.3039, 0.8),  # NGC 3576
        (260.212, -36.115, 0.8),  # NGC 6334
        (261.625, -34.2, 0.9),  # NGC 6357
        (83.8221, -5.3911, 0.5),  # Orion Nebula
        (134.7537, -43.7361, 0.6),  # RCW 36
        (134.7729, -47.5109, 0.6),  # RCW 38
        (97.9167, 4.9633, 1.5),  # Rosette Nebula
        (270.675, -22.9717, 0.6),  # Trifid Nebula
        (36.7671, 61.8742, 0.9),  # W 3
        (38.175, 61.45, 0.6),  # W 4
        (277.8604, -2.0728, 0.6),  # W 40
    ]
}
KEEP = ["Reg", "MPCM", "ePos", "rPos", "Xind", "Iind", "Olab", "xc"]


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    df = vizier_cone(VIZIER_CATALOG, ra, dec, radius_arcmin)
    if df is None or df.empty:
        return empty_frame(*KEEP)
    idc, rac, dcc = pick(df, ["MPCM"]), pick(df, ["RAJ2000", "_RAJ2000"]), pick(df, ["DEJ2000", "_DEJ2000"])
    if not all([idc, rac, dcc]):
        raise KeyError(f"MYStIX MPCM required columns missing; got {list(df.columns)}")
    selected = pd.Series(False, index=df.index)
    for c in ("Xind", "Iind"):
        if c in df:
            selected |= numeric(df[c]).notna()
    df = df[selected].reset_index(drop=True)
    if df.empty:
        return empty_frame(*KEEP)
    ident = df[idc].astype("string").str.strip()
    return with_base(df, CATALOG, ident, CATALOG + " " + ident, numeric(df[rac]), numeric(df[dcc]))
