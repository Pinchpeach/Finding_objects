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
    # PS1 3pi delivered median PSF FWHM: g 1.47, r 1.31, i 1.19, z 1.14,
    # y 1.09" (Chambers et al. 2016, Table 11); 0.83" was the site DIMM
    # seeing, not the delivered image quality (corrected 2.16.0).  The row's
    # epochMean (MJD) is the epoch of the mean position when fetched.
    "Pan-STARRS1 DR2 MeanObject": SurveyProfile(None, 0.12, 1.2, 4.0),
    # GALEX: 0.49/0.59" absolute astrometry (NUV/FUV, S/N >= 10) and 5.3"
    # NUV FWHM (Morrissey et al. 2007).
    "GALEX AIS": SurveyProfile(None, 0.80, 5.3, 8.0),
    # FIRST: 5.4" beam (Becker, White & Helfand 1995).
    "FIRST": SurveyProfile(None, 1.0, 5.4, 8.0),
    # NVSS: 45" beam (Condon et al. 1998).
    "NVSS": SurveyProfile(None, 3.0, 45.0, 30.0),
    # TGSS ADR1: 25" beam, astrometry better than 2" (Intema et al. 2017).
    "TGSS ADR1": SurveyProfile(None, 2.0, 25.0, 25.0),
    # ZTF: ~0.1" astrometry, ~2" seeing (Bellm et al. 2019; Masci et al. 2019).
    "ZTF periodic variables": SurveyProfile(None, 0.15, 2.0, 3.0),
    "ZTF light curves": SurveyProfile(None, 0.15, 2.0, 3.0),
    # Chandra CSC: on-axis PSF ~0.5"; per-source r0 is a 95 % error-ellipse
    # radius (Evans et al. 2010; CSC column documentation), see
    # infer_poserr_arcsec.
    "Chandra CSC 2.0": SurveyProfile(None, 0.60, 0.5, 5.0),
    # 4XMM: POSERR = RADEC_ERR (+) SYSERRCC, 1 sigma; EPIC on-axis PSF ~6"
    # FWHM (Webb et al. 2020).
    "XMM 4XMM-DR13": SurveyProfile(None, 1.5, 6.0, 10.0),
    # eRASS1 (Merloni et al. 2024): POS_ERR is 1 sigma and peaks at ~4.5";
    # the survey-averaged PSF half-energy width is 30" (an HEW, used here as
    # the resolution scale); survey Dec 2019 - Jun 2020 (corrected 2.16.0).
    "eROSITA eRASS1": SurveyProfile(2020.2, 4.5, 30.0, 20.0),
    "ATNF Pulsar Catalog": SurveyProfile(None, 0.5, None, 5.0),
    # MYStIX MPCM: X-ray (Chandra ACIS), UKIDSS/2MASS or Spitzer positions;
    # ePos is the 1-sigma error, 0-2.1" (Broos et al. 2013, Table 2).
    "MYStIX MPCM": SurveyProfile(None, 0.5, None, 5.0),
    # Roma-BZCAT: radio (VLA/ATCA) or optical positions, ~1" (Massaro+2015).
    "Roma-BZCAT": SurveyProfile(2000.0, 1.0, None, 5.0),
    "HASH PN Catalog": SurveyProfile(None, 1.0, None, 8.0),
    "ASAS-SN Supernova Catalog": SurveyProfile(2000.0, 1.0, None, 5.0, "transient_event"),
    "Asiago Supernova Catalog": SurveyProfile(2000.0, 1.0, None, 5.0, "transient_event"),
    "Acker PN Spectroscopy": SurveyProfile(2000.0, 2.0, None, 8.0),
    # SGA-2020 centres come from Legacy Surveys ellipse fits of large galaxies.
    "SGA-2020": SurveyProfile(None, 1.0, None, 5.0),
    # Legacy Surveys DR10: delivered seeing ~1.3/1.2/1.1" in g/r/z (DECaLS;
    # Dey et al. 2019).  Per-source errors come from ra_ivar/dec_ivar and the
    # epoch from ref_epoch (Gaia-matched stars) when fetched (2.16.0); before
    # this the main photometry source fell back to DEFAULT_PROFILE.  The
    # fallback error stays the conservative 0.6" (2.19.0; 0.10" split the
    # NGC 4522 nucleus from its galaxy), see also LS_RESOLVED_FLOOR_ARCSEC.
    "DESI Legacy Surveys DR10": SurveyProfile(None, 0.6, 1.2, 4.0),
    # DESI DR1 redshift catalogues give TARGET_RA/TARGET_DEC, the imaging
    # position the target was selected at (Legacy Surveys DR9 Tractor or
    # Gaia; Myers et al. 2023, AJ 165, 50), not a fibre or spectral
    # centroid, so the error is that of LS astrometry (~0.03" bright, 0.1"
    # used).  With the 0.6" default, a target 0.01" from its LS source and
    # 0.34" from a neighbouring star scored 0.85 vs 1 and became an
    # evidence-less "ambiguous" object (field RA 250, 2.28.0).  Resolved LS
    # sources keep their own 0.6" floor in the pair sigma.
    "DESI DR1 spectroscopy": SurveyProfile(None, 0.1, None, 5.0),
    "DESI DR1 FastSpecFit": SurveyProfile(None, 0.1, None, 5.0),
}
DEFAULT_PROFILE = SurveyProfile(None, 0.6, None, 5.0)
LS_RESOLVED_FLOOR_ARCSEC = 0.6


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
    aliases = set()
    low = {str(k).lower(): k for k in row.keys()}

    def add(ns, value):
        if value is None:
            return
        v = str(value).strip().upper().replace(" ", "")
        if not v or v in {"NAN", "NONE", "--"}:
            return
        aliases.add(f"{ns}:{v}")

    if catalog == "AllWISE":
        add("WISE", catalog_object_id)
    if catalog == "2MASS PSC":
        add("2MASS", catalog_object_id)
    for key in ("wisea", "allwise", "wise", "wise_id"):
        if key in low:
            add("WISE", row.get(low[key]))
    for key in ("_2mass", "2mass", "2mass_name", "tmass"):
        if key in low:
            add("2MASS", row.get(low[key]))
    # Legacy Surveys source identity.  DESI TARGETIDs pack RELEASE, BRICKID and
    # OBJID of the Legacy Surveys target (desitarget.targets.encode_targetid),
    # so a DESI spectrum links to its photometric source exactly where the two
    # releases agree (DR10 keeps the DR9 IDs in the north; release 9011).
    # Bit layout: OBJID 0-21, BRICKID 22-41, RELEASE 42-57,
    # MOCK 58, SKY 59; e.g. 39627887455767055 -> release 9010 (LS DR9 south).
    if catalog == "DESI Legacy Surveys DR10":
        rel, bid, oid = (_int(row.get(low[k])) if k in low else None for k in ("release", "brickid", "objid"))
        if None not in (rel, bid, oid):
            add("LSID", f"{rel}_{bid}_{oid}")
    if catalog in ("DESI DR1 spectroscopy", "DESI DR1 FastSpecFit"):
        tid = _int(catalog_object_id if catalog_object_id is not None else row.get(low.get("targetid", "TargetID")))
        if tid is not None and tid > 0 and not (tid >> 58) & 0x3:  # skip mock / sky targets
            add("LSID", f"{(tid>>42)&0xFFFF}_{(tid>>22)&0xFFFFF}_{tid&0x3FFFFF}")
    return aliases


def _int(v):
    """Exact integer (64-bit IDs must not pass through float)."""
    if v is None:
        return None
    try:
        x = int(str(v).strip())
    except (TypeError, ValueError):
        try:
            x = int(float(v))
        except (TypeError, ValueError, OverflowError):
            return None
    return x if x >= 0 else None


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
    mjd = _first(row, ("obs_mjd", "mjd_obs", "observation_mjd", "epochmean"))
    if mjd is not None and 10000 < mjd < 100000:
        return 2000.0 + (mjd - 51544.5) / 365.25
    return profile_for(catalog, row).ref_epoch


def infer_poserr_arcsec(catalog: str, row: Mapping[str, Any]) -> float:
    # Chandra CSC: r0 is the major radius of the 95 % confidence ellipse
    # (statistical only); the 1-sigma error is r0/2.448 (2-D Gaussian) and the
    # documented 0.16" astrometric systematic is added in quadrature.
    if catalog == "Chandra CSC 2.0":
        r0 = _first(row, ("err_ellipse_r0", "r0", "errmaj", "err_maj"))
        if r0 is not None and r0 > 0:
            return math.hypot(r0 / 2.448, 0.16)

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

    # eRASS1 POS_ERR (VizieR posErr) and 4XMM SC_POSERR (VizieR ePos) are
    # 1-sigma with systematics included (Merloni+2024; Webb+2020).  Column
    # names checked on the live VizieR tables (2.19.1 probe).
    if catalog in ("eROSITA eRASS1", "XMM 4XMM-DR13", "MYStIX MPCM"):
        e = _first(row, ("pos_err", "poserr", "e_pos", "epos", "sc_poserr"))
        if e is not None and e > 0:
            return e

    # Legacy Surveys ra_ivar/dec_ivar are inverse variances in 1/deg^2 (RA
    # without the cos(dec) term, i.e. along the RA coordinate).
    if catalog == "DESI Legacy Surveys DR10":
        a, b = _first(row, ("ra_ivar",)), _first(row, ("dec_ivar",))
        if a is not None and b is not None and a > 0 and b > 0:
            cosd = abs(math.cos(math.radians(_first(row, ("dec",)) or 0.0)))
            err = max(cosd / math.sqrt(a), 1.0 / math.sqrt(b)) * 3600.0
            # The ivar error is formal, for the model centre.  For a resolved
            # Tractor model the centre other surveys measure (a nucleus, a
            # moment centroid) differs at the arcsec level (2.2" for the
            # NGC 4522 PS1 / 2MASS nucleus), so resolved sources keep the
            # conservative floor.
            typ = str(row.get("type", "")).strip().upper()
            return max(err, LS_RESOLVED_FLOOR_ARCSEC) if typ and typ not in ("PSF", "GPSF") else err

    # Pan-STARRS DR2 raMeanErr / decMeanErr are in arcsec (MAST PS1 DR2
    # MeanObject schema).  Until 2.19.0 they were divided by 1000 as if in
    # mas, giving 1e-5" errors that only the PSF/6 floor hid.
    if catalog == "Pan-STARRS1 DR2 MeanObject":
        a, b = _first(row, ("rameanerr",)), _first(row, ("decmeanerr",))
        if a is not None and b is not None and max(a, b) > 0:
            return max(a, b)

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


def propagate_linear(
    ra_deg: float, dec_deg: float, pmra_masyr: float, pmdec_masyr: float, from_epoch: float, to_epoch: float
) -> tuple[float, float]:
    """Propagate ICRS coordinates with a linear proper motion.

    The displacement is applied along the local east / north unit vectors and
    the result renormalised (2.23.0): the old (dRA / cos dec, dDec) offsets
    gave Dec > 90 for a mover near a pole.  Identical to first order elsewhere.
    pmra is mu_alpha* (includes cos dec), as in Gaia.
    """
    dt = to_epoch - from_epoch
    a, d = math.radians(ra_deg), math.radians(dec_deg)
    k = math.radians(1.0 / 3.6e6) * dt  # mas/yr * yr -> radians
    ue, un = pmra_masyr * k, pmdec_masyr * k
    sa, ca, sd, cd = math.sin(a), math.cos(a), math.sin(d), math.cos(d)
    x = cd * ca - ue * sa - un * sd * ca
    y = cd * sa + ue * ca - un * sd * sa
    z = sd + un * cd
    ra = math.degrees(math.atan2(y, x)) % 360.0
    dec = math.degrees(math.atan2(z, math.hypot(x, y)))
    return ra, dec


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
    posterior = (
        density_l / (density_l + density_arcsec2) if density_arcsec2 is not None and density_arcsec2 > 0 else positional
    )
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
