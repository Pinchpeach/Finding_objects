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
