#!/usr/bin/env python3
"""Stage 1: survey-aware, epoch-aware conservative counterpart association."""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import pandas as pd

from association_model import (
    AMBIG_FIX,
    ANNOT_ASSOC,
    TYPED_ANNOTATIONS,
    annotation_physical_type,
    assess_pair,
    phot_magnitudes,
    phot_prior_enabled,
    phot_weight,
    canonical_aliases,
    infer_entity_kind,
    infer_epoch,
    infer_poserr_arcsec,
    infer_psf_arcsec,
    sep_arcsec,
    num,
    profile_for,
    tie_magnitude,
)

AMBIG_SCORE_RATIO = 0.67
TYPED_CLOSE_ARCSEC = float(os.environ.get("V2_ASSOC_TYPED_CLOSE_ARCSEC", "0.6"))
# Diagnostics of the decision (V2_ASSOC_DIAG=1; off by default, nothing else reads them): for every detection the best
# two accepted candidates (score, separation, normalised separation, catalogues and members of the group), and whether
# the groups of the two candidates are one object themselves (their anchors agree within the pair's sigma).
_DIAG = os.environ.get("V2_ASSOC_DIAG", "0") == "1"
# DESI redshifts are measured at the imaging position of a Legacy Surveys
# target (TARGET_RA/DEC; Myers et al. 2023, AJ 165, 50), so a spectrum is a
# measurement of an LS source rather than an independent detection.  Spectra
# are associated after all imaging detections (they never anchor a group
# while their target is present), and a group holding an LS source within
# TARGET_MATCH_ARCSEC is their target, decisively, as a shared identifier
# would be (LS DR10 south re-numbers the DR9 objects DESI targeted).  Before
# 2.28.0 a shredded galaxy's own fragments made the spectrum ambiguous and it
# became an evidence-less object (fields RA 250 and RA 20).
DESI_SPECTRA = ("DESI DR1 spectroscopy", "DESI DR1 FastSpecFit")
TARGET_SPECTRA = DESI_SPECTRA
TARGET_IMAGING = "DESI Legacy Surveys DR10"
# 2.61.7 (V2_ASSOC_AMBIG=spectra, off by default): LAMOST and SDSS spectra are targets as well.  LAMOST gives the coordinates of
# the input-catalogue source (Gaia, Pan-STARRS, SDSS, UCAC4; "Right ascension from input catalog", LAMOST DR10 catalogue table), so
# a LAMOST row is the measurement of an imaging source, not a detection of its own, like a DESI row.  For these spectra the
# target is the position of an imaging row of the group (any of IMAGING_TARGETS), not only a Legacy Surveys one: at low
# latitude 91 % of the quasars have no Legacy Surveys row.  SDSS spectra: the position is the SDSS target's; same treatment.
SPECTRA_EXTRA = ("LAMOST DR catalog", "SDSS DR18 spectroscopy")
IMAGING_TARGETS = ("DESI Legacy Surveys DR10", "Pan-STARRS1 DR2 MeanObject", "SDSS DR18 PhotoObj", "Gaia DR3")
if "spectra" in AMBIG_FIX:
    TARGET_SPECTRA = DESI_SPECTRA + SPECTRA_EXTRA
# 2.61.7 (V2_ASSOC_AMBIG=same / nearest): when the two best candidates of a detection are one object (their anchors lie within
# SAME_OBJECT_ARCSEC), or the nearest one is NEAREST_RATIO times nearer than the next and within NEAREST_SEP_ARCSEC, the detection
# joins instead of becoming a new object.  The values are set on the calibration fields (association_ambiguity/README.md).
SAME_OBJECT_ARCSEC = float(os.environ.get("V2_ASSOC_SAME_ARCSEC", "0.3"))
NEAREST_SEP_ARCSEC = float(os.environ.get("V2_ASSOC_NEAREST_SEP", "0.3"))
NEAREST_RATIO = float(os.environ.get("V2_ASSOC_NEAREST_RATIO", "3"))
# Literature annotation catalogues (2.47.0).  NED, SIMBAD and the compiled
# object catalogues give identifications of a source measured elsewhere, not
# detections of their own: NED holds separate entries for the optical, IR,
# X-ray and radio names of one star when it has not cross-identified them
# (Mazzarella et al. 2007, ASPC 382, 165), and SIMBAD coordinates are taken
# from the best published measurement (Wenger et al. 2000, A&AS 143, 9).
# The rule "one row per catalogue per object" therefore split one star into an
# identified photometric object plus evidence-less NED objects at the same
# position (reference-object validation, 2.46.2: 42 of 520 objects became
# UNKNOWN only because the nearest "object" was such a row).  Annotation rows
# are associated after every measurement (they never anchor a group), may
# join a group that already holds a row of their catalogue, and are given to
# the most probable candidate even when several are close.  Their membership
# confidence is then the normalised posterior of that candidate among all
# candidates (Budavari & Szalay 2008, ApJ 679, 301; Pineau et al. 2017,
# A&A 597, A89), which down-weights their evidence when the choice is unsure.
# Radio surveys (2.47.0).  An NVSS (45" beam) or TGSS (25") position often
# holds several optical sources within its error circle, so each radio row
# was "ambiguous" and became its own object: the NVSS and TGSS rows of one
# pulsar ended up apart and the 150 MHz - 1.4 GHz spectral index of the
# pulsar test (Frail et al. 2018) was never measured (reference objects:
# 0 of 10 pulsars).  Radio catalogues are cross-matched to each other by
# position, as in the TGSS-NVSS spectral-index work of de Gasperin, Intema
# & Frail (2018, MNRAS 474, 5008); an ambiguous radio row therefore joins the
# radio-only object among its candidates when there is exactly one.
RADIO_CATALOGS = frozenset({"NVSS", "TGSS ADR1", "VLASS", "FIRST", "LoTSS DR2"})
ANNOTATION_CATALOGS = frozenset(
    {
        "NED",
        "SIMBAD",
        "Roma-BZCAT",
        "Suh 2021 AGB Catalog",
        "HASH PN Catalog",
        "Acker PN Spectroscopy",
        "ATNF Pulsar Catalog",
        # Galaxy Zoo DESI: vote-fraction predictions for galaxies the Legacy
        # Surveys already detected (Walmsley et al. 2023), positions from LS DR8.
        "Galaxy Zoo DESI",
    }
)
TARGET_MATCH_ARCSEC = 0.3
# Spatial pre-selection.  Any accepted pair is within the larger profile cap
# (<= 45 arcsec) after proper-motion propagation; the index searches that cap
# plus PM_MARGIN_ARCSEC, and anchors that can move further than the margin
# over MAX_EPOCH_SPAN_YR are always checked, so results equal a full scan.
PM_MARGIN_ARCSEC = 10.0
MAX_EPOCH_SPAN_YR = 45.0
# 2.19.0: the grid cell used to be the largest cap of any detection (an NVSS
# 30" or IRAS 45" row made every query span ~165"), so dense fields cost
# O(n^2) assess_pair calls.  The index now uses a small cell; anchors whose
# own cap exceeds SMALL_CAP_ARCSEC are kept in an always-checked set (as
# fast movers are), and each detection searches its own cap, which keeps the
# result identical to a full scan.
SMALL_CAP_ARCSEC = 8.0


def _pm_shift_arcsec(det, span_yr):
    pmra, pmdec = det.get("pmra"), det.get("pmdec")
    if pmra is None or pmdec is None or det.get("ref_epoch") is None:
        return 0.0
    return math.hypot(pmra, pmdec) * span_yr / 1000.0


class _SkyIndex:
    """Uniform grid on unit-sphere Cartesian coordinates (no RA wrap/pole cases)."""

    def __init__(self, cell_arcsec: float):
        self.cell = math.radians(cell_arcsec / 3600.0)
        self.cells: dict[tuple[int, int, int], set[int]] = {}
        self.where: dict[int, tuple[int, int, int]] = {}

    def _key(self, ra, dec):
        r, d = math.radians(ra), math.radians(dec)
        x, y, z = math.cos(d) * math.cos(r), math.cos(d) * math.sin(r), math.sin(d)
        return (math.floor(x / self.cell), math.floor(y / self.cell), math.floor(z / self.cell))

    def put(self, gi, ra, dec):
        old = self.where.get(gi)
        if old is not None:
            self.cells[old].discard(gi)
        key = self._key(ra, dec)
        self.cells.setdefault(key, set()).add(gi)
        self.where[gi] = key

    def near(self, ra, dec, radius_arcsec):
        n = max(1, math.ceil(math.radians(radius_arcsec / 3600.0) / self.cell))
        kx, ky, kz = self._key(ra, dec)
        out = set()
        for i in range(kx - n, kx + n + 1):
            for j in range(ky - n, ky + n + 1):
                for k in range(kz - n, kz + n + 1):
                    out |= self.cells.get((i, j, k), set())
        return out


def _density(frame: pd.DataFrame) -> float | None:
    if len(frame) < 5:
        # A one/few-row targeted cone is not a reliable local-density estimator.
        return None
    radius = None
    for col in ("query_radius_arcmin", "cone_radius_arcmin"):
        if col in frame.columns:
            values = pd.to_numeric(frame[col], errors="coerce").dropna()
            if len(values):
                radius = float(values.median()) * 60.0
                break
    if radius is None or radius <= 0:
        # No recorded cone radius: use the rows' own footprint (distance of
        # the outermost source from the median position; cone searches are
        # circular, so this recovers the query radius to within a few %).
        ra = pd.to_numeric(frame.get("ra"), errors="coerce")
        dec = pd.to_numeric(frame.get("dec"), errors="coerce")
        ok = ra.notna() & dec.notna()
        if ok.sum() < 5:
            return None
        # Centre = mean unit vector, radius = largest great-circle distance:
        # a median RA and flat (dRA cos dec, dDec) offsets broke at RA 0/360
        # (density ~1e-12) and near the poles (2.23.0).
        import numpy as np

        a, d = np.radians(ra[ok].to_numpy(float)), np.radians(dec[ok].to_numpy(float))
        x, y, z = (np.cos(d) * np.cos(a)).mean(), (np.cos(d) * np.sin(a)).mean(), np.sin(d).mean()
        r0 = math.degrees(math.atan2(y, x)) % 360.0
        d0 = math.degrees(math.atan2(z, math.hypot(x, y)))
        radius = max(sep_arcsec(r0, d0, r, dd) for r, dd in zip(ra[ok], dec[ok]))
        if radius <= 0:
            return None
    return float(len(frame)) / (math.pi * radius * radius)


def load(raw: Path):
    rows, seen, skipped = [], set(), 0
    for path in sorted(raw.glob("*.csv")):
        # galaxy_clusters_*: cluster catalogue context for v2/clusters.py, not detections (2.32.0).
        if path.name.startswith(("collection_summary_", "ngc4522_", "galaxy_clusters_")):
            continue
        try:
            # Identifiers are text: 64-bit Gaia/PS1/SDSS IDs lose precision as float64.
            df = pd.read_csv(path, dtype={"catalog_object_id": "string", "catalog": "string"}, low_memory=False)
        except Exception:
            continue
        if not {"ra", "dec"}.issubset(df.columns):
            continue
        density = _density(df)
        for i, r in zip(df.index, df.to_dict("records")):  # plain dicts: iterrows built a Series per row
            ra, dec = num(r.get("ra")), num(r.get("dec"))
            if ra is None or dec is None:
                continue
            cat = r.get("catalog")
            cat = path.stem if pd.isna(cat) or not str(cat).strip() else str(cat)
            cid = r.get("catalog_object_id")
            cid = "" if pd.isna(cid) else str(cid).strip()
            key = (
                (cat, "id", cid)
                if cid and cid.lower() not in {"nan", "none"}
                else (cat, "sky", round(ra, 7), round(dec, 7))
            )
            prof = profile_for(cat, r)
            rows.append(
                {
                    "_dedup": key,  # private keys (leading underscore) are not written to source_association.csv
                    "_cid": cid,
                    "_tie_mag": tie_magnitude(cat, r),
                    "detection_id": f"{path.stem}:{i}",
                    "input_file": path.name,
                    "catalog": cat,
                    "catalog_object_id": cid or str(i),
                    "object_name": str(r.get("object_name", "")),
                    "ra": ra,
                    "dec": dec,
                    "poserr_arcsec": infer_poserr_arcsec(cat, r),
                    "psf_fwhm_arcsec": infer_psf_arcsec(cat, r),
                    "ref_epoch": infer_epoch(cat, r),
                    "entity_kind": infer_entity_kind(cat, r),
                    "pmra": num(r.get("pmra")),
                    "pmra_error": num(r.get("pmra_error")),
                    "pmdec": num(r.get("pmdec")),
                    "pmdec_error": num(r.get("pmdec_error")),
                    "max_radius_arcsec": prof.max_radius_arcsec,
                    "source_density_arcsec2": density,
                    "association_aliases": canonical_aliases(cat, r, cid),
                    "annotation_type": annotation_physical_type(cat, r),
                    "phot": phot_magnitudes(cat, r),
                    "source_row": int(i),
                }
            )
    # The row that is kept of two rows with the same identifier (or the same position when there is none) must not
    # depend on the order of the file: put the rows in the order of the association first (2.61.0)
    if _TIE_ORDER != "file":
        rows.sort(key=_order_key)
    kept = []
    for row in rows:
        if row["_dedup"] in seen:
            skipped += 1
            continue
        seen.add(row["_dedup"])
        kept.append(row)
    return kept, skipped


# Chance coincidence (2.48.0; V2_ASSOC_CANDIDATE_DENSITY=0 restores the old rule).  The
# probability that an unrelated source lies within the separation is set by
# the density of the sources the detection could be confused with, i.e. the
# candidate counterparts (the anchor's catalogue), not the detection's own
# catalogue: Budavari & Szalay 2008 (ApJ 679, 301) and NWAY (Salvato et al.
# 2018) put the counterpart catalogue's density in the prior.  With the
# detection's density a 6"-PSF AllWISE row is judged against the sparse WISE
# sky; shifted by 2' (NWAY's false-match test) 29-35 % of AllWISE rows still
# joined an unrelated object at high latitude, ~90 % in crowded fields
# (benchmark/experiments/assoc_phot_prior).  The larger of the two densities
# is used; on the same 26 fields this removed 14 % of the false AllWISE and
# 22 % of the false 2MASS associations with the truth accuracy unchanged
# (benchmark/experiments/assoc_density).
_CANDIDATE_DENSITY = os.environ.get("V2_ASSOC_CANDIDATE_DENSITY", "1") == "1"


# Acceptance at a target false-association rate (2.49.0; V2_ASSOC_MAX_NSEP=0
# switches it off): per catalogue, the largest normalised separation whose
# false-match rate in a shifted catalogue is <= 5 % (NWAY p_any calibration,
# Salvato et al. 2018; benchmark/calibrate_assoc_threshold.py on 80 set-B
# fields -> assoc_max_nsep.csv: AllWISE 1.75 sigma, 2MASS 2.5).  The membership
# posterior is not used: it saturates near 1 for AllWISE.  A/B on 89 fields
# (31,610 truth objects, 9 of them COSMOS deep fields): false AllWISE matches
# 20.9 -> 5.6 % (set B) and 22.4 -> 7.8 % (COSMOS, not used to calibrate),
# 2MASS 10.6 -> 4.9 %, truth +8 / -6 (benchmark/experiments/assoc_minp).
_MAX_NSEP = {}
if os.environ.get("V2_ASSOC_MAX_NSEP", "1") == "1":
    _f = Path(__file__).with_name("assoc_max_nsep.csv")
    if _f.exists():
        _MAX_NSEP = pd.read_csv(_f).set_index("catalog").max_nsep.astype(float).to_dict()


def _pair_density(det, anchor):
    own = det.get("source_density_arcsec2")
    if not _CANDIDATE_DENSITY:
        return own
    other = anchor.get("source_density_arcsec2")
    if "density" in ANNOT_ASSOC and det.get("catalog") in TYPED_ANNOTATIONS and anchor.get("catalog") not in ANNOTATION_CATALOGS and other is not None:
        # V2_ANNOT_ASSOC=density (2.62.4): a NED / SIMBAD row is looked for among survey objects, so only the survey objects can be the unrelated
        # neighbour it is confused with; the literature catalogue's own density (COSMOS 2': SIMBAD 0.067 / arcsec^2, four times the survey objects')
        # stops the pair at p_chance <= 0.25, i.e. at 1.1''.
        return other
    return max(d for d in (own, other) if d is not None) if (own is not None or other is not None) else None


def _target_sep(group, det):
    """Distance to the group's Legacy Surveys member(s), the imaging target of
    a DESI spectrum; the group anchor is often another survey's detection
    (field RA 20: anchor 0.71" away, LS target 0.02")."""
    targets = group["targets"] if det["catalog"] in DESI_SPECTRA else group.get("targets_imaging", ())
    return min((sep_arcsec(ra, dec, det["ra"], det["dec"]) for ra, dec in targets), default=math.inf)


def _typed_close(group, det):
    """V2_ANNOT_ASSOC=typed_close: the typed row ``det`` lies within TYPED_CLOSE_ARCSEC of EVERY typed row of its catalogue already in the group.

    The two entries of the catalogue are compared with each other, not with the group's anchor (Codex review of 2.62.4): the anchor is normally a survey
    row, so measuring from it merged two SIMBAD entries 0.5'' on either side of a survey position (1.0'' apart, outside the 0.6'' exception) and kept
    apart two duplicates both offset from it.  "Every" so that a chain of entries each 0.6'' from the last cannot stretch one object."""
    return all(sep_arcsec(ra, dec, det["ra"], det["dec"]) <= TYPED_CLOSE_ARCSEC for ra, dec in group["typed_annotations"][det["catalog"]])


def _anchor_key(det):
    # Prefer a PM-aware astrometric anchor, then smaller astrometric uncertainty.
    has_motion = det.get("pmra") is not None and det.get("pmdec") is not None and det.get("ref_epoch") is not None
    gaia = det.get("catalog") == "Gaia DR3"
    return (0 if gaia and has_motion else 1 if has_motion else 2, float(det.get("poserr_arcsec") or 99.0))


# Order of the detections (2.61.0).  The groups are built one detection at a time, the most precise anchors first, and
# a detection joins the group that is there when its turn comes; detections that agree on every key below are
# therefore decided by what comes last in the key.  Until 2.60.x that was the row of the input file, so the same
# detections in another order (a Legacy Surveys viewer answer against its TAP answer, a shuffled file) gave another
# set of objects: 1.1 % of the objects of the 26 deep COSMOS fields differ between two orders (WORK_REPORT_2026-11-25g.md).
# Many catalogues carry one assumed position error for every row (AllWISE, SDSS, GALEX, SGA, the 0.6'' floor of the
# resolved Legacy Surveys models: 63 % of the LS rows of a deep field), so the tie is the rule, not the exception.
# Now the last keys are the brightness (a brighter detection has the better centroid, the reason for the position error
# to rank the anchors; Fleuren et al. 2012, arXiv:1202.3891v2 eq. 7: sigma = 0.655 FWHM / SNR), then position, the catalogue's own identifier and
# only then the row.  The literature (Budavari & Basu 2016; Marrese et al. 2017, 2019) decides competing detections by
# score, not by order and gives no rule for the order; the brightness order is this project's choice (see
# LITERATURE_ASSOCIATION_ORDER_2026-11-25.md).  V2_ASSOC_TIE_ORDER=file restores the order of 2.60.x; =position drops the brightness
# (position, identifier, row) and is there to measure what the brightness adds.
_TIE_ORDER = os.environ.get("V2_ASSOC_TIE_ORDER", "brightness")
if _TIE_ORDER not in ("brightness", "position", "file"):
    raise ValueError(f"V2_ASSOC_TIE_ORDER={_TIE_ORDER!r}: expected 'brightness', 'position' or 'file'")


def _order_key(d):
    head = (d.get("catalog") in ANNOTATION_CATALOGS, d.get("catalog") in TARGET_SPECTRA, *_anchor_key(d), str(d.get("catalog")))
    if _TIE_ORDER == "file":
        return (*head, str(d.get("detection_id")))
    mag = d.get("_tie_mag") if _TIE_ORDER == "brightness" else None  # "position": the same without the brightness
    return (
        *head,
        mag if mag is not None else math.inf,
        d["ra"],
        d["dec"],
        str(d.get("_cid") or ""),
        str(d.get("detection_id")),
    )


EMPTY_COLUMNS = [
    "object_id",
    "catalog",
    "catalog_object_id",
    "ra",
    "dec",
    "input_file",
    "source_row",
    "association_status",
    "association_confidence",
    "object_ra",
    "object_dec",
]


def _diag_fields(candidates, groups) -> dict:
    """The first two accepted candidates of a detection as columns (V2_ASSOC_DIAG=1)."""
    out = {}
    for k, c in enumerate(candidates[:2], 1):
        score, nsep, gi, res = c
        g = groups[gi]
        out.update(
            {
                f"diag_c{k}_object": g["id"],
                f"diag_c{k}_score": score,
                f"diag_c{k}_sep": res.get("separation_arcsec"),
                f"diag_c{k}_nsep": res.get("normalized_separation"),
                f"diag_c{k}_sigma": res.get("combined_sigma_arcsec"),
                f"diag_c{k}_catalogs": "|".join(sorted(g["catalogs"])),
                f"diag_c{k}_members": g["members"],
            }
        )
    if candidates:  # every accepted candidate: object, separation, normalised separation, score ('|'-joined, best score first)
        out["diag_all_object"] = "|".join(groups[c[2]]["id"] for c in candidates)
        out["diag_all_sep"] = "|".join(f"{c[3].get('separation_arcsec') or 0.0:.4f}" for c in candidates)
        out["diag_all_nsep"] = "|".join(f"{c[3].get('normalized_separation') or 0.0:.3f}" for c in candidates)
        out["diag_all_score"] = "|".join(f"{c[0]:.4f}" for c in candidates)
    if len(candidates) > 1:
        a, b = groups[candidates[0][2]]["anchor"], groups[candidates[1][2]]["anchor"]
        pair = assess_pair(a, b, None)
        out["diag_c12_sep"] = pair["separation_arcsec"]
        out["diag_c12_nsep"] = pair["normalized_separation"]
    return out


def _resolve_ambiguity(candidates, groups):
    """V2_ASSOC_AMBIG ``best`` / ``same`` / ``nearest``: (still ambiguous, candidates, how it was resolved).

    best     never ambiguous: the best-scoring candidate is taken, as in Marrese et al. 2017, 2019 (the highest score among the
             good neighbours, no test against the second) and NWAY's match_flag 1 (a close second only gets match_flag 2).
    same     the anchors of the two best candidates are within SAME_OBJECT_ARCSEC: they are fragments of one object, so either
             is the right one; the best-scoring is taken.
    nearest  the nearest candidate is within NEAREST_SEP_ARCSEC and the next is NEAREST_RATIO times further: it is taken.
    """
    if "best" in AMBIG_FIX:
        return False, candidates, "best"
    if "same" in AMBIG_FIX:
        pair = assess_pair(groups[candidates[0][2]]["anchor"], groups[candidates[1][2]]["anchor"], None)
        if (pair["separation_arcsec"] or 0.0) < SAME_OBJECT_ARCSEC:
            return False, candidates, "same_object"
    if "nearest" in AMBIG_FIX:
        seps = [(c[3].get("separation_arcsec") or 0.0, k) for k, c in enumerate(candidates)]
        seps.sort()
        (s1, k1), (s2, _) = seps[0], seps[1]
        if s1 < NEAREST_SEP_ARCSEC and s2 >= NEAREST_RATIO * max(s1, 1e-3):
            return False, [candidates[k1]] + [c for k, c in enumerate(candidates) if k != k1], "nearest_clear"
    return True, candidates, ""


def run(raw_dir: Path, out: Path):
    detections, skipped = load(raw_dir)
    # Build groups from the best astrometric anchors first.  This prevents a
    # coarse IRAS/low-resolution row from becoming the coordinate anchor merely
    # because its filename sorts earlier.
    detections.sort(key=_order_key)
    groups, records = [], []
    use_phot = phot_prior_enabled()
    epochs = [float(d["ref_epoch"]) for d in detections if d.get("ref_epoch") is not None]
    # Epoch span from the data (a 1950 catalogue vs Gaia is 66 yr), at least
    # the historical 45 yr.
    span = max(MAX_EPOCH_SPAN_YR, (max(epochs) - min(epochs)) if epochs else 0.0)
    index = _SkyIndex(SMALL_CAP_ARCSEC + PM_MARGIN_ARCSEC)
    fast_movers: set[int] = set()
    wide: set[int] = set()
    alias_groups: dict[str, set[int]] = {}
    cap = lambda d: float(d.get("max_radius_arcsec") or 5.0)

    def place(gi):
        anchor = groups[gi]["anchor"]
        index.put(gi, anchor["ra"], anchor["dec"])
        if _pm_shift_arcsec(anchor, span) > PM_MARGIN_ARCSEC:
            fast_movers.add(gi)
        else:
            fast_movers.discard(gi)
        if cap(anchor) > SMALL_CAP_ARCSEC:
            wide.add(gi)
        else:
            wide.discard(gi)

    for det in detections:
        # Time-domain events remain distinct from persistent host/catalog objects.
        # Event identity can later be linked to a host in a dedicated event layer.
        candidates = []
        target_taken = False
        if det["entity_kind"] != "transient_event":
            # Accepted pairs lie within max(cap_anchor, cap_det) plus the PM
            # shifts: anchors with a cap above SMALL_CAP are in ``wide``.
            reach = max(cap(det), SMALL_CAP_ARCSEC) + PM_MARGIN_ARCSEC + _pm_shift_arcsec(det, span)
            nearby = index.near(det["ra"], det["dec"], reach)
            nearby |= fast_movers
            nearby |= wide
            for alias in det.get("association_aliases") or ():
                nearby |= alias_groups.get(alias, set())
            for gi in sorted(nearby):
                group = groups[gi]
                if group["entity_kind"] == "transient_event":
                    continue
                if det.get("annotation_type") and det["catalog"] in group["typed_annotations"]:
                    # Two entries of one annotation catalogue that both carry a
                    # physical type are two objects for that catalogue (a
                    # supernova and its host galaxy; association_model).
                    # V2_ANNOT_ASSOC=typed_close (2.62.4): not when the two entries' positions agree within TYPED_CLOSE_ARCSEC (0.6'': the
                    # radius COSMOS2020 uses for its ancillary catalogues, Weaver et al. 2022 sec. 2.6); a host and a supernova are farther apart.
                    if not ("typed_close" in ANNOT_ASSOC and _typed_close(group, det)):
                        continue
                if det["catalog"] in group["catalogs"] and det["catalog"] not in ANNOTATION_CATALOGS:
                    # A second spectrum of a target already holding one is a
                    # duplicate, not evidence for a neighbour (field RA 20).
                    target_taken |= det["catalog"] in TARGET_SPECTRA and _target_sep(group, det) <= TARGET_MATCH_ARCSEC
                    continue
                shared_aliases = set(det.get("association_aliases") or ()) & set(group.get("aliases") or ())
                if shared_aliases:
                    result = assess_pair(group["anchor"], det, det.get("source_density_arcsec2"))
                    result.update(
                        {
                            "accepted": True,
                            "association_score": 1.0,
                            "association_posterior": 1.0,
                            "likelihood_ratio": None,
                            "association_method": "catalog_alias",
                            "shared_aliases": "|".join(sorted(shared_aliases)),
                        }
                    )
                    candidates.append((1.0, 0.0, gi, result))
                    continue
                density = _pair_density(det, group["anchor"])
                result = assess_pair(group["anchor"], det, density)
                if use_phot and det["catalog"] in det.get("phot", {}):
                    w = phot_weight(det["catalog"], group.get("G"), det["phot"][det["catalog"]])
                    if w != 1.0:
                        # NWAY: the prior weight multiplies the positional Bayes factor.
                        result["association_score"] *= w
                        lik = result["positional_likelihood"] * w / (2.0 * math.pi * result["combined_sigma_arcsec"] ** 2)
                        result["association_posterior"] = lik / (lik + density) if density else min(1.0, result["positional_likelihood"] * w)
                        result["likelihood_ratio"] = lik / density if density else None
                        result["accepted"] = result["accepted"] and result["association_score"] >= 1e-5
                        result["phot_weight"] = w
                result["association_method"] = "position_epoch_likelihood"
                result["shared_aliases"] = ""
                if det["catalog"] in _MAX_NSEP and result["normalized_separation"] > _MAX_NSEP[det["catalog"]]:
                    result["accepted"] = False
                if det["catalog"] in TARGET_SPECTRA and _target_sep(group, det) <= TARGET_MATCH_ARCSEC:
                    result.update({"accepted": True, "association_method": "spectroscopic_target"})
                if result["accepted"]:
                    candidates.append((result["association_score"], result["normalized_separation"], gi, result))
            candidates.sort(key=lambda x: (-x[0], x[1]))

        # An exact shared identifier is decisive: positional neighbours (e.g.
        # catalogue duplicates in crowded fields) cannot make it ambiguous.
        alias_hits = [c for c in candidates if c[3].get("association_method") == "catalog_alias"]
        target_hits = [c for c in candidates if c[3].get("association_method") == "spectroscopic_target"]
        if len(alias_hits) == 1:
            candidates = alias_hits
        elif target_hits:
            candidates = [min(target_hits, key=lambda c: _target_sep(groups[c[2]], det))]
        elif det["catalog"] in TARGET_SPECTRA and target_taken:
            candidates = []
        ambiguous = len(candidates) > 1 and candidates[1][0] >= candidates[0][0] * AMBIG_SCORE_RATIO
        if ambiguous and det["catalog"] in RADIO_CATALOGS:
            radio = [c for c in candidates if groups[c[2]]["catalogs"] <= RADIO_CATALOGS]
            if len(radio) == 1:
                candidates = radio
                ambiguous = False
        if ambiguous and det["catalog"] in ANNOTATION_CATALOGS:
            total = sum(c[0] for c in candidates)
            best = dict(candidates[0][3])
            best["association_posterior"] = min(
                float(best.get("association_posterior", best.get("association_score", 1.0)) or 0.0),
                candidates[0][0] / total if total > 0 else 0.0,
            )
            best["association_method"] = "annotation_most_probable"
            candidates = [(candidates[0][0], candidates[0][1], candidates[0][2], best)] + candidates[1:]
            ambiguous = False
        resolution = ""
        if ambiguous and AMBIG_FIX:
            ambiguous, candidates, resolution = _resolve_ambiguity(candidates, groups)

        if candidates and not ambiguous:
            _, _, gi, match = candidates[0]
            group = groups[gi]
            oid = group["id"]
            group["catalogs"].add(det["catalog"])
            if group.get("G") is None and "G" in (det.get("phot") or {}):
                group["G"] = det["phot"]["G"]
            if det.get("annotation_type"):
                group["typed_annotations"].setdefault(det["catalog"], []).append((det["ra"], det["dec"]))
            group["members"] += 1
            if det["catalog"] == TARGET_IMAGING:
                group["targets"].append((det["ra"], det["dec"]))
            if "spectra" in AMBIG_FIX and det["catalog"] in IMAGING_TARGETS:
                group["targets_imaging"].append((det["ra"], det["dec"]))
            group["aliases"].update(det.get("association_aliases") or ())
            for alias in det.get("association_aliases") or ():
                alias_groups.setdefault(alias, set()).add(gi)
            if _anchor_key(det) < _anchor_key(group["anchor"]):
                group["anchor"] = det
                place(gi)
            status = "matched"
        else:
            oid = f"OBJ{len(groups)+1:06d}"
            groups.append(
                {
                    "id": oid,
                    "anchor": det,
                    "catalogs": {det["catalog"]},
                    "typed_annotations": {det["catalog"]: [(det["ra"], det["dec"])]} if det.get("annotation_type") else {},  # catalogue -> positions of its typed rows
                    "G": (det.get("phot") or {}).get("G"),
                    "members": 1,
                    "entity_kind": det["entity_kind"],
                    "aliases": set(det.get("association_aliases") or ()),
                    "targets": [(det["ra"], det["dec"])] if det["catalog"] == TARGET_IMAGING else [],
                    "targets_imaging": [(det["ra"], det["dec"])] if det["catalog"] in IMAGING_TARGETS else [],
                }
            )
            place(len(groups) - 1)
            for alias in det.get("association_aliases") or ():
                alias_groups.setdefault(alias, set()).add(len(groups) - 1)
            if candidates:
                # Keep the best competing candidate's diagnostics, but the
                # detection anchors its own object, so its own catalog evidence
                # is fully its own; the ambiguity is recorded in the status.
                # (association_posterior too: the confidence read below prefers it,
                # so the competitor's posterior used to down-weight the
                # detection's own evidence; fixed 2.19.0.)
                match = {
                    **candidates[0][3],
                    "association_score": 1.0,
                    "association_posterior": 1.0,
                    "association_method": "new_source_ambiguous",
                }
            else:
                match = {
                    "separation_arcsec": None,
                    "comparison_epoch": None,
                    "proper_motion_propagated": False,
                    "propagation_direction": "none",
                    "combined_sigma_arcsec": None,
                    "match_radius_arcsec": None,
                    "normalized_separation": None,
                    "positional_likelihood": None,
                    "chance_probability": None,
                    "association_score": 1.0,
                    "association_method": "new_source",
                    "shared_aliases": "",
                }
            status = (
                "ambiguous_new" if ambiguous else ("event_new" if det["entity_kind"] == "transient_event" else "new")
            )

        diag = _diag_fields(candidates, groups) if _DIAG else {}
        if AMBIG_FIX:  # how an ambiguity was resolved ('' = it was none or stayed one); only with a V2_ASSOC_AMBIG switch
            diag["ambiguity_resolution"] = resolution
        # Sum of the likelihood ratios of every accepted candidate (Fleuren et al. 2012 denominator); the posterior
        # measurements read it, nothing else does.  A candidate without a ratio (shared identifier) counts as 0.
        lr_sum = sum(float(c[3].get("likelihood_ratio") or 0.0) for c in candidates)
        confidence = match.get("association_posterior", match.get("association_score"))
        records.append(
            {
                **{k: v for k, v in det.items() if k != "phot" and not k.startswith("_")},
                "association_aliases": "|".join(sorted(det.get("association_aliases") or ())),
                "object_id": oid,
                "association_status": status,
                "match_separation_arcsec": match.get("separation_arcsec"),
                "comparison_epoch": match.get("comparison_epoch"),
                "proper_motion_propagated": bool(match.get("proper_motion_propagated")),
                "propagation_direction": match.get("propagation_direction"),
                "combined_sigma_arcsec": match.get("combined_sigma_arcsec"),
                "match_radius_arcsec": match.get("match_radius_arcsec"),
                "normalized_separation": match.get("normalized_separation"),
                "positional_likelihood": match.get("positional_likelihood"),
                "chance_probability": match.get("chance_probability"),
                "association_confidence": confidence,
                "association_probability_calibrated": False,
                "association_method": match.get("association_method", "position_epoch_likelihood"),
                "shared_aliases": match.get("shared_aliases", ""),
                "candidate_count": len(candidates),
                "likelihood_ratio": match.get("likelihood_ratio") if status == "matched" else None,
                "lr_sum_candidates": lr_sum,
                "phot_weight": match.get("phot_weight", 1.0),
                **diag,
            }
        )

    group_by_id = {g["id"]: g for g in groups}
    for rec, det in zip(records, detections):  # one record per detection, same order
        anchor = group_by_id[rec["object_id"]]["anchor"]
        # Membership confidence is judged against the object's final anchor
        # (its most precise position).  The score computed at match time used
        # whatever anchor the group had then (e.g. an offset NED position),
        # which left faint Legacy Surveys/DESI members with ~0 confidence.
        if rec["association_method"] == "position_epoch_likelihood" and anchor is not det and rec["phot_weight"] >= 1.0:
            final = assess_pair(anchor, det, _pair_density(det, anchor))
            rec["association_confidence"] = max(rec["association_confidence"] or 0.0, final["association_posterior"])
            rec["final_anchor_separation_arcsec"] = final["separation_arcsec"]
        rec["object_ra"] = anchor["ra"]
        rec["object_dec"] = anchor["dec"]
        rec["object_ref_epoch"] = anchor.get("ref_epoch")
        rec["object_anchor_catalog"] = anchor.get("catalog")
        rec["object_entity_kind"] = group_by_id[rec["object_id"]]["entity_kind"]

    out.parent.mkdir(parents=True, exist_ok=True)
    # An empty field still gets a header, so later stages read 0 rows
    # instead of failing on a file without columns.
    pd.DataFrame(records, columns=None if records else EMPTY_COLUMNS).to_csv(out, index=False)
    print(f"[OK] detections={len(records)} deduplicated={skipped} groups={len(groups)} -> {out}")
    return out


def main():
    root = Path(__file__).resolve().parent
    p = argparse.ArgumentParser()
    p.add_argument("--raw-dir", type=Path, default=root.parent / "rawdata")
    p.add_argument("--out", type=Path, default=root / "source_association.csv")
    a = p.parse_args()
    run(a.raw_dir, a.out)


if __name__ == "__main__":
    main()
