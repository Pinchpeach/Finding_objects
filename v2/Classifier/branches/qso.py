"""Conservative QSO/AGN refinement."""
from __future__ import annotations
import math

def _has_positive(row,prefixes):
    for k,v in row.items():
        if any(str(k).startswith(p) for p in prefixes):
            try:
                x=float(v)
                if math.isfinite(x) and x>0: return True
            except Exception:
                pass
    return False

def classify(row):
    radio=_has_positive(row,("rx_radio_","first_","nvss_","lotss_","vlass_"))
    xray=_has_positive(row,("rx_chandra_","rx_xmm_","rx_erosita_","chandra_","xmm_","erosita_"))
    return {"detailed_class":"UNRESOLVED","confidence":None,
            "radio_detected":radio,"xray_detected":xray,
            "basis":"QSO routed; radio-loudness/subtype requires dedicated validated definition/model"}
