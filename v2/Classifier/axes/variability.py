"""Variability axis: RR Lyrae, Cepheid, Mira, eclipsing, rotational, eruptive, etc."""
from __future__ import annotations
AXIS="variability"
CLASSES=("RR_LYRAE","CEPHEID","MIRA","ECLIPSING","ROTATIONAL","ERUPTIVE","OTHER_VARIABLE","UNKNOWN")
def classify(row):
    return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"NOT_IMPLEMENTED","evidence":[]}
