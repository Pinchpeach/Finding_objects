"""Compact-object axis: NS/pulsar and future compact-object subclasses."""
from __future__ import annotations
AXIS="compact"
CLASSES=("NS","PULSAR","XRB","OTHER_COMPACT","UNKNOWN")
def classify(row):
    return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"NOT_IMPLEMENTED","evidence":[]}
