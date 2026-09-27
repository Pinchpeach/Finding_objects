"""Compact-object evidence axis.

Gaia DR3 can identify ellipsoidal-variable systems with possible compact
companions. That is not equivalent to identifying the observed source itself as
a neutron star/black hole, so the branch exposes a separate candidate class and
does not promote it to NS/PULSAR/XRB without additional validated evidence.
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

def classify(row):
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
