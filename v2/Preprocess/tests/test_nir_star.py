"""2MASS point-source count prior (2.41.0)."""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Preprocess"))
import nir_star  # noqa: E402


def _rows():
    # Orion B (b ~ -16): clean K = 11.2; same with gal_contam 1; K = 13.6;
    # ph_qual C in Ks; cc_flg 'p' in Ks; high latitude clean (NGP); no 2MASS.
    return pd.DataFrame(
        {
            "object_id": [f"O{i}" for i in range(7)],
            "ra": [85.42] * 5 + [192.86, 85.42],
            "dec": [-1.9] * 5 + [27.13, -1.9],
            "2mass_psc__Kmag": [11.2, 11.2, 13.6, 11.2, 11.2, 12.5, np.nan],
            "2mass_psc__Qflg": ["AAA", "AAA", "AAA", "AAC", "AAA", "AAA", np.nan],
            "2mass_psc__Cflg": [0, "000", "000", "000", "00p", "000", np.nan],
            "2mass_psc__Xflg": [0, 1, 0, 0, 0, 0, np.nan],
        }
    )


def test_only_clean_bright_point_sources_qualify():
    assert nir_star.bright_point_source(_rows()).tolist() == [True, False, False, False, False, True, False]


def test_prior_is_stronger_near_the_plane():
    p = nir_star.star_probability(_rows())
    assert p[0] > 0.98 and 0.95 < p[5] < 0.98


def test_no_flags_no_claim():
    d = _rows().drop(columns=["2mass_psc__Xflg"])
    assert not nir_star.bright_point_source(d).any()


def _stage5(tmp_path, items):
    spec = importlib.util.spec_from_file_location("s5_nir", V2 / "Preprocess" / "05_likelihood_vectors.py")
    s5 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s5)
    d = _rows()
    d["evidence_json"] = [json.dumps(items)] * len(d)
    ev, out = tmp_path / "e.csv", tmp_path / "l.csv"
    d.to_csv(ev, index=False)
    s5.run(ev, out)
    return pd.read_csv(out)


def test_stage5_classifies_evidence_free_bright_point_sources_as_stars(tmp_path):
    r = _stage5(tmp_path, [])
    assert r.primary_class.tolist() == ["STAR", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "STAR", "UNKNOWN"]
    assert set(r.classification_status[r.primary_class.eq("UNKNOWN")]) == {"NO_EVIDENCE"}
    assert r.classification_basis[0] == nir_star.BASIS


def test_stage5_resolves_star_galaxy_conflict_but_not_galaxy_qso(tmp_path):
    star = {"rule_id": "AST-GAL-002", "class": "STAR", "score": 0.95, "raw_score": 0.95, "kind": "binary_evidence"}
    gal = {"rule_id": "PS1-MORPH-001", "class": "GALAXY", "score": 0.95, "raw_score": 0.95, "kind": "binary_evidence"}
    qso = {"rule_id": "SPC-SDSS-003", "class": "QSO", "score": 0.95, "raw_score": 0.95, "kind": "catalog_label"}
    r = _stage5(tmp_path, [star, gal])
    assert r.primary_class[0] == "STAR"
    r = _stage5(tmp_path, [gal, qso])
    assert r.classification_basis[0] != nir_star.BASIS
