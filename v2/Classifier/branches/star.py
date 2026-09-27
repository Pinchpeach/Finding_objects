"""STAR-family detailed refinement.

The branch returns independent stellar axes rather than forcing one mutually
exclusive subtype. Gaia DSC is used only for broad stellar-family candidates;
Gaia variability labels are preserved as catalog evidence; atmospheric
parameters are passed through for later validated spectral-typing models.
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

def classify(row):
    star=_num(row,"classprob_dsc_combmod_star")
    wd=_num(row,"classprob_dsc_combmod_whitedwarf")
    binary=_num(row,"classprob_dsc_combmod_binarystar")

    family="UNRESOLVED"
    family_score=None
    family_basis="insufficient stellar-family evidence"
    candidates=[("WHITE_DWARF_CANDIDATE",wd),("BINARY_CANDIDATE",binary),("STAR_LIKE",star)]
    valid=[x for x in candidates if x[1] is not None]
    if valid:
        best=max(valid,key=lambda x:x[1])
        # Candidate threshold is deliberately conservative. Detailed WD/binary
        # type is not inferred here.
        if best[1] >= 0.80:
            family,family_score=best
            family_basis="Gaia DR3 DSC dominant stellar-family posterior"

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

    # Spectral type is intentionally unresolved until a validated XP/spectrum
    # model is installed. GSP-Phot parameters are exposed as inputs, not mapped
    # through hand-written temperature cuts.
    result={
        "detailed_class":family,
        "confidence":family_score,
        "stellar_family":family,
        "stellar_family_score":family_score,
        "variability":variability,
        "spectral_type":"UNRESOLVED",
        "stellar_parameters":stellar_parameters,
        "basis":family_basis,
    }
    return result
