"""Hierarchical astronomical decision trees.

Nodes use four-state evidence: TRUE, FALSE, UNKNOWN, CONFLICTING.
Identity and characterization are intentionally separate.  Missing observations
never become negative evidence, and Method-1 predictions never become Method-2
reference labels.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any

class EvidenceState(str, Enum):
    TRUE="TRUE"; FALSE="FALSE"; UNKNOWN="UNKNOWN"; CONFLICTING="CONFLICTING"

@dataclass
class NodeResult:
    node: str
    state: str
    value: str
    evidence: list[str]
    counter_evidence: list[str]
    missing: list[str]

def state(v: Any) -> EvidenceState:
    if isinstance(v,EvidenceState): return v
    if v is True: return EvidenceState.TRUE
    if v is False: return EvidenceState.FALSE
    if isinstance(v,str) and v.upper() in EvidenceState.__members__: return EvidenceState[v.upper()]
    return EvidenceState.UNKNOWN

def _node(node,value,e=(),c=(),m=(),s="TRUE"):
    return NodeResult(node,s,value,list(e),list(c),list(m))

def identity_tree(f: dict) -> dict:
    path=[]
    # 1 observation validity
    if f.get("official_footprint") is False:
        path.append(_node("observation_validity","NOT_OBSERVED",m=["usable survey observation"]))
        return _finish("NOT_OBSERVED",path)
    assoc=f.get("counterpart_status")
    direct=bool(f.get("spectrum_verified"))
    if not direct and assoc in {"ambiguous","likely_not_same_object","observed_no_counterpart","no_response"}:
        path.append(_node("observation_validity","UNRESOLVED",e=[f"counterpart={assoc}"],m=["secure association"]))
        return _finish("UNKNOWN",path)
    path.append(_node("observation_validity","USABLE",e=["verified spectrum" if direct else f"counterpart={assoc}"]))

    # 2 stellar/extragalactic
    stellar=[]; extra=[]; missing=[]
    if f.get("parallax_snr",0)>=5: stellar.append("parallax S/N >= 5")
    if f.get("proper_motion_snr",0)>=5: stellar.append("proper-motion S/N >= 5")
    if state(f.get("stellar_absorption_pattern"))==EvidenceState.TRUE: stellar.append("stellar absorption pattern")
    z=f.get("redshift")
    if z is not None and z>0.002: extra.append("spectroscopic redshift > 0.002")
    if state(f.get("extended_morphology"))==EvidenceState.TRUE: extra.append("extended morphology")
    if not stellar and not extra: missing+=["parallax/proper motion","redshift","morphology","stellar spectral pattern"]
    if stellar and extra:
        path.append(_node("physical_branch","CONFLICTING",stellar,extra,missing,s="CONFLICTING"))
        return _finish("AMBIGUOUS",path)
    if stellar:
        path.append(_node("physical_branch","STELLAR",stellar,extra,missing))
        return _finish("STAR",path,characterize_star(f))
    if not extra:
        path.append(_node("physical_branch","UNKNOWN",m=missing,s="UNKNOWN"))
        return _finish("UNKNOWN",path)
    path.append(_node("physical_branch","EXTRAGALACTIC",extra,stellar))

    # 3 AGN/QSO vs galaxy
    agn=[]; gal=[]
    if state(f.get("broad_permitted_lines"))==EvidenceState.TRUE: agn.append("broad permitted lines")
    if state(f.get("high_ionization_lines"))==EvidenceState.TRUE: agn.append("high-ionization lines")
    if state(f.get("xray_excess"))==EvidenceState.TRUE: agn.append("X-ray excess")
    if state(f.get("radio_excess"))==EvidenceState.TRUE: agn.append("radio excess")
    if state(f.get("wise_agn_colors"))==EvidenceState.TRUE: agn.append("WISE AGN-like SED")
    if state(f.get("narrow_nebular_lines"))==EvidenceState.TRUE: gal.append("narrow nebular lines")
    if state(f.get("extended_morphology"))==EvidenceState.TRUE: gal.append("extended morphology")
    broad_state=state(f.get("broad_permitted_lines"))
    # A non-detection is not an absence unless broad-line sensitivity was adequate.
    broad_tested=bool(f.get("broad_line_test_adequate"))
    if broad_state==EvidenceState.TRUE:
        path.append(_node("extragalactic_identity","AGN_QSO",agn,gal))
        return _finish("QSO_AGN",path,characterize_agn(f))
    # Independent AGN evidence keeps the object out of the galaxy leaf while
    # broad-line status is UNKNOWN/insufficient.
    independent=[x for x in agn if x!="broad permitted lines"]
    if independent and (broad_state==EvidenceState.UNKNOWN or not broad_tested):
        path.append(_node("extragalactic_identity","AGN_CANDIDATE",independent,gal,
                          ["quantitative broad-line fit / FWHM"]))
        return _finish("AGN_CANDIDATE",path,characterize_agn(f))
    # Enter the galaxy leaf only when galaxy evidence exists and AGN evidence
    # does not dominate.  BPT/subtype decisions remain in the galaxy subtree.
    if gal and not independent:
        path.append(_node("extragalactic_identity","GALAXY",gal,agn))
        return _finish("GALAXY",path,characterize_galaxy(f))
    if agn:
        path.append(_node("extragalactic_identity","AGN_CANDIDATE",agn,gal,
                          ["decisive AGN diagnostic"]))
        return _finish("AGN_CANDIDATE",path,characterize_agn(f))
    path.append(_node("extragalactic_identity","UNKNOWN",m=["AGN/galaxy discriminating evidence"],s="UNKNOWN"))
    return _finish("UNKNOWN_EXTRAGALACTIC",path)

def characterize_star(f):
    p=[]
    if state(f.get("white_dwarf_pattern"))==EvidenceState.TRUE: subtype="WHITE_DWARF"
    elif state(f.get("molecular_bands"))==EvidenceState.TRUE: subtype="M_TYPE_CANDIDATE"
    elif state(f.get("strong_balmer_absorption"))==EvidenceState.TRUE: subtype="A_TYPE_CANDIDATE"
    elif state(f.get("helium_ii"))==EvidenceState.TRUE: subtype="O_TYPE_CANDIDATE"
    elif state(f.get("helium_i"))==EvidenceState.TRUE: subtype="B_TYPE_CANDIDATE"
    elif state(f.get("metal_absorption_strong"))==EvidenceState.TRUE: subtype="FGK_CANDIDATE"
    else: subtype="STELLAR_SUBTYPE_UNKNOWN"
    p.append(_node("stellar_spectral_subtype",subtype,m=[] if subtype!="STELLAR_SUBTYPE_UNKNOWN" else ["quantitative stellar spectrum/SED"],s="TRUE" if subtype!="STELLAR_SUBTYPE_UNKNOWN" else "UNKNOWN"))
    lum="LUMINOSITY_CLASS_AVAILABLE" if f.get("parallax_snr",0)>=5 and f.get("absolute_magnitude") is not None else "LUMINOSITY_CLASS_UNKNOWN"
    p.append(_node("stellar_luminosity",lum,m=[] if "AVAILABLE" in lum else ["reliable distance and absolute magnitude"],s="TRUE" if "AVAILABLE" in lum else "UNKNOWN"))
    return [asdict(x) for x in p]

def characterize_galaxy(f):
    p=[]
    morph="EARLY_TYPE" if state(f.get("smooth_concentrated"))==EvidenceState.TRUE else "DISK_SPIRAL" if state(f.get("disk_spiral"))==EvidenceState.TRUE else "IRREGULAR" if state(f.get("irregular"))==EvidenceState.TRUE else "MORPHOLOGY_UNKNOWN"
    p.append(_node("galaxy_morphology",morph,m=[] if morph!="MORPHOLOGY_UNKNOWN" else ["resolved morphology"],s="TRUE" if morph!="MORPHOLOGY_UNKNOWN" else "UNKNOWN"))
    req=["Halpha","Hbeta","OIII_5007","NII_6583"]; covered=all(f.get("line_covered",{}).get(x,False) for x in req); sig=all(f.get("line_snr",{}).get(x,0)>=3 for x in req)
    if covered and sig and f.get("bpt_class"): bpt=str(f["bpt_class"]).upper()
    else: bpt="INSUFFICIENT_BPT"
    p.append(_node("galaxy_emission_diagnostic",bpt,m=[] if bpt!="INSUFFICIENT_BPT" else ["Halpha/Hbeta/[OIII]/[NII] coverage and S/N"]))
    return [asdict(x) for x in p]

def characterize_agn(f):
    p=[]
    broad=state(f.get("broad_permitted_lines"))==EvidenceState.TRUE
    subtype="BROAD_LINE_AGN" if broad else "NARROW_LINE_AGN_CANDIDATE"
    p.append(_node("agn_spectral_type",subtype,e=["broad permitted lines"] if broad else [],m=[] if broad else ["broad-line evidence or narrow-line diagnostics"]))
    channels=[]
    for key,label in [("radio_excess","RADIO"),("xray_excess","XRAY"),("wise_agn_colors","IR"),("optical_variability","VARIABLE")]:
        if state(f.get(key))==EvidenceState.TRUE: channels.append(label)
    p.append(_node("agn_multiband_evidence",",".join(channels) if channels else "NONE_CONFIRMED",e=channels,m=[] if channels else ["calibrated radio/X-ray/IR/variability evidence"],s="TRUE" if channels else "UNKNOWN"))
    return [asdict(x) for x in p]

def _finish(label,path,characterization=None):
    return {"identity":label,"decision_path":[asdict(x) for x in path],"characterization":characterization or [],
            "reference_promotion_allowed":False}
