"""Literature-only classes carry no probability (2.54.0, Stage 5)."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

P = Path(__file__).resolve().parents[1]


def _stage5():
    spec = importlib.util.spec_from_file_location("s5_literature", P / "05_likelihood_vectors.py")
    s5 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s5)
    return s5


def test_ned_only_qso_is_a_literature_label_without_probability(tmp_path):
    s5 = _stage5()
    # as Stage 4 writes them (score = 0.85 x reliability 0.8 x association)
    label = {"score": 0.68, "raw_score": 0.85, "reliability": 0.8, "association_reliability": 1.0,
             "kind": "catalog_label", "origin": "CATALOG", "feature_group": "catalog_reference"}
    ned = label | {"rule_id": "NED-TYPE-001", "class": "QSO", "value": "QSO"}
    simbad = label | {"rule_id": "SIMBAD-TYPE-001", "class": "GALAXY", "value": "G"}
    ls = {"rule_id": "LS-MORPH-001", "class": "GALAXY", "score": 0.9, "raw_score": 0.9, "kind": "morphology"}
    d = pd.DataFrame(
        {
            "object_id": ["NEDONLY", "SIMBADONLY", "MEASURED"],
            "ra": [150.10, 150.11, 150.12],
            "dec": [2.20, 2.21, 2.22],
            "catalogs": ["NED", "SIMBAD", "DESI Legacy Surveys DR10|NED"],
            "evidence_json": [json.dumps([ned]), json.dumps([simbad]), json.dumps([ls, ned | {"class": "GALAXY"}])],
        }
    )
    src = tmp_path / "e.csv"
    d.to_csv(src, index=False)
    s5.run(src, tmp_path / "o.csv")
    o = pd.read_csv(tmp_path / "o.csv").set_index("object_id")
    for oid, cls in (("NEDONLY", "QSO"), ("SIMBADONLY", "GALAXY")):
        r = o.loc[oid]
        assert r.primary_class == cls  # the literature class is kept
        assert r.classification_status == "LITERATURE_LABEL"
        assert r.classification_basis == s5.LITERATURE_BASIS
        assert np.isnan(r.primary_confidence)
        assert all(np.isnan(r[f"p_{c}"]) for c in ("star", "galaxy", "qso"))
    m = o.loc["MEASURED"]  # a measurement as well: a probability as before
    assert m.classification_status != "LITERATURE_LABEL"
    assert np.isfinite(m.p_galaxy)


def test_literature_only_needs_evidence_decision():
    s5 = _stage5()
    ned = [{"rule_id": "NED-TYPE-001", "class": "QSO", "score": 0.85}]
    both = ned + [{"rule_id": "DSC-001", "class": "QSO", "score": 0.6}]
    got = s5.literature_only([ned, ned, both, []], ["evidence", "near-infrared star counts", "evidence", "evidence"])
    assert got.tolist() == [True, False, False, False]
