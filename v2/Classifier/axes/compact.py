"""Compact-object axis with conservative catalog evidence."""

from __future__ import annotations
import math
import importlib.util as _ilu
from pathlib import Path as _P

_s = _ilu.spec_from_file_location("v2_simbad_otypes", _P(__file__).resolve().parents[1] / "simbad_otypes.py")
OTYPES = _ilu.module_from_spec(_s)
_s.loader.exec_module(OTYPES)
AXIS = "compact"
CLASSES = ("NS", "PULSAR", "PULSAR_CANDIDATE", "XRB", "COMPACT_COMPANION_CANDIDATE", "OTHER_COMPACT", "UNKNOWN")
# Radio pulsar candidate without the ATNF catalogue (2.6.3; revised 2.10.0).
# Pulsars have steep spectra (alpha ~ -1.6; Jankowski et al. 2018, Bates et
# al. 2013) and are compact.  Selection (Frail et al. 2018): TGSS 150 MHz -
# NVSS 1.4 GHz alpha <= -1.5 with TGSS S_total / S_peak <= 1.5.  Linear
# polarisation (Han & Tian 1999) is recorded as supporting evidence only when
# it is significant (P / sigma_P >= 3) and > 5 %: for the typical 3-7 mJy
# candidate the NVSS polarisation error (~0.3 mJy) makes a 5 % cut a 1-sigma
# test.  Measured with one row per NVSS source (benchmark/evaluate_pulsar.py;
# ATNF only as label, all quantities around the NVSS position): alpha +
# compactness 25/116 pulsar sources (21.6 %), 3/2531 ordinary sources
# (0.12 %); adding "fpol > 5 %" kept the same 3 false positives and lost 9
# pulsars; significant polarisation alone is 7/116 with 0/2531.
PSR_ALPHA_MAX = -1.5
PSR_COMPACT_MAX = 1.5
PSR_POL_MIN = 0.05
PSR_POL_SNR = 3.0
# Purity (2.14.0): the candidate's confidence is a sky-level posterior from
# naive Bayes with likelihood ratios measured per NVSS source
# (benchmark/evaluate_pulsar.py): prior = known pulsar sources among all NVSS
# sources (116 / 1.77 M); steep + compact LR = 0.216 / (4/2533) (Laplace);
# Galactic plane |b| < 10 deg: 0.621 / 0.099 (off-plane 0.379 / 0.901);
# significant polarisation: 0.241 / 0.0332 (absent 0.759 / 0.9668) -- rates
# over all sources (pulsars 28/116, controls 84/2531), not within the steep +
# compact candidates, so the factors are combined assuming independence.
# Normal pulsars concentrate to the plane (scale height 330 pc; Lorimer et
# al. 2006, MNRAS 372, 777); millisecond pulsars are nearly isotropic, so the
# plane factor under-rates them.
PSR_PRIOR_ODDS = 116 / 1.77e6
PSR_LR_RULE = 0.216 / (4 / 2533)
PSR_LR_PLANE = (0.621 / 0.099, 0.379 / 0.901)
PSR_LR_POL = (0.241 / 0.0332, 0.759 / 0.9668)
PSR_PLANE_B = 10.0


def _galactic_b(ra, dec):
    ra, dec = math.radians(ra), math.radians(dec)
    dg, ag = math.radians(27.12825), math.radians(192.85948)
    return math.degrees(math.asin(math.sin(dec) * math.sin(dg) + math.cos(dec) * math.cos(dg) * math.cos(ra - ag)))


def pulsar_posterior(row, ev):
    odds = PSR_PRIOR_ODDS * PSR_LR_RULE
    odds *= PSR_LR_POL[0] if ev.get("significantly_polarised") else PSR_LR_POL[1]
    ra, dec = _num(row, "ra"), _num(row, "dec")
    if ra is not None and dec is not None:
        b = _galactic_b(ra, dec)
        ev["galactic_b"] = round(b, 2)
        odds *= PSR_LR_PLANE[0] if abs(b) < PSR_PLANE_B else PSR_LR_PLANE[1]
    return round(odds / (1 + odds), 4)


def radio_pulsar_evidence(row):
    s14 = _num(row, "nvss__S1.4")
    s150 = _num(row, "tgss_adr1__Stotal")
    peak = _num(row, "tgss_adr1__Speak")
    if None in (s14, s150, peak) or s14 <= 0 or s150 <= 0 or peak <= 0:
        return None
    alpha = math.log10(s150 / s14) / math.log10(150 / 1400)
    compact = s150 / peak
    if not (alpha <= PSR_ALPHA_MAX and compact <= PSR_COMPACT_MAX):
        return None
    pol = _num(row, "nvss__polFlux")
    epol = _num(row, "nvss__e_polFlux")
    polarised = (
        pol is not None and epol is not None and epol > 0 and pol / epol >= PSR_POL_SNR and pol / s14 > PSR_POL_MIN
    )
    ev = {
        "kind": "radio_steep_compact",
        "alpha_150_1400": round(alpha, 3),
        "compactness_150": round(compact, 3),
        "significantly_polarised": bool(polarised),
    }
    if pol is not None:
        ev["nvss_fractional_pol"] = round(pol / s14, 3)
    return ev


def _bool(row, key):
    v = row.get(key)
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "1.0", "true", "t", "yes"}


def _text(row, key):
    v = row.get(key)
    if v is None:
        return None
    v = str(v).strip()
    return None if not v or v.lower() == "nan" else v


def _num(row, key):
    try:
        v = float(row.get(key))
        return v if math.isfinite(v) else None
    except Exception:
        return None


def classify(row):
    catalogs = _text(row, "catalogs") or ""
    if "ATNF Pulsar Catalog" in catalogs:
        assoc = _num(row, "association_confidence__atnf_pulsar_catalog")
        return {
            "axis": AXIS,
            "label": "PULSAR",
            "confidence": assoc,
            "status": "ATNF_CATALOG_MATCH",
            "evidence": [
                {
                    "kind": "atnf_pulsar_catalog_counterpart",
                    "association_confidence": assoc,
                    "score_semantics": "raw association score; not calibrated posterior",
                }
            ],
        }
    simbad = _text(row, "otype")
    hit, _c = OTYPES.resolve(simbad, {"Psr": "PULSAR", "N*": "NS", "XB*": "XRB"})  # hierarchy (2.22.0)
    if hit == "NS":
        return {
            "axis": AXIS,
            "label": "NS",
            "confidence": None,
            "status": "SIMBAD_CURATED_NS",
            "evidence": [{"kind": "simbad_physical_type", "otype": simbad}],
        }
    if hit == "PULSAR":
        return {
            "axis": AXIS,
            "label": "PULSAR",
            "confidence": None,
            "status": "SIMBAD_CURATED_PULSAR",
            "evidence": [{"kind": "simbad_physical_type", "otype": simbad}],
        }
    if hit == "XRB":
        return {
            "axis": AXIS,
            "label": "XRB",
            "confidence": None,
            "status": "SIMBAD_CURATED_XRB",
            "evidence": [{"kind": "simbad_physical_type", "otype": simbad}],
        }
    psr = radio_pulsar_evidence(row)
    if psr is not None:
        return {
            "axis": AXIS,
            "label": "PULSAR_CANDIDATE",
            "confidence": pulsar_posterior(row, psr),
            "status": "RADIO_STEEP_COMPACT_POLARISED" if psr["significantly_polarised"] else "RADIO_STEEP_COMPACT",
            "evidence": [psr],
        }
    if _bool(row, "in_vari_compact_companion"):
        return {
            "axis": AXIS,
            "label": "COMPACT_COMPANION_CANDIDATE",
            "confidence": None,
            "status": "GAIA_DR3_COMPACT_COMPANION_CANDIDATE",
            "evidence": [{"kind": "gaia_dr3_vari_summary", "in_vari_compact_companion": True}],
        }
    return {
        "axis": AXIS,
        "label": "UNKNOWN",
        "confidence": None,
        "status": "NO_VALIDATED_COMPACT_EVIDENCE",
        "evidence": [],
    }
