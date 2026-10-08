#!/usr/bin/env python3
"""Survey-aware, epoch-aware positional association helpers.

The functions in this module deliberately distinguish three concepts:
(1) catalog positional uncertainty, (2) instrumental PSF/resolution, and
(3) the final association score.  The score is a conservative diagnostic,
not a calibrated posterior probability.

Gaia proper motions use mu_alpha* = d(alpha)/dt cos(delta).  Linear propagation
is adequate for the decade-scale catalog matching performed here; the pipeline
records when this approximation is used so a future full covariance propagation
can replace it without changing the Stage-1 interface.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Any


@dataclass(frozen=True)
class SurveyProfile:
    ref_epoch: float | None
    fallback_poserr_arcsec: float
    psf_fwhm_arcsec: float | None
    max_radius_arcsec: float
    entity_kind: str = "persistent_source"


# Fallback values are used only when a catalog row does not provide a per-source
# positional error.  They are intentionally conservative and are kept separate
# from the PSF.  Per-source errors always take precedence.
PROFILES = {
    "Gaia DR3": SurveyProfile(2016.0, 0.10, 0.18, 5.0),
    "AllWISE": SurveyProfile(2010.5, 0.50, 6.1, 8.0),
    "2MASS PSC": SurveyProfile(2000.0, 0.25, 2.5, 6.0),
    "Pan-STARRS1 DR2 MeanObject": SurveyProfile(None, 0.12, 0.83, 4.0),
    "GALEX AIS": SurveyProfile(None, 0.80, 5.3, 8.0),
    "FIRST": SurveyProfile(None, 1.0, 5.0, 8.0),
    "NVSS": SurveyProfile(None, 3.0, 45.0, 30.0),
    "Chandra CSC 2.0": SurveyProfile(None, 0.60, 0.5, 5.0),
    "XMM 4XMM-DR13": SurveyProfile(None, 1.5, 6.0, 10.0),
    "eROSITA eRASS1": SurveyProfile(2020.5, 4.0, 26.0, 20.0),
    "ATNF Pulsar Catalog": SurveyProfile(None, 0.5, None, 5.0),
    "HASH PN Catalog": SurveyProfile(None, 1.0, None, 8.0),
    "ASAS-SN Supernova Catalog": SurveyProfile(2000.0, 1.0, None, 5.0, "transient_event"),
    "Asiago Supernova Catalog": SurveyProfile(2000.0, 1.0, None, 5.0, "transient_event"),
    "Acker PN Spectroscopy": SurveyProfile(2000.0, 2.0, None, 8.0),
    # SGA-2020 centres come from Legacy Surveys ellipse fits of large galaxies.
    "SGA-2020": SurveyProfile(None, 1.0, None, 5.0),
}
DEFAULT_PROFILE = SurveyProfile(None, 0.6, None, 5.0)


def num(value: Any) -> float | None:
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _first(row: Mapping[str, Any], keys: tuple[str, ...]) -> float | None:
    """First finite value among ``keys`` (case-insensitive), in ``keys`` order."""
    low = None
    for key in keys:
        if key in row:
            actual = key
        else:
            # Built lazily: Stage-1 detection records use canonical keys, and
            # rebuilding this map per call dominated association runtime.
            if low is None:
                low = {str(k).lower(): k for k in row.keys()}
            actual = low.get(key.lower())
            if actual is None:
                continue
        value = num(row.get(actual))
        if value is not None:
            return value
    return None



def canonical_aliases(catalog: str, row: Mapping[str, Any], catalog_object_id: str | None = None) -> set[str]:
    """Return namespaced cross-catalog identifiers safe for direct association.

    Only identifiers with an explicit survey namespace are compared.  Generic
    source names are intentionally excluded to avoid accidental merges.
    """
    aliases=set()
    low={str(k).lower():k for k in row.keys()}
    def add(ns, value):
        if value is None:return
        v=str(value).strip().upper().replace(" ","")
        if not v or v in {"NAN","NONE","--"}:return
        aliases.add(f"{ns}:{v}")
    if catalog=="AllWISE":add("WISE",catalog_object_id)
    if catalog=="2MASS PSC":add("2MASS",catalog_object_id)
    for key in ("wisea","allwise","wise","wise_id"):
        if key in low:add("WISE",row.get(low[key]))
    for key in ("_2mass","2mass","2mass_name","tmass"):
        if key in low:add("2MASS",row.get(low[key]))
    return aliases

def profile_for(catalog: str, row: Mapping[str, Any] | None = None) -> SurveyProfile:
    row = row or {}
    if catalog == "Suh 2021 AGB Catalog":
        subtype = str(row.get("agb_subclass", "")).upper()
        if "IRAS" in subtype:
            # IRAS-based positions can be displaced by many arcsec.  This is a
            # positional-uncertainty allowance, not permission to merge hosts.
            return SurveyProfile(1983.5, 12.0, 30.0, 45.0)
        if "WISE" in subtype:
            return SurveyProfile(2010.5, 1.0, 6.1, 10.0)
        return SurveyProfile(None, 5.0, 12.0, 20.0)
    return PROFILES.get(catalog, DEFAULT_PROFILE)


def infer_epoch(catalog: str, row: Mapping[str, Any]) -> float | None:
    explicit = _first(row, ("ref_epoch", "epoch_jyear", "observation_epoch", "obs_epoch"))
    if explicit is not None and 1800.0 < explicit < 2200.0:
        return explicit
    mjd = _first(row, ("obs_mjd", "mjd_obs", "observation_mjd"))
    if mjd is not None and 10000 < mjd < 100000:
        return 2000.0 + (mjd - 51544.5) / 365.25
    return profile_for(catalog, row).ref_epoch


def infer_poserr_arcsec(catalog: str, row: Mapping[str, Any]) -> float:
    explicit = _first(row, ("poserr_arcsec", "pos_err", "radec_err", "err_maj", "errmaj"))
    if explicit is not None and explicit > 0:
        return explicit

    # Catalog-native RA/Dec error pairs in arcsec.
    for keys in (("sigra", "sigdec"), ("e_raj2000", "e_dej2000"), ("rasig", "desig")):
        a, b = _first(row, (keys[0],)), _first(row, (keys[1],))
        if a is not None and b is not None and max(a, b) > 0:
            return max(a, b)

    # Gaia DR3 coordinate errors are mas.
    if catalog == "Gaia DR3":
        a, b = _first(row, ("ra_error",)), _first(row, ("dec_error",))
        if a is not None and b is not None and max(a, b) > 0:
            return max(a, b) / 1000.0

    # Pan-STARRS mean-coordinate errors are supplied in mas by the MAST table.
    if catalog == "Pan-STARRS1 DR2 MeanObject":
        a, b = _first(row, ("rameanerr",)), _first(row, ("decmeanerr",))
        if a is not None and b is not None and max(a, b) > 0:
            return max(a, b) / 1000.0

    return profile_for(catalog, row).fallback_poserr_arcsec


def infer_psf_arcsec(catalog: str, row: Mapping[str, Any]) -> float | None:
    explicit = _first(row, ("psf_fwhm_arcsec", "fwhm_arcsec", "psffwhm"))
    return explicit if explicit is not None and explicit > 0 else profile_for(catalog, row).psf_fwhm_arcsec


def infer_entity_kind(catalog: str, row: Mapping[str, Any]) -> str:
    value = str(row.get("entity_kind", "")).strip()
    return value or profile_for(catalog, row).entity_kind


def _pm(row: Mapping[str, Any]) -> tuple[float | None, float | None, float | None, float | None]:
    return (
        _first(row, ("pmra",)),
        _first(row, ("pmdec",)),
        _first(row, ("pmra_error",)),
        _first(row, ("pmdec_error",)),
    )


def propagate_linear(ra_deg: float, dec_deg: float, pmra_masyr: float, pmdec_masyr: float,
                     from_epoch: float, to_epoch: float) -> tuple[float, float]:
    """Propagate ICRS coordinates with the tangent-plane proper-motion model."""
    dt = to_epoch - from_epoch
    cosd = max(abs(math.cos(math.radians(dec_deg))), 1e-8)
    dra_deg = (pmra_masyr * dt) / (3.6e6 * cosd)
    ddec_deg = (pmdec_masyr * dt) / 3.6e6
    return (ra_deg + dra_deg) % 360.0, dec_deg + ddec_deg


def sep_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    dra = math.radians(((ra2 - ra1 + 180.0) % 360.0) - 180.0)
    d1, d2 = math.radians(dec1), math.radians(dec2)
    a = math.sin((d2 - d1) / 2.0) ** 2 + math.cos(d1) * math.cos(d2) * math.sin(dra / 2.0) ** 2
    return math.degrees(2.0 * math.asin(min(1.0, math.sqrt(max(0.0, a))))) * 3600.0


def effective_sigma_arcsec(det: Mapping[str, Any], target_epoch: float | None = None) -> float:
    pos = max(float(det["poserr_arcsec"]), 0.02)
    psf = num(det.get("psf_fwhm_arcsec"))
    # PSF/6 is a conservative centroiding floor; it is not interpreted as a
    # formal astrometric uncertainty.
    if psf is not None:
        pos = max(pos, psf / 6.0)
    epoch = num(det.get("ref_epoch"))
    if target_epoch is not None and epoch is not None:
        _, _, epmra, epmdec = _pm(det)
        if epmra is not None or epmdec is not None:
            pm_sigma = max(epmra or 0.0, epmdec or 0.0) * abs(target_epoch - epoch) / 1000.0
            pos = math.hypot(pos, pm_sigma)
    return pos


def comparison_positions(a: Mapping[str, Any], b: Mapping[str, Any]):
    """Return positions at a common epoch, preferring propagation of a PM source."""
    ara, ade, bra, bde = map(float, (a["ra"], a["dec"], b["ra"], b["dec"]))
    aepoch, bepoch = num(a.get("ref_epoch")), num(b.get("ref_epoch"))
    apmra, apmdec, _, _ = _pm(a)
    bpmra, bpmdec, _, _ = _pm(b)
    if aepoch is not None and bepoch is not None and apmra is not None and apmdec is not None:
        ara, ade = propagate_linear(ara, ade, apmra, apmdec, aepoch, bepoch)
        return ara, ade, bra, bde, bepoch, True, "a_to_b"
    if aepoch is not None and bepoch is not None and bpmra is not None and bpmdec is not None:
        bra, bde = propagate_linear(bra, bde, bpmra, bpmdec, bepoch, aepoch)
        return ara, ade, bra, bde, aepoch, True, "b_to_a"
    return ara, ade, bra, bde, None, False, "none"


def chance_probability(separation_arcsec: float, density_arcsec2: float | None) -> float | None:
    if density_arcsec2 is None or density_arcsec2 < 0:
        return None
    return 1.0 - math.exp(-math.pi * separation_arcsec * separation_arcsec * density_arcsec2)


def assess_pair(a: Mapping[str, Any], b: Mapping[str, Any], density_arcsec2: float | None = None) -> dict[str, Any]:
    ara, ade, bra, bde, epoch, propagated, direction = comparison_positions(a, b)
    sep = sep_arcsec(ara, ade, bra, bde)
    sa = effective_sigma_arcsec(a, epoch)
    sb = effective_sigma_arcsec(b, epoch)
    sigma = max(math.hypot(sa, sb), 0.05)
    psf = max(num(a.get("psf_fwhm_arcsec")) or 0.0, num(b.get("psf_fwhm_arcsec")) or 0.0)
    cap = max(float(a.get("max_radius_arcsec", 5.0)), float(b.get("max_radius_arcsec", 5.0)))
    radius = min(cap, max(0.15, 5.0 * sigma, 0.6 * psf))
    norm = sep / sigma
    positional = math.exp(-0.5 * norm * norm)
    pchance = chance_probability(sep, density_arcsec2)
    score = positional * (1.0 - pchance) if pchance is not None else positional
    accepted = sep <= radius and (pchance is None or pchance <= 0.25) and score >= 1e-5
    # Membership posterior (Budavari & Szalay 2008, ApJ 679, 301): the
    # positional likelihood density of a true counterpart against the
    # background density of unrelated sources.  ``score`` keeps ranking
    # candidates; the posterior is what downstream evidence is weighted by
    # (a unique 3-sigma match is not 1% reliable in a sparse field).
    density_l = positional / (2.0 * math.pi * sigma * sigma)
    posterior = density_l / (density_l + density_arcsec2) if density_arcsec2 is not None and density_arcsec2 > 0 else positional
    return {
        "association_posterior": posterior,
        "accepted": accepted,
        "separation_arcsec": sep,
        "comparison_epoch": epoch,
        "proper_motion_propagated": propagated,
        "propagation_direction": direction,
        "combined_sigma_arcsec": sigma,
        "match_radius_arcsec": radius,
        "normalized_separation": norm,
        "positional_likelihood": positional,
        "chance_probability": pchance,
        "association_score": score,
    }
