"""The position an object is shown at, separated from the order of the association (task "버", 2.62.10+; literature: LITERATURE_OBJECT_POSITION_2026-11-28.md).

Stage 1 gives every group the position of its ANCHOR, the member the association order put first.  That is not the most precise position of the group: the anchor is chosen
by the unfloored position error, while the association itself (and the match radius) uses the effective error ``max(poserr, 0.02'', PSF / 6)``, under which AllWISE (PSF / 6 =
1.02'') is far less precise than an optical row.  The objects anchored by AllWISE lie beyond 0.5'' of their COSMOS2020 source in 71 % of the cases
(WORK_REPORT_2026-11-28d.md, 5.6).

``V2_OBJECT_POSITION`` (default ``anchor`` = nothing changes; ``best``) replaces only the printed ``ra`` / ``dec`` of the FINAL tables by the position of the member with the
smallest ranked error (the rule SIMBAD uses for its basic data: the most accurate measurement; Wenger et al. 2000, A&AS 143, 9, 3.2.2).  It is applied once, at the very end of
``pipeline.py``: stages 1-7, the host and cluster groups, the designations (names come from catalogue identifiers, not from coordinates), ``separation_arcmin`` and the cone cut all
run on the anchor position, so the labels, the probabilities and the object set are those of the default run by construction.  With ``best`` the table gets six more columns:

    ra_anchor, dec_anchor       the position the pipeline worked with (the anchor's)
    position_source             the catalogue of the member whose position is printed
    position_sigma_arcsec       its error as ranked (the effective error without the proper-motion term, with the catalogue floors of POSITION_FLOOR)
    position_epoch              its reference epoch (Gaia DR3 2016.0; None where the catalogue gives none).  Positions of different epochs are not mixed: one member's position
                                at that member's epoch, and no proper-motion propagation to a common epoch (the anchor has the same limit)
    position_shift_arcsec       the distance between the two positions

Ties of the effective error are broken by the measured error under the floor (``poserr_arcsec``, unfloored: the floor PSF / 6 is a guess and often the same for several optical
catalogues), then by ``TIE_PRIORITY`` (astrometric quality of the catalogue, Gaia first), the catalogue name and the detection id, so the result does not depend on the order of the rows.
(The first version broke ties by the priority alone: 3.24 % of the clean objects beyond 0.5'' of their COSMOS2020 source against 3.16 % with the measured error first, WORK_REPORT_2026-11-28g.md.)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ENV = "V2_OBJECT_POSITION"
MODES = ("anchor", "best")
NEW_COLUMNS = ["ra_anchor", "dec_anchor", "position_source", "position_sigma_arcsec", "position_epoch", "position_shift_arcsec"]

# Catalogues in the order of their astrometric quality for a tie of the effective error (Gaia DR3 first: ICRS, epoch 2016.0).  The literature compilations come last: their
# coordinates are other people's measurements.
TIE_PRIORITY = (
    "Gaia DR3",
    "DESI Legacy Surveys DR10",
    "Pan-STARRS1 DR2 MeanObject",
    "SDSS DR18 PhotoObj",
    "2MASS PSC",
    "AllWISE",
    "GALEX AIS",
    "SIMBAD",
    "NED",
)


# A catalogue-level floor of the error used ONLY to choose the printed position (the association keeps its own errors).  Pan-STARRS1 DR2 ``raMeanErr`` is the scatter of the single-epoch RAs
# of the mean position, not an error of the position (benchmark/position_errors/UNITS.md); read as one it gives 0.03'' (median), and the objects Pan-STARRS1 anchors lie beyond 0.5'' of
# their COSMOS2020 source in 17.1 % of the cases against 1.9 % for the Legacy Surveys row of the same object (26 deep COSMOS fields; by magnitude i > 22: 29 %, i > 24: 85 %).  The floor is the
# 0.6'' of the association's default for a catalogue of unknown accuracy (``DEFAULT_PROFILE``), the one value tried: it puts the Legacy Surveys row (also 0.6'') ahead by the tie rule.
POSITION_FLOOR = {"Pan-STARRS1 DR2 MeanObject": 0.6}


def mode() -> str:
    """The switch: '' / ``anchor`` (default) or ``best``; anything else is an error (like the other V2_* switches)."""
    raw = os.environ.get(ENV, "").strip().lower()
    if raw in ("", "anchor"):
        return "anchor"
    if raw == "best":
        return "best"
    raise ValueError(f"{ENV}={raw!r}: expected one of {', '.join(MODES)}")


def _posserr_native() -> frozenset:
    pre = str(Path(__file__).resolve().parent / "Preprocess")
    if pre not in sys.path:
        sys.path.insert(0, pre)
    import association_model as AM  # noqa: E402

    return frozenset(getattr(AM, "POSERR_NATIVE", ()))


def effective_sigma(a: pd.DataFrame) -> np.ndarray:
    """``association_model.effective_sigma_arcsec`` without the proper-motion term, for every row (a test compares the two)."""
    pos = np.maximum(pd.to_numeric(a["poserr_arcsec"], errors="coerce").fillna(99.0).to_numpy(float), 0.02)
    psf = pd.to_numeric(a["psf_fwhm_arcsec"], errors="coerce").to_numpy(float) if "psf_fwhm_arcsec" in a else np.full(len(a), np.nan)
    use_psf = np.isfinite(psf)
    if "allwise_raw" in _posserr_native():
        use_psf &= (a["catalog"] != "AllWISE").to_numpy()
    return np.where(use_psf, np.maximum(pos, psf / 6.0), pos)


def position_sigma(a: pd.DataFrame) -> np.ndarray:
    """The error that ranks the members for the printed position: ``effective_sigma`` with the catalogue floors of ``POSITION_FLOOR``."""
    sigma = effective_sigma(a)
    for cat, floor in POSITION_FLOOR.items():
        sigma = np.where((a["catalog"] == cat).to_numpy(), np.maximum(sigma, floor), sigma)
    return sigma


def best_positions(assoc: pd.DataFrame) -> pd.DataFrame:
    """One row per ``object_id``: ra, dec, source, sigma, epoch of the member with the smallest effective error (``assoc`` = the table of Stage 1)."""
    a = assoc[["object_id", "catalog", "ra", "dec"]].copy()
    a["detection_id"] = assoc["detection_id"].astype(str) if "detection_id" in assoc else ""
    a["epoch"] = pd.to_numeric(assoc["ref_epoch"], errors="coerce") if "ref_epoch" in assoc else np.nan
    a["ra"], a["dec"] = pd.to_numeric(a["ra"], errors="coerce"), pd.to_numeric(a["dec"], errors="coerce")
    a["sigma"] = position_sigma(assoc)
    # a tie of the effective error is mostly a tie of the FLOOR (PSF / 6: Legacy Surveys, Pan-STARRS1 and SDSS all give 0.2'' for a 1.2'' PSF): the measured error under the floor decides
    a["measured"] = pd.to_numeric(assoc["poserr_arcsec"], errors="coerce").fillna(99.0)
    for cat, floor in POSITION_FLOOR.items():  # the catalogue floor holds for the tie key too (a scatter statistic must not win the tie either)
        a["measured"] = np.where((a["catalog"] == cat).to_numpy(), np.maximum(a["measured"], floor), a["measured"])
    rank = {c: i for i, c in enumerate(TIE_PRIORITY)}
    a["rank"] = a["catalog"].map(rank).fillna(len(TIE_PRIORITY)).astype(int)
    a = a[np.isfinite(a["ra"]) & np.isfinite(a["dec"])]
    a = a.sort_values(["object_id", "sigma", "measured", "rank", "catalog", "detection_id"], kind="mergesort").drop_duplicates("object_id")
    return a.set_index("object_id")[["ra", "dec", "catalog", "sigma", "epoch"]].rename(columns={"catalog": "source"})


def apply(out: pd.DataFrame, assoc: pd.DataFrame) -> pd.DataFrame:
    """``out`` unchanged in the default mode; with ``best`` its ``ra`` / ``dec`` become the best member's and six columns are added (see the module text)."""
    if mode() == "anchor":
        return out
    out = out.copy()
    out["ra_anchor"], out["dec_anchor"] = out["ra"], out["dec"]
    best = best_positions(assoc) if len(assoc) else pd.DataFrame(columns=["ra", "dec", "source", "sigma", "epoch"])
    key = out["object_id"] if "object_id" in out else pd.Series(index=out.index, dtype=object)
    b = best.reindex(key.to_numpy())
    have = b["ra"].notna().to_numpy()
    ra = np.where(have, b["ra"].to_numpy(float), pd.to_numeric(out["ra"], errors="coerce").to_numpy(float))
    dec = np.where(have, b["dec"].to_numpy(float), pd.to_numeric(out["dec"], errors="coerce").to_numpy(float))
    dra = (ra - pd.to_numeric(out["ra_anchor"], errors="coerce").to_numpy(float)) * np.cos(np.radians(dec))
    ddec = dec - pd.to_numeric(out["dec_anchor"], errors="coerce").to_numpy(float)
    out["ra"], out["dec"] = ra, dec
    out["position_source"] = np.where(have, b["source"].to_numpy(object), None)
    out["position_sigma_arcsec"] = np.where(have, b["sigma"].to_numpy(float), np.nan)
    out["position_epoch"] = np.where(have, b["epoch"].to_numpy(float), np.nan)
    out["position_shift_arcsec"] = np.where(have, np.hypot(dra, ddec) * 3600.0, np.nan)
    return out
