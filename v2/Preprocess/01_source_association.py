#!/usr/bin/env python3
"""Stage 1: survey-aware, epoch-aware conservative counterpart association."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import pandas as pd

from association_model import (
    assess_pair,
    canonical_aliases,
    infer_entity_kind,
    infer_epoch,
    infer_poserr_arcsec,
    infer_psf_arcsec,
    sep_arcsec,
    num,
    profile_for,
)

AMBIG_SCORE_RATIO = 0.67
# DESI redshifts are measured at the imaging position of a Legacy Surveys
# target (TARGET_RA/DEC; Myers et al. 2023, AJ 165, 50), so a spectrum is a
# measurement of an LS source rather than an independent detection.  Spectra
# are associated after all imaging detections (they never anchor a group
# while their target is present), and a group holding an LS source within
# TARGET_MATCH_ARCSEC is their target, decisively, as a shared identifier
# would be (LS DR10 south re-numbers the DR9 objects DESI targeted).  Before
# 2.28.0 a shredded galaxy's own fragments made the spectrum ambiguous and it
# became an evidence-less object (fields RA 250 and RA 20).
TARGET_SPECTRA = ("DESI DR1 spectroscopy", "DESI DR1 FastSpecFit")
TARGET_IMAGING = "DESI Legacy Surveys DR10"
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
        if path.name.startswith(("collection_summary_", "ngc4522_")):
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
            if key in seen:
                skipped += 1
                continue
            seen.add(key)
            prof = profile_for(cat, r)
            rows.append(
                {
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
                    "source_row": int(i),
                }
            )
    return rows, skipped


def _anchor_key(det):
    # Prefer a PM-aware astrometric anchor, then smaller astrometric uncertainty.
    has_motion = det.get("pmra") is not None and det.get("pmdec") is not None and det.get("ref_epoch") is not None
    gaia = det.get("catalog") == "Gaia DR3"
    return (0 if gaia and has_motion else 1 if has_motion else 2, float(det.get("poserr_arcsec") or 99.0))


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


def run(raw_dir: Path, out: Path):
    detections, skipped = load(raw_dir)
    # Build groups from the best astrometric anchors first.  This prevents a
    # coarse IRAS/low-resolution row from becoming the coordinate anchor merely
    # because its filename sorts earlier.
    detections.sort(
        key=lambda d: (
            d.get("catalog") in TARGET_SPECTRA,
            *_anchor_key(d),
            str(d.get("catalog")),
            str(d.get("detection_id")),
        )
    )
    groups, records = [], []
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
                if det["catalog"] in group["catalogs"]:
                    # A second spectrum of a target already holding one is a
                    # duplicate, not evidence for a neighbour (field RA 20).
                    target_taken |= (
                        det["catalog"] in TARGET_SPECTRA
                        and TARGET_IMAGING in group["catalogs"]
                        and assess_pair(group["anchor"], det)["separation_arcsec"] <= TARGET_MATCH_ARCSEC
                    )
                    continue
                shared_aliases = set(det.get("association_aliases") or ()) & set(group.get("aliases") or ())
                if shared_aliases:
                    result = assess_pair(group["anchor"], det, det.get("source_density_arcsec2"))
                    result.update(
                        {
                            "accepted": True,
                            "association_score": 1.0,
                            "association_posterior": 1.0,
                            "association_method": "catalog_alias",
                            "shared_aliases": "|".join(sorted(shared_aliases)),
                        }
                    )
                    candidates.append((1.0, 0.0, gi, result))
                    continue
                density = det.get("source_density_arcsec2")
                result = assess_pair(group["anchor"], det, density)
                result["association_method"] = "position_epoch_likelihood"
                result["shared_aliases"] = ""
                if (
                    det["catalog"] in TARGET_SPECTRA
                    and TARGET_IMAGING in group["catalogs"]
                    and result["separation_arcsec"] <= TARGET_MATCH_ARCSEC
                ):
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
            candidates = [min(target_hits, key=lambda c: c[3]["separation_arcsec"])]
        elif det["catalog"] in TARGET_SPECTRA and target_taken:
            candidates = []
        ambiguous = len(candidates) > 1 and candidates[1][0] >= candidates[0][0] * AMBIG_SCORE_RATIO

        if candidates and not ambiguous:
            _, _, gi, match = candidates[0]
            group = groups[gi]
            oid = group["id"]
            group["catalogs"].add(det["catalog"])
            group["members"] += 1
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
                    "members": 1,
                    "entity_kind": det["entity_kind"],
                    "aliases": set(det.get("association_aliases") or ()),
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

        confidence = match.get("association_posterior", match.get("association_score"))
        records.append(
            {
                **{**det, "association_aliases": "|".join(sorted(det.get("association_aliases") or ()))},
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
            }
        )

    group_by_id = {g["id"]: g for g in groups}
    for rec, det in zip(records, detections):  # one record per detection, same order
        anchor = group_by_id[rec["object_id"]]["anchor"]
        # Membership confidence is judged against the object's final anchor
        # (its most precise position).  The score computed at match time used
        # whatever anchor the group had then (e.g. an offset NED position),
        # which left faint Legacy Surveys/DESI members with ~0 confidence.
        if rec["association_method"] == "position_epoch_likelihood" and anchor is not det:
            final = assess_pair(anchor, det, det.get("source_density_arcsec2"))
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
