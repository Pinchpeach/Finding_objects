"""'From paper' classifications: what the literature says about an object.

The catalogue-based classifier abstains (UNKNOWN) when the survey data do not
decide the class. Many such objects have nevertheless been classified in
papers. This module collects that information without letting it change
the pipeline's own class:

* SIMBAD object type (assigned by SIMBAD curators from the literature;
  Wenger et al. 2000) with the papers that discuss the object most
  (``Get_data/simbad.py``: has_ref.obj_freq, then most recent).
* Paper catalogues the pipeline cross-matches, each the product of one
  publication (AGB stars, planetary nebulae, pulsars, supernovae).
* NED preferred object type and its number of references.

Output per object: ``paper_class`` (readable class), ``paper_source``
(where it comes from), ``paper_refs`` (bibcode (year) title; '|'
separated), ``paper_ads`` (ADS links). Objects whose own class is UNKNOWN
show ``from paper: <class>`` as their sub-class, with the status
``FROM_PAPER``; their primary class stays UNKNOWN.
"""

from __future__ import annotations
import sys
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import row_num as _num, text as _text  # noqa: E402

# Paper catalogues used as cross-match sources (ADS bibcodes).
PAPER_CATALOGS = {
    "Suh 2021 AGB Catalog": ("AGB star", "2021ApJS..256...43S", "Suh 2021, ApJS 256, 43"),
    "HASH PN Catalog": ("Planetary nebula", "2016JPhCS.728c2008P", "Parker, Bojicic & Frew 2016 (HASH)"),
    "ATNF Pulsar Catalog": ("Pulsar", "2005AJ....129.1993M", "Manchester et al. 2005, AJ 129, 1993"),
    "Asiago Supernova Catalog": ("Supernova", "1999A&AS..139..531B", "Barbon et al. 1999, A&AS 139, 531"),
    "ASAS-SN Supernova Catalog": ("Supernova", "2017MNRAS.464.2672H", "Holoien et al. 2017, MNRAS 464, 2672"),
}

# Readable SIMBAD types when the collector could not fetch SIMBAD's own
# otypedef descriptions (common types only; others are shown as the code).
SIMBAD_LABEL = {
    "G": "Galaxy",
    "GiG": "Galaxy in a group",
    "GiC": "Galaxy in a cluster",
    "GiP": "Galaxy in a pair",
    "BiC": "Brightest galaxy in a cluster",
    "IG": "Interacting galaxies",
    "PaG": "Pair of galaxies",
    "LSB": "Low surface brightness galaxy",
    "EmG": "Emission-line galaxy",
    "SBG": "Starburst galaxy",
    "H2G": "HII galaxy",
    "bCG": "Blue compact galaxy",
    "AGN": "Active galactic nucleus",
    "SyG": "Seyfert galaxy",
    "Sy1": "Seyfert 1 galaxy",
    "Sy2": "Seyfert 2 galaxy",
    "LIN": "LINER galaxy",
    "QSO": "Quasar",
    "BLL": "BL Lac object",
    "Bla": "Blazar",
    "rG": "Radio galaxy",
    "ClG": "Cluster of galaxies",
    "GrG": "Group of galaxies",
    "*": "Star",
    "Star": "Star",
    "WD*": "White dwarf",
    "PM*": "High proper-motion star",
    "EB*": "Eclipsing binary",
    "RR*": "RR Lyrae variable",
    "V*": "Variable star",
    "LP*": "Long-period variable",
    "YSO": "Young stellar object",
    "BD*": "Brown dwarf",
    "C*": "Carbon star",
    "AGB*": "AGB star",
    "PN": "Planetary nebula",
    "SN*": "Supernova",
    "Psr": "Pulsar",
    "XB*": "X-ray binary",
    "CV*": "Cataclysmic variable",
    "IR": "Infrared source",
    "X": "X-ray source",
    "Rad": "Radio source",
    "UV": "UV-emission source",
    "mR": "Metric radio source",
    "cm": "Centimetric radio source",
    "smm": "Sub-millimetric source",
    "Opt": "Optical source",
    "?": "Object of unknown nature",
    "Unknown": "Object of unknown nature",
}
NED_LABEL = {
    "G": "Galaxy",
    "QSO": "Quasar",
    "*": "Star (point source)",
    "GPair": "Galaxy pair",
    "GTrpl": "Galaxy triple",
    "GGroup": "Group of galaxies",
    "GClstr": "Cluster of galaxies",
    "IrS": "Infrared source",
    "RadioS": "Radio source",
    "UvS": "UV source",
    "XrayS": "X-ray source",
    "VisS": "Visual source",
    "Neb": "Nebula",
    "PN": "Planetary nebula",
    "SN": "Supernova",
    "HII": "HII region",
    "WD*": "White dwarf",
    "PofG": "Part of a galaxy",
    "GClstr": "Cluster of galaxies",
    "SNR": "Supernova remnant",
    "Nova": "Nova",
    "**": "Double star",
    "*Ass": "Stellar association",
    "*Cl": "Star cluster",
    "EmLS": "Emission-line source",
    "EmObj": "Emission object",
    "Blue*": "Blue star",
    "C*": "Carbon star",
    "V*": "Variable star",
    "!*": "Galactic star",
    "Other": "Other object",
    "G_Lens": "Lensed image of a galaxy",
    "Q_Lens": "Lensed image of a quasar",
    "AbLS": "Absorption-line system",
    "MCld": "Molecular cloud",
    "RfN": "Reflection nebula",
    "UvES": "UV excess source",
    "QGroup": "Group of quasars",
    "Q": "Quasar",
}
# Types that only say in which band something was detected: they are kept
# but marked, because they do not say what the object is.
DETECTION_ONLY = {
    "IR",
    "X",
    "Rad",
    "UV",
    "mR",
    "cm",
    "smm",
    "Opt",
    "?",
    "Unknown",
    "IrS",
    "RadioS",
    "UvS",
    "XrayS",
    "VisS",
}


def ads(bibcode: str) -> str:
    return f"https://ui.adsabs.harvard.edu/abs/{bibcode}"


def from_paper(row) -> dict | None:
    """The literature classification of one object, or None."""
    cats = set(str(row.get("catalogs") or "").split("|"))
    for cat, (cls, bib, cite) in PAPER_CATALOGS.items():
        if cat in cats:
            return {
                "paper_class": cls,
                "paper_source": f"{cat} ({cite})",
                "paper_refs": f"{bib} ({cite})",
                "paper_ads": ads(bib),
                "detection_only": False,
            }
    ot = _text(row, "simbad__otype")
    if ot:
        label = _text(row, "simbad__simbad_otype_label") or SIMBAD_LABEL.get(ot, ot)
        bibs = (_text(row, "simbad__simbad_ref_bibcodes") or "").split("|")
        titles = (_text(row, "simbad__simbad_ref_titles") or "").split("|")
        years = (_text(row, "simbad__simbad_ref_years") or "").split("|")
        refs = [f"{b} ({y}) {t}".strip() for b, y, t in zip(bibs, years + [""] * 3, titles + [""] * 3) if b]
        n = _num(row, "simbad__simbad_nbref")
        src = f"SIMBAD {_text(row, 'simbad__main_id') or ''} (otype {ot}" + (f", {int(n)} papers)" if n else ")")
        return {
            "paper_class": label,
            "paper_source": src,
            "paper_refs": "|".join(refs) or None,
            "paper_ads": "|".join(ads(b) for b in bibs if b) or None,
            "detection_only": ot in DETECTION_ONLY,
        }
    nt = _text(row, "ned__Type")
    if nt:
        n = _num(row, "ned__References")
        return {
            "paper_class": NED_LABEL.get(nt, nt),
            "paper_source": f"NED {_text(row, 'ned__Object Name') or ''} (type {nt}"
            + (f", {int(n)} references)" if n else ")"),
            "paper_refs": None,
            "paper_ads": None,
            "detection_only": nt in DETECTION_ONLY,
        }
    return None
