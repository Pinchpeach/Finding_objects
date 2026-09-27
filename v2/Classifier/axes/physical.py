"""Physical/evolutionary-state axis: WD, RGB, AGB and future stellar states."""
from __future__ import annotations
AXIS="physical"
CLASSES=("WD","RGB","AGB","OTHER_STELLAR","UNKNOWN")
def classify(row):
    return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"NOT_IMPLEMENTED","evidence":[]}
