"""Young stars in nebulae: MYStIX membership and Gaia fidelity (2.42.0)."""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Get_data"))
import mystix_mpcm  # noqa: E402


def _s5():
    spec = importlib.util.spec_from_file_location("s5_member", V2 / "Preprocess" / "05_likelihood_vectors.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_ob_only_members_are_dropped(monkeypatch):
    rows = pd.DataFrame(
        {
            "MPCM": ["053500.1-052300.0", "053500.2-052300.0", "053500.3-052300.0"],
            "RAJ2000": [83.75, 83.751, 83.752],
            "DEJ2000": [-5.38, -5.38, -5.38],
            "Xind": [12, np.nan, np.nan],
            "Iind": [np.nan, 5, np.nan],
            "Olab": ["", "", "OB 7"],
        }
    )
    monkeypatch.setattr(mystix_mpcm, "vizier_cone", lambda *a, **k: rows.copy())
    out = mystix_mpcm.fetch(83.75, -5.38, 6)
    assert out.catalog_object_id.tolist() == ["053500.1-052300.0", "053500.2-052300.0"]
    assert set(out.catalog) == {"MYStIX MPCM"}


def _run(tmp_path, catalogs, items):
    s5 = _s5()
    d = pd.DataFrame({"object_id": ["O1"], "ra": [83.8], "dec": [-5.4], "catalogs": [catalogs], "evidence_json": [json.dumps(items)]})
    ev, out = tmp_path / "e.csv", tmp_path / "l.csv"
    d.to_csv(ev, index=False)
    s5.run(ev, out)
    return pd.read_csv(out).iloc[0]


def test_member_is_a_star_unless_its_spectrum_says_otherwise(tmp_path):
    dsc_gal = {"rule_id": "DSC-001", "class": "GALAXY", "score": 0.99, "raw_score": 0.99, "kind": "direct_probability"}
    r = _run(tmp_path, "2MASS PSC|Chandra CSC 2.0|MYStIX MPCM", [dsc_gal])
    assert r.primary_class == "STAR" and r.classification_basis.startswith("young-star membership")
    spec_gal = {"rule_id": "SPC-SDSS-002", "class": "GALAXY", "score": 0.99, "raw_score": 0.99, "kind": "catalog_label"}
    r = _run(tmp_path, "2MASS PSC|MYStIX MPCM|SDSS DR18 spectroscopy", [spec_gal])
    assert r.primary_class != "STAR"
    r = _run(tmp_path, "2MASS PSC|Chandra CSC 2.0", [])
    assert r.primary_class == "UNKNOWN"


def test_high_fidelity_lifts_the_cstar_gate():
    s5 = _s5()
    pm = {"rule_id": "AST-GAL-002", "class": "STAR", "value": 30.0, "reliability": 0.9, "association_reliability": 0.9, "cstar_sigma": 40.0}
    assert not s5._decisive_motion([pm])
    assert s5._decisive_motion([dict(pm, fidelity=0.95)])
    assert not s5._decisive_motion([dict(pm, fidelity=0.5)])
