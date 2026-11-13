"""Where a classification comes from: catalogue lookup, another survey's
classifier, or our own inference from measurements (2.51.0).

The scientific review of 2026-11-11 (SCIENTIFIC_REVIEW_2026-11-11.md, 2.8 and
7.2) found that most sub-class and axis labels are copied from SIMBAD, Gaia
or dedicated catalogues, so their accuracy is that of the source catalogue,
not of this pipeline.  Every decision now carries one of

  CATALOG              copied from a literature / spectroscopic catalogue
                       (SIMBAD, NED, HASH, ATNF, Roma-BZCAT, Suh 2021, SN
                       catalogues, SGA, SDSS / LAMOST / DESI spectral classes)
  EXTERNAL_CLASSIFIER  the output of another survey's classifier (Gaia DR3
                       variability / SOS / ESP / DSC-based candidate tables,
                       the ZTF periodic-variable catalogue, Galaxy Zoo DESI)
  INFERRED             our rule applied to measurements (Gaia HR regions,
                       colour selections, radio spectral index, WISE colours,
                       emission-line diagnostics on measured line fluxes,
                       the coarse-class fusion of photometry and astrometry)
  NONE                 no decision (UNKNOWN / no evidence / routed elsewhere)

so that results and validation can be split by provenance
(benchmark/score_by_provenance.py): only INFERRED decisions measure what the
pipeline itself infers.
"""

from __future__ import annotations

import json

CATALOG_PREFIXES = (
    "SIMBAD",
    "NED",
    "HASH_",
    "ATNF",
    "ROMA_BZCAT",
    "SUH2021",
    "ASASSN_SUPERNOVA",
    "ASIAGO_SUPERNOVA",
    "SN_HOST_PAST_EVENT",
    "PN_SPECTROSCOPY",
    "SDSS_SUBCLASS",
    "LAMOST_SUBCLASS",
    "DESI_SUBCLASS",
    "SDSS_BROADLINE",
    "FROM_PAPER",
    "SPEC_Z",
    "SGA",
)
EXTERNAL_PREFIXES = (
    "GAIA_DR3_",  # Gaia DR3 vari classifier, SOS tables, ESP-UCD, candidate tables
    "ZTF_PERIODIC",
    "GZ_DESI",
    "GAIA_LPV_CSTAR",
    "GAIA_ESP_ELS",
    "ESP_UCD",
)
NONE_PREFIXES = ("NO_", "INSUFFICIENT", "NOT_", "ROUTED", "UNMAPPED", "NON_STELLAR", "STAR_LIKE_NO", "UNKNOWN", "NOT_ROUTED")
# Stage-4 evidence that is a catalogue label (classification_rules.csv kind
# catalog_label): spectroscopic classes and literature types.
CATALOG_EVIDENCE = ("SPC-", "SIMBAD-TYPE", "NED-TYPE", "SGA-")
GROUPS = {"EXTRAGALACTIC": {"GALAXY", "QSO"}, "POINT_SOURCE": {"STAR", "QSO"}}


def of_rule(rule) -> str:
    """Provenance of an axis status or a sub-class rule id."""
    r = str(rule or "").strip().upper()
    if not r or r in {"NAN", "NONE"}:
        return "NONE"
    if r.startswith(NONE_PREFIXES):
        return "NONE"
    if r.startswith(CATALOG_PREFIXES) or r.endswith("_SUBCLASS"):
        return "CATALOG"
    if r.startswith(EXTERNAL_PREFIXES):
        return "EXTERNAL_CLASSIFIER"
    return "INFERRED"


def of_primary(label, evidence_json) -> str:
    """CATALOG when a spectroscopic / literature label supports the final
    coarse class, else INFERRED (fusion of measurements); NONE for UNKNOWN."""
    lab = str(label or "").upper()
    if lab not in {"STAR", "GALAXY", "QSO"}:
        return "NONE"
    try:
        ev = json.loads(evidence_json) if isinstance(evidence_json, str) else []
    except (TypeError, ValueError):
        ev = []
    for e in ev or []:
        rid = str(e.get("rule_id", ""))
        cls = str(e.get("class", ""))
        if rid.startswith(CATALOG_EVIDENCE) and (cls == lab or lab in GROUPS.get(cls, ())):
            try:
                if float(e.get("score", 0)) >= 0.5:
                    return "CATALOG"
            except (TypeError, ValueError):
                continue
    return "INFERRED"
