"""Conservative QSO/AGN refinement."""

from __future__ import annotations
import math

# Survey membership comes from Stage-2 ``catalogs`` (an associated counterpart),
# not from column-name prefixes, which also match unrelated fields.
RADIO_CATALOGS = ("FIRST", "NVSS", "LoTSS DR2", "VLASS")
XRAY_CATALOGS = ("Chandra CSC 2.0", "XMM 4XMM-DR13", "eROSITA eRASS1")


def _catalogs(row):
    v = row.get("catalogs")
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return set()
    return {x for x in str(v).split("|") if x}


def _positive(row, key):
    try:
        x = float(row.get(key))
        return math.isfinite(x) and x > 0
    except Exception:
        return False


def classify(row):
    cats = _catalogs(row)
    # rx_* fields come from benchmark tables that carry matched fluxes directly.
    radio = (
        bool(cats.intersection(RADIO_CATALOGS)) or _positive(row, "rx_radio_peak") or _positive(row, "rx_radio_integr")
    )
    xray = bool(cats.intersection(XRAY_CATALOGS)) or any(
        _positive(row, k) for k in row.keys() if str(k).startswith(("rx_chandra_", "rx_xmm_", "rx_erosita_"))
    )
    return {
        "detailed_class": "UNRESOLVED",
        "confidence": None,
        "radio_detected": radio,
        "xray_detected": xray,
        "basis": "QSO routed; radio-loudness/subtype requires dedicated validated definition/model",
    }
