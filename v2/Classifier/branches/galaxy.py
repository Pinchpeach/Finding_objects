"""Conservative GALAXY-family refinement."""
from __future__ import annotations

def classify(row):
    # Detailed early/spiral/bar/merger morphology should be image-based or use
    # a separately validated morphology model (e.g. Galaxy Zoo-style labels).
    return {"detailed_class":"UNRESOLVED","confidence":None,
            "basis":"GALAXY routed; detailed morphology requires dedicated image/model branch"}
