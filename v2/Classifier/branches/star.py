"""STAR-family detailed refinement.

This branch is conservative by design:
- Gaia HR-locus and Gaia DSC provide WHITE_DWARF candidate evidence.
- Strongly conflicting evidence produces UNRESOLVED rather than a forced label.
- Variability remains an independent axis.
- DA/DB/DC/DQ/DZ/DO spectral typing is not attempted from broadband features.
"""
from __future__ import annotations
import math

def _num(row,key):
    try:
        v=float(row.get(key))
        return v if math.isfinite(v) else None
    except Exception:
        return None

def _text(row,key):
    v=row.get(key)
    if v is None: return None
    s=str(v).strip()
    return None if not s or s.lower()=="nan" else s

def _wd_hr_signal(row):
    """Gentile Fusillo+2021 broad Gaia WD-locus signal.

    Returns True/False only when the literature cut is directly usable;
    otherwise returns None. This is candidate evidence, not a subtype.
    """
    p=_num(row,"parallax"); pe=_num(row,"parallax_error")
    g=_num(row,"phot_g_mean_mag")
    color=_num(row,"bp_rp")
    if color is None:
        bp=_num(row,"phot_bp_mean_mag"); rp=_num(row,"phot_rp_mean_mag")
        if bp is not None and rp is not None: color=bp-rp
    if None in (p,pe,g,color) or p<=0 or pe<=0 or p/pe<=1:
        return None
    abs_g=g+5*math.log10(p)-10
    return bool(abs_g > 6 + 5*color)

def classify(row):
    star=_num(row,"classprob_dsc_combmod_star")
    wd=_num(row,"classprob_dsc_combmod_whitedwarf")
    binary=_num(row,"classprob_dsc_combmod_binarystar")
    hr=_wd_hr_signal(row)

    dsc_wd=wd is not None and wd>=0.80
    dsc_star=star is not None and star>=0.80
    dsc_binary=binary is not None and binary>=0.80

    family="UNRESOLVED"
    family_score=None
    family_basis="insufficient or conflicting stellar-family evidence"

    if hr is True and (dsc_star or dsc_binary) and not dsc_wd:
        family_basis="Gaia HR WD-locus conflicts with strong Gaia DSC non-WD stellar-family evidence"
    elif dsc_wd and hr is False:
        family_basis="strong Gaia DSC WD posterior conflicts with usable Gaia HR-locus evidence"
    elif dsc_wd or hr is True:
        family="WHITE_DWARF_CANDIDATE"
        family_score=wd if dsc_wd else None
        if dsc_wd and hr is True:
            family_basis="Gaia DSC and literature Gaia HR-locus both support WD candidate"
        elif dsc_wd:
            family_basis="Gaia DR3 DSC white-dwarf posterior; HR-locus unavailable"
        else:
            family_basis="Gentile Fusillo+2021 broad Gaia HR-locus WD candidate evidence"
    elif dsc_binary:
        family="BINARY_CANDIDATE"
        family_score=binary
        family_basis="Gaia DR3 DSC physical-binary posterior"
    elif dsc_star:
        family="STAR_LIKE"
        family_score=star
        family_basis="Gaia DR3 DSC stellar posterior"

    var_class=_text(row,"best_class_name")
    var_score=_num(row,"best_class_score")
    variability={
        "class": var_class if var_class else "UNRESOLVED",
        "catalog_score": var_score,
        "basis": "Gaia DR3 vari_classifier_result; score retained as catalog evidence, not assumed calibrated across classes"
                if var_class else "no Gaia DR3 variability class available",
    }

    stellar_parameters={
        "teff_gspphot":_num(row,"teff_gspphot"),
        "logg_gspphot":_num(row,"logg_gspphot"),
        "mh_gspphot":_num(row,"mh_gspphot"),
    }

    # Gaia-XP DA/DB subtype predictions are accepted only after the object is
    # independently routed as a WD candidate. The 0.90 gate was fixed before
    # the independent SDSS DR14 external evaluation; unsupported/low-confidence
    # cases remain UNRESOLVED.
    xp_subtype=_text(row,"wd_xp_subtype_prediction")
    xp_conf=_num(row,"wd_xp_subtype_confidence")
    spectral_type="UNRESOLVED"
    spectral_type_confidence=None
    spectral_basis="Gaia XP coefficients or validated optical spectrum model required"
    if family=="WHITE_DWARF_CANDIDATE" and xp_subtype in {"DA","DB"} and xp_conf is not None and xp_conf>=0.90:
        spectral_type=xp_subtype
        spectral_type_confidence=xp_conf
        spectral_basis="externally validated Gaia-XP DA/DB model; calibrated probability >= 0.90"

    return {
        "detailed_class":family,
        "confidence":family_score,
        "stellar_family":family,
        "stellar_family_score":family_score,
        "wd_hr_locus_signal":hr,
        "variability":variability,
        "spectral_type":spectral_type,
        "spectral_type_confidence":spectral_type_confidence,
        "spectral_type_requirement":spectral_basis,
        "stellar_parameters":stellar_parameters,
        "basis":family_basis,
    }
