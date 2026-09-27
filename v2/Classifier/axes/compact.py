"""Compact-object axis.

Evidence order:
1. ATNF Pulsar Catalog counterpart: direct PULSAR identification.
2. Exact curated SIMBAD physical types for pulsars/X-ray binaries.
3. Gaia compact-companion candidate flag, which is never promoted to NS/PULSAR/XRB.
"""
from __future__ import annotations
import math
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

def _num(row,key):
    try:
        value=float(row.get(key))
        return value if math.isfinite(value) else None
    except Exception:return None

def classify(row):
    catalogs=_text(row,"catalogs") or ""
    if "ATNF Pulsar Catalog" in catalogs:
        assoc=_num(row,"association_confidence__atnf_pulsar_catalog")
        return {
            "axis":AXIS,"label":"PULSAR","confidence":None,
            "status":"ATNF_CATALOG_MATCH",
            "evidence":[{
                "kind":"atnf_pulsar_catalog_counterpart",
                "association_confidence":assoc,
                "note":"Counterpart associated with the ATNF Pulsar Catalog; association quality retained separately from class identity.",
            }],
        }

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
