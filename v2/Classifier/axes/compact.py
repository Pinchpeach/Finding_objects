"""Compact-object axis.

Exact curated SIMBAD physical types can identify pulsars and X-ray binaries.
Gaia DR3 compact-companion evidence remains a candidate-only route and is never
promoted to NS/PULSAR/XRB by itself.
"""
from __future__ import annotations
AXIS="compact"
CLASSES=("NS","PULSAR","XRB","COMPACT_COMPANION_CANDIDATE","OTHER_COMPACT","UNKNOWN")

def _bool(row,key):
    value=row.get(key)
    if value is None:return False
    if isinstance(value,bool):return value
    text=str(value).strip().lower()
    return text in {"1","1.0","true","t","yes"}

def _text(row,key):
    value=row.get(key)
    if value is None:return None
    value=str(value).strip()
    return None if not value or value.lower()=="nan" else value

def classify(row):
    simbad=_text(row,"otype")
    if simbad=="Psr":
        return {
            "axis":AXIS,"label":"PULSAR","confidence":None,
            "status":"SIMBAD_CURATED_PULSAR",
            "evidence":[{"kind":"simbad_physical_type","otype":"Psr","note":"Exact SIMBAD Pulsar physical type."}],
        }
    if simbad in {"XB*","LXB","HXB"}:
        return {
            "axis":AXIS,"label":"XRB","confidence":None,
            "status":"SIMBAD_CURATED_XRB",
            "evidence":[{"kind":"simbad_physical_type","otype":simbad,"note":"Exact SIMBAD X-ray-binary physical type."}],
        }
    if _bool(row,"in_vari_compact_companion"):
        return {
            "axis":AXIS,
            "label":"COMPACT_COMPANION_CANDIDATE",
            "confidence":None,
            "status":"GAIA_DR3_COMPACT_COMPANION_CANDIDATE",
            "evidence":[{
                "kind":"gaia_dr3_vari_summary",
                "in_vari_compact_companion":True,
                "note":"Candidate compact companion system; not promoted to NS/PULSAR/XRB.",
            }],
        }
    return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"NO_VALIDATED_COMPACT_EVIDENCE","evidence":[]}
