"""Transient/nebular phenomenon axis with independent event and spectroscopy channels.

Raw catalog/association scores are retained as evidence scores. They are not
reported as calibrated posterior probabilities; calibration is a separate stage.
"""

from __future__ import annotations
import functools
import importlib.util as _ilu
from pathlib import Path as _P

_s = _ilu.spec_from_file_location("v2_classifier_rowutil", _P(__file__).resolve().parents[1] / "_rowutil.py")
ROW = _ilu.module_from_spec(_s)
_s.loader.exec_module(ROW)
OTYPES = ROW.OTYPES
_num, _text = ROW.num, ROW.text
AXIS = "phenomenon"
_result = functools.partial(ROW.axis_result, AXIS)
CLASSES = ("SN", "PN", "NOVA", "MICROLENSING", "OTHER_TRANSIENT", "OTHER_PHENOMENON", "NONE", "UNKNOWN")
# Curated SIMBAD types (resolved through the otype hierarchy, 2.22.0):
# code -> (label, status).
SIMBAD_CURATED = {
    "SN*": ("SN", "SIMBAD_CURATED_SN"),
    "PN": ("PN", "SIMBAD_CURATED_PN"),
    "No*": ("NOVA", "SIMBAD_CURATED_NOVA"),
}
# Gaia DR3 vari_classifier_result event classes -> (label, status).
GAIA_EVENTS = {
    "SN": ("SN", "GAIA_DR3_SN_CANDIDATE"),
    "MICROLENSING": ("MICROLENSING", "GAIA_DR3_MICROLENSING_CANDIDATE"),
}


def _event_evidence(row, catalog, kind):
    assoc = _num(
        row,
        "association_confidence__" + catalog.lower().replace("-", "_").replace(" ", "_").replace("/", "_").strip("_"),
    )
    event_mjd = _num(row, "event_mjd")
    obs_mjd = _num(row, "observation_mjd") or _num(row, "obs_mjd")
    dt = None if event_mjd is None or obs_mjd is None else obs_mjd - event_mjd
    return assoc, {
        "kind": kind,
        "association_confidence": assoc,
        "event_mjd": event_mjd,
        "observation_mjd": obs_mjd,
        "delta_days": dt,
        "sn_subtype": _text(row, "sn_subtype"),
        "note": "Transient event is kept separate from persistent host-galaxy detections; event time is retained when available.",
    }


def _pn_lines(row):
    vals = {
        k: _num(row, k)
        for k in (
            "pn_heii_4686",
            "pn_oiii_4363",
            "pn_oiii_5007",
            "pn_halpha",
            "pn_nii_6584",
            "pn_sii_6717",
            "pn_sii_6731",
        )
    }
    detected = {k: v for k, v in vals.items() if v is not None and v > 0}
    ratio = None
    if vals["pn_oiii_5007"] and vals["pn_halpha"]:
        ratio = vals["pn_oiii_5007"] / vals["pn_halpha"]
    return detected, ratio


# HASH PNstat codes (VizieR V/163 ReadMe, Note 3; Parker, Bojicic & Frew
# 2016): T = True, L = Likely, P = Possible PN.  c (new candidates), s
# (objects to check), o (interesting object), ooun (unknown nature), k
# (transition object) are not yet graded.  Every other code is a PN mimic or
# non-PN entry (HII region, symbiotic star, galaxy, YSO, artefact, ...; X /
# N = "Not PN").  2.19.1: the 2.18.0 parser guessed words; the live column
# holds these codes, and unknown letters were kept as PN.
HASH_PN = {"T": "TRUE", "L": "LIKELY"}
HASH_POSSIBLE = {"P"}
HASH_UNGRADED = {"c", "s", "o", "ooun", "k", "test"}


def _hash_grade(status):
    s = (status or "").strip()
    if not s:
        return None  # no status column: identity evidence as before
    if s in HASH_PN:
        return HASH_PN[s]
    if s in HASH_POSSIBLE:
        return "POSSIBLE"
    if s in HASH_UNGRADED:
        return "UNGRADED"
    return "NOT_PN"


def _sn_epoch_status(ev):
    """Catalogue SN matched long after the event is the host, not the SN."""
    dt = ev.get("delta_days")
    return dt is not None and dt > SN_MAX_DELTA_DAYS


# A catalogued SN is the transient only near its event: an observation more
# than a year after discovery sees the host galaxy (same rule as the
# time-domain branch, which needs an event epoch; 2.18.0).  It applies only
# when the row carries both event_mjd and observation_mjd: the survey
# collectors do not set an observation epoch, so a catalogue SN match stays SN
# (2.22.0 review; ALGORITHM.md section 7 says so).
SN_MAX_DELTA_DAYS = 365.0


def classify(row):
    catalogs = _text(row, "catalogs") or ""
    if "Acker PN Spectroscopy" in catalogs:
        # The Strasbourg-ESO catalogue is itself a PN catalogue (Acker et al.
        # 1992): a counterpart is identity evidence, like HASH.  The old
        # ">= 2 positive lines" test only checked that data existed; the
        # ratios used against PN mimics (Frew & Parker 2010) are reported.
        detected, ratio = _pn_lines(row)
        assoc = _num(row, "association_confidence__acker_pn_spectroscopy")
        sii = sum(v for k, v in detected.items() if k.startswith("pn_sii"))
        ha = detected.get("pn_halpha")
        return _result(
            "PN",
            assoc,
            "PN_SPECTROSCOPY_EVIDENCE",
            [
                {
                    "kind": "pn_emission_line_spectrum",
                    "association_confidence": assoc,
                    "detected_lines": detected,
                    "oiii5007_to_halpha": ratio,
                    "sii_to_halpha": (sii / ha if sii and ha else None),
                    "note": "Acker et al. (1992) Strasbourg-ESO PN catalogue counterpart (identity evidence); [S II]/Ha and [O III]/Ha reported for mimic checks (Frew & Parker 2010).",
                }
            ],
        )
    if "HASH PN Catalog" in catalogs:
        assoc = _num(row, "association_confidence__hash_pn_catalog")
        status = _text(row, "pn_catalog_status")
        grade = _hash_grade(status)
        ev = [
            {
                "kind": "hash_pn_catalog_counterpart",
                "association_confidence": assoc,
                "pn_catalog_status": status,
                "hash_grade": grade,
                "note": "Independent counterpart in HASH; identity evidence, not a generic spectroscopic classifier.",
            }
        ]
        if grade == "NOT_PN":
            return _result("OTHER_PHENOMENON", assoc, "HASH_NON_PN_ENTRY", ev)
        if grade == "UNGRADED":
            return _result("UNKNOWN", None, "HASH_UNGRADED_ENTRY", ev)
        if grade == "POSSIBLE":
            return _result("PN", assoc, "HASH_POSSIBLE_PN", ev)
        return _result("PN", assoc, "HASH_PN_CATALOG_MATCH", ev)
    for cat, kind, status in (
        ("ASAS-SN Supernova Catalog", "asas_sn_supernova_event", "ASASSN_SUPERNOVA_EVENT_MATCH"),
        ("Asiago Supernova Catalog", "asiago_supernova_event", "ASIAGO_SUPERNOVA_EVENT_MATCH"),
    ):
        if cat in catalogs:
            assoc, ev = _event_evidence(row, cat, kind)
            if _sn_epoch_status(ev):
                return _result("OTHER_PHENOMENON", assoc, "SN_HOST_PAST_EVENT", [ev])
            return _result("SN", assoc, status, [ev])

    # Generic time-domain branch: only promote an explicit SN light-curve class
    # if an event epoch is present. This avoids treating a host detection as SN.
    # Offline hook: no collector writes transient_lightcurve_class / event_mjd
    # yet, so this branch fires only for inputs that provide them (2.23.0 review).
    lc = _text(row, "transient_lightcurve_class")
    event_mjd = _num(row, "event_mjd")
    if lc and lc.upper().startswith("SN") and event_mjd is not None:
        score = _num(row, "transient_lightcurve_score")
        return _result(
            "SN",
            score,
            "TIME_DOMAIN_SN_CANDIDATE",
            [
                {
                    "kind": "event_time_aware_lightcurve",
                    "class": lc,
                    "score": score,
                    "event_mjd": event_mjd,
                    "score_semantics": "raw time-domain classifier score; requires per-axis calibration",
                }
            ],
        )

    simbad = _text(row, "otype")
    _hit, code = OTYPES.resolve(simbad, SIMBAD_CURATED)  # hierarchy (2.22.0)
    code = code or simbad
    if code in SIMBAD_CURATED:
        label, status = SIMBAD_CURATED[code]
        return _result(label, None, status, [{"kind": "simbad_physical_type", "otype": code}])

    raw = _text(row, "best_class_name")
    score = _num(row, "best_class_score")
    evidence = (
        []
        if raw is None
        else [
            {
                "kind": "gaia_dr3_vari_classifier_result",
                "best_class_name": raw,
                "best_class_score": score,
                "score_semantics": "Gaia candidate score; raw evidence, not calibrated probability",
            }
        ]
    )
    if raw in GAIA_EVENTS:
        label, status = GAIA_EVENTS[raw]
        return _result(label, score, status, evidence)
    return _result("UNKNOWN", None, "NO_VALIDATED_PHENOMENON_EVIDENCE", evidence)
