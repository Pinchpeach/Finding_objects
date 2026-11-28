"""The two membership-only readings added in 2.62.7 (task "러") next to ``right_object``: ``shared`` and ``displaced`` (``measure_association.measure_field``).

``right_object`` = correct + alone_identified says which rows sit in an object that holds an acceptable counterpart, whoever anchors.  It cannot see a FRAGMENT: an AllWISE row alone in an
object of its own is "identified" (the position of its object reaches the truth source) while the optical object that holds the same source is another object.  ``shared`` counts rows
whose own object holds an acceptable counterpart that another object holds too; ``displaced`` counts rows whose own object holds none while another object does.  Joining the row to the
optical object moves it out of both, and neither depends on who anchors.
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "benchmark" / "association_truth"))
_spec = importlib.util.spec_from_file_location("measure_association_t2", V2 / "benchmark" / "association_truth" / "measure_association.py")
MA = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MA)
ARC = 1.0 / 3600.0


def _row(det, cat, oid, ra, dec, status):
    return dict(detection_id=det, catalog=cat, object_id=oid, ra=ra, dec=dec, object_ra=ra, object_dec=dec, association_status=status, normalized_separation=0.5,
                association_confidence=0.9, likelihood_ratio=10.0, lr_sum_candidates=10.0, poserr_arcsec=0.5, combined_sigma_arcsec=1.0, source_density_arcsec2=1e-3,
                candidate_count=1, catalog_object_id=det)


def _truth():
    # one bright truth source (HSC i 20: in the reference set) with W1 flux
    return pd.DataFrame(dict(ra=[150.0], dec=[2.0], HSCimagAuto=[20.0], FIRACCH1=[10.0], FUVISTAKs=[np.nan], FCFHTu=[np.nan]))


LS = "DESI Legacy Surveys DR10"


def test_a_row_alone_in_a_duplicate_object_is_shared_and_joining_removes_it():
    ls = _row("a", LS, "OBJ1", 150.0, 2.0, "new")
    alone = pd.DataFrame([ls, _row("w", "AllWISE", "OBJ2", 150.0 + 0.2 * ARC, 2.0, "new")])  # two objects hold the one truth source
    joined = pd.DataFrame([ls, _row("w", "AllWISE", "OBJ1", 150.0 + 0.2 * ARC, 2.0, "matched")])
    ra, rj = MA.measure_field(alone, _truth())["AllWISE"], MA.measure_field(joined, _truth())["AllWISE"]
    assert (ra["shared"], ra["displaced"], ra["alone_identified"]) == (1, 0, 1)  # right_object counts the row as right already
    assert (rj["shared"], rj["displaced"], rj["correct"]) == (0, 0, 1)
    assert ra["correct"] + ra["alone_identified"] == rj["correct"] + rj["alone_identified"] == 1  # right_object does not move: the gain is only in shared


def test_a_row_whose_own_object_holds_nothing_while_another_does_is_displaced():
    ls = _row("a", LS, "OBJ1", 150.0, 2.0, "new")
    alone = pd.DataFrame([ls, _row("w", "AllWISE", "OBJ2", 150.0 + 3.0 * ARC, 2.0, "new")])  # 3'' away: the object of the AllWISE row reaches no truth source
    joined = pd.DataFrame([ls, _row("w", "AllWISE", "OBJ1", 150.0 + 3.0 * ARC, 2.0, "matched")])
    ra, rj = MA.measure_field(alone, _truth())["AllWISE"], MA.measure_field(joined, _truth())["AllWISE"]
    assert (ra["displaced"], ra["shared"], ra["alone_unidentified"]) == (1, 0, 1)
    assert (rj["displaced"], rj["shared"], rj["correct"]) == (0, 0, 1)
    assert rj["correct"] + rj["alone_identified"] - (ra["correct"] + ra["alone_identified"]) == 1  # here right_object does see the gain
