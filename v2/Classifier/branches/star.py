"""Conservative STAR-family refinement."""
from __future__ import annotations
import math

def _num(row,key):
    try:
        v=float(row.get(key))
        return v if math.isfinite(v) else None
    except Exception:
        return None

def classify(row):
    wd=_num(row,"classprob_dsc_combmod_whitedwarf")
    binary=_num(row,"classprob_dsc_combmod_binarystar")
    if wd is not None and wd >= 0.80:
        return {"detailed_class":"WHITE_DWARF_CANDIDATE","confidence":wd,
                "basis":"Gaia DR3 DSC white-dwarf posterior; spectral subtype deferred"}
    if binary is not None and binary >= 0.80:
        return {"detailed_class":"BINARY_CANDIDATE","confidence":binary,
                "basis":"Gaia DR3 DSC physical-binary posterior; binary type deferred"}
    return {"detailed_class":"UNRESOLVED","confidence":None,
            "basis":"STAR routed; validated stellar subtype model not yet applied"}
