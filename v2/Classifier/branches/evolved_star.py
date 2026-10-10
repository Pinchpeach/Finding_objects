"""Conservative RGB/AGB refinement from Gaia DR3 FLAME.

Gaia DR3 FLAME evolstage=490 marks the RGB base and 1290 the RGB tip. We apply
the Gaia validation guardrails used for giant FLAME parameters (logg < 3.5,
mass < 2 Msun, age > 1 Gyr). FLAME does not provide an AGB stage in this
published convention, so AGB remains unresolved instead of being guessed.
"""

from __future__ import annotations
import math
import sys as _sys
from pathlib import Path as _Path

_V2 = _Path(__file__).resolve().parents[2]
if str(_V2) not in _sys.path:
    _sys.path.insert(0, str(_V2))
from common import row_num as _num  # noqa: E402


def classify(row):
    stage = _num(row, "evolstage_flame")
    logg = _num(row, "logg_gspphot")
    mass = _num(row, "mass_flame")
    age = _num(row, "age_flame")
    payload = {
        "evolstage_flame": stage,
        "logg_gspphot": logg,
        "mass_flame": mass,
        "age_flame": age,
    }
    if None in (stage, logg, mass, age):
        return {
            "label": "UNRESOLVED",
            "confidence": None,
            "status": "MISSING_FLAME_GIANT_QUALITY",
            "evidence": [
                {
                    "kind": "gaia_flame",
                    "values": payload,
                    "note": "RGB inference requires FLAME stage plus giant validation guardrails.",
                }
            ],
        }
    if 490 <= stage <= 1290 and logg < 3.5 and mass < 2.0 and age > 1.0:
        return {
            "label": "RGB",
            "confidence": None,
            "status": "GAIA_FLAME_RGB",
            "evidence": [
                {
                    "kind": "gaia_flame",
                    "values": payload,
                    "note": "Gaia FLAME evolutionary stage lies from RGB base through RGB tip and passes giant validation guardrails.",
                }
            ],
        }
    return {
        "label": "UNRESOLVED",
        "confidence": None,
        "status": "NO_VALIDATED_RGB_AGB_LABEL",
        "evidence": [
            {
                "kind": "gaia_flame",
                "values": payload,
                "note": "No validated AGB inference is made from FLAME; out-of-guardrail giant stages abstain.",
            }
        ],
    }
