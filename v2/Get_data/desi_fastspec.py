"""DESI DR1 emission lines (FastSpecFit) cone-search collector (2.7.0).

Source: the DESI DR1 AGN/galaxy value-added catalogue on NOIRLab Astro Data Lab
(``desi_dr1.agngal``), whose line fluxes, inverse variances and rest-frame
equivalent widths are the FastSpecFit measurements (Moustakas et al. 2023,
ASCL 2308.005; DESI Collaboration 2025, DR1).  The full FastSpecFit VAC is not
cone-searchable; this table carries the lines the BPT / WHAN rules need.

Output columns follow Get_data/sdss_spectroscopy.py (``line_*``: flux,
1-sigma error, EW positive in emission), so Classifier/subclass.py applies the
same diagnostics.  A line with zero inverse variance (outside the DESI
wavelength range, e.g. H-alpha at z > 0.49, or not fitted) is left empty:
FastSpecFit reports 0 there, which must not read as "no emission".
No classification is done here.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

if str(Path(__file__).resolve().parent) not in sys.path:  # loaded by file path elsewhere
    sys.path.insert(0, str(Path(__file__).resolve().parent))
# Same Data Lab TAP service and bounded-attempt pattern as desi_legacy.py (Data
# Lab can stall).  Its HTTP session has a timeout, so an abandoned attempt
# thread ends instead of piling up (pyvo's default session has none; 2.23.0).
from desi_legacy import TAP_URL, _query_with_retries, _service  # noqa: F401 (TAP_URL: benchmark)
from _catalog_utils import empty_frame, save_csv

save = save_csv  # collector API: save(df, path)

CATALOG = "DESI DR1 FastSpecFit"
TABLE = "desi_dr1.agngal"
LINES = {"ha": "halpha", "hb": "hbeta", "oiii5007": "oiii_5007", "nii6584": "nii_6584"}
EXTRA = ["halpha_broad_flux", "halpha_broad_flux_ivar", "halpha_broad_sigma", "opt_uv_type", "agn_maskbits"]
LINE_FIELDS = [f"line_{k}_{s}" for k in LINES for s in ("flux", "flux_err")] + [
    "line_ha_ew",
    "line_nii6584_ew",
    "line_source",
]


def standardise(df: pd.DataFrame) -> pd.DataFrame:
    """FastSpecFit columns -> line_* columns (shared with the SDSS collector)."""
    out = df.copy()
    for k, src in LINES.items():
        f = pd.to_numeric(out.get(f"{src}_flux"), errors="coerce")
        iv = pd.to_numeric(out.get(f"{src}_flux_ivar"), errors="coerce")
        ok = iv > 0
        out[f"line_{k}_flux"] = f.where(ok)
        out[f"line_{k}_flux_err"] = 1.0 / np.sqrt(iv.where(ok))
    ew = pd.to_numeric(out.get("halpha_ew"), errors="coerce")
    ewiv = pd.to_numeric(out.get("halpha_ew_ivar"), errors="coerce")
    out["line_ha_ew"] = ew.where(ewiv > 0)
    out["line_nii6584_ew"] = np.nan  # not in this table: the WHAN "passive" test needs it
    out["line_source"] = "FastSpecFit"
    return out


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    cols = [
        "targetid",
        "target_ra",
        "target_dec",
        "z",
        "zwarn",
        "spectype",
        "zcat_primary",
        *[f"{s}_{x}" for s in LINES.values() for x in ("flux", "flux_ivar")],
        "halpha_ew",
        "halpha_ew_ivar",
        *EXTRA,
    ]
    query = (
        f"SELECT {', '.join(cols)} FROM {TABLE} WHERE 't' = q3c_radial_query(target_ra, target_dec, "
        f"{float(ra):.10f}, {float(dec):.10f}, {float(radius_arcmin) / 60.0:.10f})"
    )
    df = _query_with_retries(lambda: _service().search(query).to_table().to_pandas())
    if df.empty:
        return empty_frame(*LINE_FIELDS)
    df.columns = [str(c).strip() for c in df.columns]
    prim = df["zcat_primary"].astype(str).str.strip().str.lower().isin(["true", "t", "1"])
    df = df[prim] if prim.any() else df  # one spectrum per object
    df = standardise(df)
    df.insert(0, "catalog", CATALOG)
    df.insert(1, "catalog_object_id", df["targetid"].astype("int64").astype(str))
    df.insert(2, "object_name", "DESI " + df["catalog_object_id"])
    df.insert(3, "ra", pd.to_numeric(df["target_ra"], errors="coerce"))
    df.insert(4, "dec", pd.to_numeric(df["target_dec"], errors="coerce"))
    return df.drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)
