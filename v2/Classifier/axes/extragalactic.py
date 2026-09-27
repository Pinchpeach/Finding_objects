"""Extragalactic axis: galaxy/AGN/QSO refinements."""
from __future__ import annotations
AXIS="extragalactic"
CLASSES=("GALAXY","AGN","QSO","OTHER_EXTRAGALACTIC","UNKNOWN")
def classify(row):
    return {"axis":AXIS,"label":"UNKNOWN","confidence":None,"status":"NOT_IMPLEMENTED","evidence":[]}
