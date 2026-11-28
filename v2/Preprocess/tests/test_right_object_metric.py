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
