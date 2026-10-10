"""Why an object stays UNKNOWN: a short, data-based explanation.

The coarse classifier abstains for four reasons (Preprocess/05 status):

* WITHIN_LARGE_GALAXY - inside a large galaxy's D26 ellipse, where survey
  detections are mostly pieces of that galaxy.
* NO_EVIDENCE - no rule could use the data. Typical cases are single-survey
  detections at or beyond the survey limit:
    - SDSS imaging: 95% completeness for point sources at r = 22.2
      (York et al. 2000; Stoughton et al. 2002);
    - Legacy Surveys: below S/N 10 the Tractor model choice is not used
      (Dey et al. 2019), see LS-MORPH-001/002;
    - Pan-STARRS1 MeanObject rows with no valid mean PSF magnitude (-999),
      typically objects with only one or two single-epoch detections
      (Flewelling et al. 2020).
* LOW_CONFIDENCE - the fused probabilities of two classes overlap.
* CONFLICT - strong evidence points at different classes.
"""

from __future__ import annotations
import json
import math
import sys
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import row_num as _num  # noqa: E402

LS_MORPH_SNR = 10.0  # LS-MORPH-001/002 threshold
SDSS_R_LIMIT = 22.2  # SDSS 95% point-source completeness (r)


def _ls_snr(row):
    out = []
    for b in ("r", "z"):
        f, iv = _num(row, f"desi_legacy_surveys_dr10__flux_{b}"), _num(row, f"desi_legacy_surveys_dr10__flux_ivar_{b}")
        if f is not None and iv is not None and iv > 0:
            out.append(f * math.sqrt(iv))
    return max(out) if out else None


def _single(row, cat):
    if cat == "Pan-STARRS1 DR2 MeanObject":
        valid = any(_num(row, f"std_mag__ps1_{b}") is not None for b in "grizy")
        n = _num(row, "pan_starrs1_dr2_meanobject__nDetections")
        if not valid:
            return "Pan-STARRS1 detection without valid mean photometry" + (
                f" ({int(n)} detections)" if n is not None else ""
            )
        bands = [b for b in "grizy" if _num(row, f"std_mag__ps1_{b}") is not None]
        i = _num(row, "std_mag__ps1_i")
        if len(bands) < 3:
            return (
                f"Pan-STARRS1 only, measured in {len(bands)} band{'s' if len(bands) != 1 else ''} ({''.join(bands)})"
                + (f", {int(n)} detections" if n is not None else "")
            )
        if i is None or not 14 <= i <= 21:
            return "Pan-STARRS1 only, i outside 14-21 (morphology not used); colours inconclusive"
        return "Pan-STARRS1 only; morphology and colours inconclusive"
    if cat == "SDSS DR18 PhotoObj":
        r = _num(row, "std_mag__sdss_r")
        if r is not None and r > SDSS_R_LIMIT:
            return f"SDSS only, r = {r:.1f} (beyond the r = {SDSS_R_LIMIT} completeness limit)"
        return "SDSS imaging only, no clean photometry"
    if cat == "DESI Legacy Surveys DR10":
        snr = _ls_snr(row)
        if snr is not None and snr < LS_MORPH_SNR:
            return f"Legacy Surveys only, S/N = {snr:.0f} (< {LS_MORPH_SNR:.0f}: morphology not used)"
        return "Legacy Surveys only; colours inconclusive"
    if cat in ("AllWISE", "GALEX AIS", "2MASS PSC"):
        return f"{cat} only: single-band-family detection, no optical counterpart"
    return f"only in {cat}"


def reason(row) -> str | None:
    if str(row.get("primary_class") or "UNKNOWN").upper() != "UNKNOWN":
        return None
    status = str(row.get("classification_status") or "")
    if status == "WITHIN_LARGE_GALAXY":
        return "inside a large galaxy: probably part of it"
    if status == "CONFLICT":
        try:
            ev = json.loads(row.get("evidence_json") or "[]")
        except (TypeError, ValueError):
            ev = []
        strong = sorted(
            {
                f"{e.get('class')} ({e.get('rule_id')})"
                for e in ev
                if float(e.get("score") or 0) >= 0.8 and e.get("class") in ("STAR", "GALAXY", "QSO")
            }
        )
        return "conflicting evidence: " + ", ".join(strong) if strong else "conflicting evidence"
    if status == "LOW_CONFIDENCE":
        p = {c: _num(row, f"p_{c.lower()}") for c in ("STAR", "GALAXY", "QSO")}
        p = {c: v for c, v in p.items() if v is not None}
        if len(p) >= 2:
            (a, pa), (b, pb) = sorted(p.items(), key=lambda kv: -kv[1])[:2]
            return f"{a} or {b}: probabilities overlap ({pa:.2f} vs {pb:.2f})"
        return "low confidence"
    cats = [c for c in str(row.get("catalogs") or "").split("|") if c and c not in ("SIMBAD", "NED")]
    if not cats:
        return "only literature databases (SIMBAD/NED), no survey measurement"
    if len(cats) == 1:
        return _single(row, cats[0])
    return "no usable classification data in " + ", ".join(cats)
