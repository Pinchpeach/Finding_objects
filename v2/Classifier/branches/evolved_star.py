"""Conservative evolved-giant evidence from Gaia DR3 FLAME.

FLAME evolstage > 490 marks a giant (100-420 main sequence, 420-490
subgiant); values above ~1300 point to bad GSP-Phot parameters (Fouesneau et
al. 2023, Sect. 3.3.2; Gaia DR3 documentation 11.3.6).  Giant masses and
ages are usable only for 1.0 < M < 2.0 Msun and age > 1.5 Gyr (Fouesneau et
al. 2023; the documentation says > 1 Gyr) with the second flags_flame digit
0.  The FLAME tracks end at the RGB tip, so red-clump and AGB stars are
forced onto an "RGB" stage: a passing star is labelled RED_GIANT (RGB or
AGB), not RGB (2.17.0; on 180 Kepler RGB/AGB stars the old guardrails passed
8 RGB + 2 AGB, these 8 RGB + 1 AGB).
"""
from __future__ import annotations
import math

def _num(row,key):
    try:
        value=float(row.get(key))
        return value if math.isfinite(value) else None
    except Exception:
        return None

def classify(row):
    stage=_num(row,"evolstage_flame")
    logg=_num(row,"logg_gspphot")
    mass=_num(row,"mass_flame")
    age=_num(row,"age_flame")
    flags=row.get("flags_flame")
    try:
        flags=str(int(float(flags))).zfill(2) if flags is not None and str(flags).strip() not in ("","nan") else None
    except (TypeError,ValueError):
        flags=str(flags).strip() or None
    payload={
        "evolstage_flame":stage,
        "logg_gspphot":logg,
        "mass_flame":mass,
        "age_flame":age,
        "flags_flame":flags,
    }
    if None in (stage,logg,mass,age):
        return {
            "label":"UNRESOLVED","confidence":None,"status":"MISSING_FLAME_GIANT_QUALITY",
            "evidence":[{"kind":"gaia_flame","values":payload,
                         "note":"RGB inference requires FLAME stage plus giant validation guardrails."}],
        }
    flags_ok=flags is None or (len(flags)>=2 and flags[1]=="0")
    if 490 <= stage <= 1300 and logg < 3.5 and 1.0 <= mass < 2.0 and age > 1.5 and flags_ok:
        return {
            "label":"RED_GIANT","confidence":None,"status":"GAIA_FLAME_GIANT",
            "evidence":[{"kind":"gaia_flame","values":payload,
                         "note":"Gaia FLAME giant stage within the Fouesneau+2023 mass/age guardrails; FLAME cannot separate RGB from red clump / AGB."}],
        }
    return {
        "label":"UNRESOLVED","confidence":None,"status":"NO_VALIDATED_RGB_AGB_LABEL",
        "evidence":[{"kind":"gaia_flame","values":payload,
                     "note":"No validated AGB inference is made from FLAME; out-of-guardrail giant stages abstain."}],
    }
