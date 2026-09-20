"""Interpretable top-down decision-tree classification for astronomical objects.

The tree is deliberately hierarchical: observations fill high-level physical
properties first; lower branches are evaluated only when their prerequisites
are supported. Predictions never become Method 2 reference labels.
"""
from dataclasses import dataclass, asdict
import math

@dataclass
class DecisionNode:
    node: str
    value: str
    evidence: str
    confidence: float | None = None

def _ok(x): return x is not None and not (isinstance(x,float) and math.isnan(x))

def classify_decision_tree(f: dict):
    path=[]
    # L1: data/association validity
    assoc=f.get("counterpart_status")
    usable=assoc in {None,"probable_counterpart","confirmed"} or bool(f.get("spectrum_verified"))
    path.append(DecisionNode("L1_observation_validity","usable" if usable else "uncertain",
        f"counterpart={assoc}; spectrum_verified={bool(f.get('spectrum_verified'))}"))
    if not usable:
        return {"predicted_class":"UNKNOWN","decision_path":[asdict(x) for x in path],"reason":"association/coverage not secure"}

    # L2: stellar vs extragalactic physical evidence
    stellar=0; extra=0; ev=[]
    if _ok(f.get("parallax_snr")) and f["parallax_snr"]>=5: stellar+=3; ev.append("significant parallax")
    if _ok(f.get("proper_motion_snr")) and f["proper_motion_snr"]>=5: stellar+=2; ev.append("significant proper motion")
    z=f.get("redshift")
    if _ok(z) and z>0.002: extra+=3; ev.append("non-zero spectroscopic redshift")
    if f.get("extended_morphology") is True: extra+=2; ev.append("extended morphology")
    if f.get("stellar_absorption_pattern") is True: stellar+=2; ev.append("stellar absorption pattern")
    branch="stellar" if stellar>extra else "extragalactic" if extra>stellar else "undetermined"
    path.append(DecisionNode("L2_physical_branch",branch,"; ".join(ev) or "insufficient physical evidence"))
    if branch=="stellar":
        return {"predicted_class":"STAR","decision_path":[asdict(x) for x in path],
                "reason":"stellar branch supported","needs_subtype":True}
    if branch=="undetermined":
        return {"predicted_class":"UNKNOWN","decision_path":[asdict(x) for x in path],
                "reason":"stellar/extragalactic branch unresolved"}

    # L3: AGN/QSO vs galaxy
    agn=0; gal=0; ev=[]
    if f.get("broad_permitted_lines") is True: agn+=4; ev.append("broad permitted lines")
    if f.get("high_ionization_lines") is True: agn+=2; ev.append("high-ionization lines")
    if f.get("xray_excess") is True or f.get("radio_excess") is True: agn+=1; ev.append("X-ray/radio excess")
    if f.get("wise_agn_colors") is True: agn+=1; ev.append("mid-IR AGN-like colors")
    if f.get("narrow_nebular_lines") is True: gal+=1; ev.append("narrow nebular lines")
    if f.get("extended_morphology") is True: gal+=1; ev.append("extended morphology")
    branch="QSO" if agn>=4 and agn>gal else "GALAXY" if gal>agn or agn<4 else "AMBIGUOUS_AGN_GALAXY"
    path.append(DecisionNode("L3_extragalactic_type",branch,"; ".join(ev) or "insufficient AGN/galaxy evidence"))
    return {"predicted_class":branch,"decision_path":[asdict(x) for x in path],
            "reason":"top-down physical decision tree","needs_subtype":True}

def flatten_path(result):
    return " > ".join(f"{n['node']}={n['value']}" for n in result["decision_path"])
