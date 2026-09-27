"""Phenomenon/event axis: SN, PN, nova and other transient/peculiar phenomena."""
from __future__ import annotations
AXIS="phenomenon"
CLASSES=("SN","PN","NOVA","OTHER_TRANSIENT","OTHER_PHENOMENON","NONE","UNKNOWN")
def classify(row):
    return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"NOT_IMPLEMENTED","evidence":[]}
