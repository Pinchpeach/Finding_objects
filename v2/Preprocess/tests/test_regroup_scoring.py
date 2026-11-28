"""The three readings of a truth source's label (regroup.score_accuracy) and their comparison (rescore_labels), 2.62.6.

``pick``  the class of the one object with the most catalogues within 1.5'' (the old reading); ``exists``  an object within 0.5'' has the truth class;
``every``  all objects within 0.5'' have it.  A rule that groups a fragment under its parent changes which object is the pick but not what is within 0.5''.
"""

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "benchmark" / "association_truth"))
spec = importlib.util.spec_from_file_location("regroup_t", V2 / "benchmark" / "association_truth" / "regroup.py")
RG = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RG)
import rescore_labels as RL  # noqa: E402

ARC = 1.0 / 3600.0


def truth():
    return pd.DataFrame(dict(ra=[10.0], dec=[2.0], ACSmuClass=[1], lptype=[0], ACSF814Wmag=[22.0]))  # one GALAXY


def objects(parent_of_fragment=None):
    """A GALAXY object of one catalogue 0.1'' from the truth source and a STAR fragment of three catalogues 0.3'' away (it wins the pick)."""
    return pd.DataFrame(
        dict(object_id=["A", "B"], ra=[10.0 + 0.1 * ARC, 10.0 + 0.3 * ARC], dec=[2.0, 2.0], catalogs=["LS", "LS|PS1|AllWISE"], primary_class=["GALAXY", "STAR"],
             parent_object_id=[None, parent_of_fragment])  # fmt: skip
    )


def test_a_fragment_of_the_wrong_class_wins_the_pick_but_not_the_existence_reading():
    r = RG.score_accuracy(objects(), truth()).iloc[0]
    assert r.pred == "STAR" and r.n_near == 2  # the pick is the fragment with more catalogues
    assert r.exists_near and not r.all_near and r.classes_near == "GALAXY|STAR"


def test_grouping_the_fragment_under_its_parent_changes_the_pick_only():
    r = RG.score_accuracy(objects(parent_of_fragment="A"), truth()).iloc[0]
    assert r.pred == "GALAXY" and r.exists_near and r.all_near and r.classes_near == "GALAXY"  # the fragment now takes its parent's class


def test_a_truth_source_without_an_object_within_0_5_arcsec_is_in_no_reading():
    o = objects()
    o["ra"] = [10.0 + 1.0 * ARC, 10.0 + 1.2 * ARC]  # both farther than 0.5'', inside the 1.5'' of the pick
    r = RG.score_accuracy(o, truth()).iloc[0]
    assert r.n_near == 0 and not r.exists_near and not r.all_near and r.pred == "STAR"


def labels(parent):
    t = RG.score_accuracy(objects(parent), truth())
    t.insert(0, "field", "deep_cosmos_1")
    return t


def test_rescore_counts_the_pick_artifact_as_fixed_only_under_the_pick_reading():
    split = pd.Series({"deep_cosmos_1": "calibration"})
    rows = {(r["half"], r["reading"]): r for r in RL.compare(labels(None), labels("A"), split)}
    assert rows[("calibration", "pick")]["fixed"] == 1 and rows[("calibration", "pick")]["broken"] == 0
    assert rows[("calibration", "exists")]["fixed"] == 0 and rows[("calibration", "exists")]["broken"] == 0  # the same GALAXY was within 0.5'' in both
    assert rows[("calibration", "every")]["fixed"] == 1  # but the wrong-class competitor within 0.5'' is gone
    assert rows[("all", "pick")]["truth_sources"] == 1
    # an object is within 0.5'' in both runs and the class that is there did not change: nothing fixed or broken among the truth sources with one in both
    assert rows[("calibration", "exists_both_near")]["truth_sources"] == 1 and rows[("calibration", "exists_both_near")]["fixed"] == 0


def test_the_exact_mcnemar_p_is_two_sided():
    assert RL.mcnemar(0, 11) == pytest.approx(2 * 0.5**11)
    assert RL.mcnemar(1, 11) == pytest.approx(2 * (1 + 12) / 2**12)
    assert RL.mcnemar(0, 0) == 1.0
