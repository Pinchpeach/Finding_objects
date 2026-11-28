"""The anchor-independent reading of an association (2.62.7 review, Codex): ``right_object`` = correct + alone_identified.

``measure_association.measure_field`` counts a row that is not joined and whose counterpart no OTHER object holds as ``rightly_alone``, also when its own object
holds no truth id either.  The same row joined to an object without truth id is ``unknown``.  So ``correct + rightly_alone`` (the first ``right_object`` of 2.62.7)
moves with the anchor when nothing about the object's membership changed; ``correct + alone_identified`` and ``unknown + alone_unidentified`` do not.
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "benchmark" / "association_truth"))
_spec = importlib.util.spec_from_file_location("measure_association_t", V2 / "benchmark" / "association_truth" / "measure_association.py")
MA = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MA)
ARC = 1.0 / 3600.0


def _row(det, cat, oid, ra, dec, status):
    return dict(detection_id=det, catalog=cat, object_id=oid, ra=ra, dec=dec, object_ra=ra, object_dec=dec, association_status=status, normalized_separation=0.5,
                association_confidence=0.9, likelihood_ratio=10.0, lr_sum_candidates=10.0, poserr_arcsec=0.5, combined_sigma_arcsec=1.0, source_density_arcsec2=1e-3,
                candidate_count=1, catalog_object_id=det)


def _truth():
    # one faint truth source (HSC i 26: not in the reference set, so no object can carry its id) with W1 flux at the AllWISE position
    return pd.DataFrame(dict(ra=[150.0], dec=[2.0], HSCimagAuto=[26.0], FIRACCH1=[10.0], FUVISTAKs=[np.nan], FCFHTu=[np.nan]))


def test_the_same_row_alone_or_joined_to_an_object_without_truth_id_counts_the_same():
    alone = pd.DataFrame([_row("w", "AllWISE", "OBJ1", 150.0, 2.0, "new")])
    joined = pd.DataFrame([_row("t", "2MASS PSC", "OBJ1", 150.0 + 0.3 * ARC, 2.0, "new"), _row("w", "AllWISE", "OBJ1", 150.0, 2.0, "matched")])
    ra = MA.measure_field(alone, _truth())["AllWISE"]
    rj = MA.measure_field(joined, _truth())["AllWISE"]
    assert (ra["rightly_alone"], ra["alone_unidentified"], ra["alone_identified"]) == (1, 1, 0)
    assert (rj["unknown"], rj["correct"]) == (1, 0)
    assert ra["correct"] + ra["alone_identified"] == rj["correct"] + rj["alone_identified"] == 0  # right_object
    assert ra["unknown"] + ra["alone_unidentified"] == rj["unknown"] + rj["alone_unidentified"] == 1  # unidentified
    assert ra["correct"] + ra["rightly_alone"] != rj["correct"] + rj["rightly_alone"]  # the first right_object moved with the anchor


def test_a_blended_row_whose_own_object_holds_a_counterpart_is_right_alone_or_joined():
    """Codex review of 2.62.7 (second): own object and ANOTHER object both hold acceptable counterparts.  Unjoined, the row is "missed" (another holder exists), joined it is
    "correct"; the object reading counts it in the right object both times."""
    # two bright truth sources 1.5'' apart, both in the reference set and both carrying W1 flux (a blend for the 6.1'' AllWISE PSF)
    truth = pd.DataFrame(dict(ra=[150.0, 150.0 + 1.5 * ARC], dec=[2.0, 2.0], HSCimagAuto=[20.0, 20.2], FIRACCH1=[10.0, 9.0], FUVISTAKs=[np.nan] * 2, FCFHTu=[np.nan] * 2))
    ls_a = _row("a", "DESI Legacy Surveys DR10", "OBJ1", 150.0, 2.0, "new")
    ls_b = _row("b", "DESI Legacy Surveys DR10", "OBJ2", 150.0 + 1.5 * ARC, 2.0, "new")
    alone = pd.DataFrame([ls_a, ls_b, _row("w", "AllWISE", "OBJ3", 150.0 + 0.2 * ARC, 2.0, "new")])  # the AllWISE row anchors an object of its own...
    alone.loc[2, "object_id"] = "OBJ1"  # ...that holds the LS row of source A (the LS row is its member, the AllWISE row its anchor)
    alone.loc[0, "association_status"] = "matched"
    joined = pd.DataFrame([ls_a, ls_b, _row("w", "AllWISE", "OBJ1", 150.0 + 0.2 * ARC, 2.0, "matched")])  # the same membership, the LS row anchors
    ra = MA.measure_field(alone, truth)["AllWISE"]
    rj = MA.measure_field(joined, truth)["AllWISE"]
    assert (ra["missed"], ra["alone_identified"]) == (1, 1)  # unjoined: another holder exists, so "missed", but its own object holds a counterpart
    assert rj["correct"] == 1
    assert ra["correct"] + ra["alone_identified"] == rj["correct"] + rj["alone_identified"] == 1


def test_an_object_without_a_resolving_row_reads_the_same_whoever_anchors_it():
    """2.62.10 review: one object {AllWISE, GALEX}, no resolving row, the truth source 0.1'' from the GALEX row and 0.9'' from the AllWISE row.  T(O) came from the
    ANCHOR position, so the AllWISE row was alone_unidentified when AllWISE anchored and correct when GALEX anchored.  It now comes from a member chosen by a fixed rule."""
    truth = pd.DataFrame(dict(ra=[150.0], dec=[2.0], HSCimagAuto=[20.0], FIRACCH1=[10.0], FUVISTAKs=[np.nan], FCFHTu=[5.0]))
    w, g = (150.0 + 0.9 * ARC, 2.0), (150.0 + 0.1 * ARC, 2.0)

    def row(det, cat, status, anchor):
        r = _row(det, cat, "O1", *(w if cat == "AllWISE" else g), status)
        r["object_ra"], r["object_dec"] = anchor
        return r

    by_w = pd.DataFrame([row("w", "AllWISE", "new", w), row("g", "GALEX AIS", "matched", w)])
    by_g = pd.DataFrame([row("w", "AllWISE", "matched", g), row("g", "GALEX AIS", "new", g)])
    rw, rg = MA.measure_field(by_w, truth)["AllWISE"], MA.measure_field(by_g, truth)["AllWISE"]
    readings = lambda r: (r["correct"] + r["alone_identified"], r["false"] + r["alone_wrong"], r["unknown"] + r["alone_unidentified"], r["shared"], r["displaced"])  # noqa: E731
    assert readings(rw) == readings(rg) == (1, 0, 0, 0, 0)  # right_object 1 both ways (GALEX, the sharper PSF, gives the object its truth id)
