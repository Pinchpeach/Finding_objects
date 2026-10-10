"""End-to-end Preprocess smoke test on the committed NGC 4522 raw data."""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT.parent / "rawdata"
RULES = ROOT / "classification_rules.csv"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"pre_{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_pipeline(tmp_path: Path) -> pd.DataFrame:
    import sys
    sys.path.insert(0, str(ROOT))
    a, i, f, e, l = (tmp_path / n for n in ("a.csv", "i.csv", "f.csv", "e.csv", "l.csv"))
    _load("01_source_association").run(RAW, a)
    _load("02_integrate_objects").run(a, RAW, i)
    _load("03_extract_features").run(i, RULES, f)
    _load("04_build_evidence").run(f, RULES, e)
    _load("05_likelihood_vectors").run(e, l)
    return pd.read_csv(l, low_memory=False)


def test_pipeline_runs_and_emits_valid_vectors(tmp_path):
    out = _run_pipeline(tmp_path)
    assert len(out) > 0
    total = out[["likelihood_star", "likelihood_galaxy", "likelihood_qso"]].sum(axis=1)
    assert ((total - 1.0).abs() < 1e-9).all()
    assert set(out.primary_class) <= {"STAR", "GALAXY", "QSO", "UNKNOWN"}
    # The SDSS spectrum of NGC 4522 itself is a spectroscopic galaxy.
    spec = out[out.catalogs.fillna("").str.contains("SDSS DR18 spectroscopy", regex=False)]
    assert (spec.primary_class == "GALAXY").all()


def test_evidence_applies_each_reliability_once(tmp_path):
    out = _run_pipeline(tmp_path)
    for raw in out.evidence_json:
        for ev in json.loads(raw):
            if ev.get("kind") == "linear_feature":
                continue
            expected = ev["raw_score"] * ev["reliability"] * ev["association_reliability"]
            assert math.isclose(ev["score"], expected, rel_tol=1e-9)
            assert ev["reliability"] <= 1.0 and ev["association_reliability"] <= 1.0


def test_emit_does_not_square_association_reliability():
    mod = _load("04_build_evidence")
    rule = {"rule_id": "X", "likelihood_method": "k", "threshold_origin": "o", "feature_group": "g"}
    out = []
    mod.emit(out, rule, "GALAXY", 0.9, reliability=1.0, association_reliability=0.5)
    assert math.isclose(out[0]["score"], 0.45)


def test_proper_motion_star_rule_is_quality_gated():
    mod = _load("04_build_evidence")
    rules = pd.read_csv(RULES, keep_default_na=False)
    rule = rules[rules.rule_id == "AST-GAL-002"].iloc[0]
    row = pd.Series({
        "pmra": 50.0, "pmra_error": 1.0, "pmdec": 0.0, "pmdec_error": 1.0,
        "catalog_confidence_gaia_astrometry": 0.5,
        "association_confidence__gaia_dr3": 0.5,
    })
    (ev,) = mod.evaluate(rule, row)
    assert math.isclose(ev["score"], ev["raw_score"] * 0.25)


def test_same_named_fields_do_not_cross_catalogs(tmp_path):
    """DESI Legacy and SDSS PhotoObj both publish ``type``; rules must read SDSS's."""
    import sys
    sys.path.insert(0, str(ROOT))
    raw = tmp_path / "raw"
    raw.mkdir()
    base = {"ra": 150.0, "dec": 2.0}
    pd.DataFrame([{**base, "catalog": "DESI Legacy Surveys DR10", "catalog_object_id": "ls1",
                   "object_name": "ls1", "type": "PSF"}]).to_csv(raw / "desi_legacy_t.csv", index=False)
    pd.DataFrame([{**base, "catalog": "SDSS DR18 PhotoObj", "catalog_object_id": "1237", "object_name": "s1",
                   "type": 3, "clean": 1}]).to_csv(raw / "sdss_dr18_t.csv", index=False)
    a, i, f, e = (tmp_path / n for n in ("a.csv", "i.csv", "f.csv", "e.csv"))
    _load("01_source_association").run(raw, a)
    _load("02_integrate_objects").run(a, raw, i)
    integrated = pd.read_csv(i)
    assert len(integrated) == 1 and integrated.loc[0, "type"] == "PSF"  # legacy bare name: first wins
    _load("03_extract_features").run(i, RULES, f)
    _load("04_build_evidence").run(f, RULES, e)
    ev = json.loads(pd.read_csv(e).loc[0, "evidence_json"])
    assert any(x["rule_id"] == "SDSS-PHOTO-001" and x["class"] == "GALAXY" for x in ev)


def test_64bit_identifiers_survive_association(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    # A missing ID in the column would make pandas parse the rest as float64.
    pd.DataFrame([
        {"catalog": "Gaia DR3", "catalog_object_id": "3796442680948579328", "object_name": "a", "ra": 10.0, "dec": 1.0},
        {"catalog": "Gaia DR3", "catalog_object_id": "3796442680948579329", "object_name": "b", "ra": 11.0, "dec": 1.0},
        {"catalog": "Gaia DR3", "catalog_object_id": None, "object_name": "c", "ra": 12.0, "dec": 1.0},
    ]).to_csv(raw / "gaia_t.csv", index=False)
    a = tmp_path / "a.csv"
    _load("01_source_association").run(raw, a)
    ids = set(pd.read_csv(a, dtype={"catalog_object_id": str}).catalog_object_id)
    assert {"3796442680948579328", "3796442680948579329"} <= ids
    assert "nan" not in ids


def test_detections_inside_large_galaxy_abstain(tmp_path):
    import sys
    sys.path.insert(0, str(ROOT))
    raw = tmp_path / "raw"
    raw.mkdir()
    ra0, dec0 = 150.0, 2.0
    # SGA galaxy: D26 = 4 arcmin, major axis North-South (PA 0), b/a = 0.5.
    pd.DataFrame([{"catalog": "SGA-2020", "catalog_object_id": "SGA1", "object_name": "NGC X", "ra": ra0, "dec": dec0,
                   "sga_d26_arcmin": 4.0, "sga_pa_deg": 0.0, "sga_ba": 0.5}]).to_csv(raw / "sga.csv", index=False)
    east = lambda arcmin: ra0 + arcmin / 60.0 / math.cos(math.radians(dec0))
    pd.DataFrame([
        # 1.5' North: inside (major semi-axis 2').  1.5' East: outside (minor semi-axis 1').
        {"catalog": "SIMBAD", "catalog_object_id": "in", "object_name": "in", "ra": ra0, "dec": dec0 + 1.5 / 60, "otype": "*"},
        {"catalog": "SIMBAD", "catalog_object_id": "out", "object_name": "out", "ra": east(1.5), "dec": dec0, "otype": "*"},
    ]).to_csv(raw / "simbad.csv", index=False)
    a, i, f, e, l = (tmp_path / n for n in ("a.csv", "i.csv", "f.csv", "e.csv", "l.csv"))
    _load("01_source_association").run(raw, a)
    _load("02_integrate_objects").run(a, raw, i)
    _load("03_extract_features").run(i, RULES, f)
    _load("04_build_evidence").run(f, RULES, e)
    _load("05_likelihood_vectors").run(e, l)
    out = pd.read_csv(l).set_index("simbad__catalog_object_id", drop=False)
    assert math.isclose(out.loc["in", "host_elliptical_radius"], 0.75, rel_tol=1e-3)
    assert math.isclose(out.loc["out", "host_elliptical_radius"], 1.5, rel_tol=1e-3)
    assert out.loc["in", "classification_status"] == "WITHIN_LARGE_GALAXY"
    # Outside the ellipse the object is classified normally (a lone SIMBAD
    # label may still fall below the abstention threshold).
    assert out.loc["out", "classification_status"] != "WITHIN_LARGE_GALAXY"
    assert out.loc["out", "p_star"] > max(out.loc["out", "p_galaxy"], out.loc["out", "p_qso"])
    host = pd.read_csv(l)
    host = host[host.catalogs.str.contains("SGA-2020", regex=False)].iloc[0]
    assert host.primary_class == "GALAXY"


def test_field_prior_em_recovers_class_mix():
    import numpy as np
    mod = _load("05_likelihood_vectors")
    rng = np.random.default_rng(1)
    # Calibrated under equal priors: draw posteriors, then labels from them.
    P = rng.dirichlet([0.4, 0.4, 0.4], size=60000)
    y = np.array([rng.choice(3, p=p) for p in P])
    # Label shift to a 70/20/10 field: subsample each class.
    keep = np.concatenate([rng.choice(np.where(y == c)[0], n, replace=False) for c, n in enumerate((7000, 2000, 1000))])
    pi = mod.estimate_field_prior(P[keep], [1 / 3, 1 / 3, 1 / 3])
    assert np.allclose(pi, [0.7, 0.2, 0.1], atol=0.03)


def test_one_command_pipeline_on_committed_field(tmp_path):
    import shutil
    raw = tmp_path / "raw"
    raw.mkdir()
    for f in RAW.glob("*_ra188p4155_dec9p1751_r0p5arcmin.csv"):
        shutil.copy(f, raw / f.name)
    spec = importlib.util.spec_from_file_location("v2_pipeline", ROOT.parent / "pipeline.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = mod.run(tmp_path / "work", raw_dir=raw)
    assert len(out) > 0
    assert {"primary_class", "physical_class", "variability_class", "classification_status"} <= set(out.columns)
    assert (tmp_path / "work" / "pipeline_summary.csv").exists()


def test_color_knn_same_colour_subset_and_leave_one_out():
    import sys
    import numpy as np
    sys.path.insert(0, str(ROOT))
    import color_knn
    ref = pd.DataFrame({"id": ["a", "b", "c", "d"], "truth_class": ["STAR", "STAR", "GALAXY", "GALAXY"],
                        "ls_g_r_color": [0.5, 0.52, 1.5, 1.52], "ls_r_z_color": [0.2, 0.21, 0.9, 0.91],
                        "ls_z_w1_color": [-1.0, np.nan, 1.0, np.nan], "ls_w1_w2_color": np.nan})
    obj = pd.DataFrame({"ls_g_r_color": [0.5, 1.5, 0.5], "ls_r_z_color": [0.2, 0.9, np.nan],
                        "ls_z_w1_color": [np.nan, 1.0, np.nan]})
    f = color_knn.class_fractions(obj, ref, k=1)
    assert f[0].argmax() == 0 and f[1].argmax() == 1   # nearest in the colours both have
    assert np.isnan(f[2]).all()                         # fewer than two colours: no evidence
    # Leave-one-out: "a" may not vote for itself; its only same-subset
    # neighbour with z-W1 is "c" (GALAXY).
    g = color_knn.class_fractions(obj.iloc[[0]].assign(ls_z_w1_color=-1.0), ref, k=1, ids=["a"])
    assert g[0].argmax() == 1


def test_unreliable_evidence_is_weak_not_contrary():
    mod = _load("05_likelihood_vectors")
    model = {"classes": ["STAR", "GALAXY", "QSO"], "intercept": {"STAR": 0, "GALAXY": 0, "QSO": 0},
             "coef": {"LS-MORPH-001:GALAXY": {"STAR": -2.0, "GALAXY": 2.0, "QSO": 0.0}}}
    item = {"rule_id": "LS-MORPH-001", "class": "GALAXY", "kind": "binary_evidence", "raw_score": 0.75,
            "reliability": 1.0, "association_reliability": 0.001, "score": 0.00075}
    p, _ = mod.fuse([item], model)
    assert abs(p["STAR"] - p["GALAXY"]) < 0.01      # ~no evidence, not "not a galaxy"
    p, _ = mod.fuse([dict(item, association_reliability=1.0, score=0.75)], model)
    assert p["GALAXY"] > 0.8


def test_association_posterior_sparse_vs_dense():
    import sys
    sys.path.insert(0, str(ROOT))
    from association_model import assess_pair
    a = {"ra": 150.0, "dec": 2.0, "poserr_arcsec": 0.3, "catalog": "X"}
    b = {"ra": 150.0, "dec": 2.0 + 1.27 / 3600, "poserr_arcsec": 0.3, "catalog": "Y"}   # ~3 sigma
    sparse = assess_pair(a, b, 1e-4)      # one source per 10^4 arcsec^2
    dense = assess_pair(a, b, 0.2)
    assert sparse["positional_likelihood"] < 0.02
    assert sparse["association_posterior"] > 0.8         # unique counterpart, sparse field
    assert dense["association_posterior"] < sparse["association_posterior"]


def test_desi_targetid_links_to_legacy_surveys_source(tmp_path):
    raw = tmp_path / "raw"; raw.mkdir()
    rel, bid, oid = 9011, 123456, 789
    tid = (rel << 42) | (bid << 22) | oid
    ra0, dec0 = 245.0, 43.0
    # Two Legacy Surveys sources 0.15" apart (one the DESI target); DESI at the target.
    pd.DataFrame([{"catalog": "DESI Legacy Surveys DR10", "catalog_object_id": "a", "ra": ra0, "dec": dec0,
                   "release": rel, "brickid": bid, "objid": oid},
                  {"catalog": "DESI Legacy Surveys DR10", "catalog_object_id": "b", "ra": ra0, "dec": dec0 + 0.15 / 3600,
                   "release": rel, "brickid": bid, "objid": oid + 1}]).to_csv(raw / "ls.csv", index=False)
    pd.DataFrame([{"catalog": "DESI DR1 spectroscopy", "catalog_object_id": str(tid), "ra": ra0, "dec": dec0 + 0.07 / 3600}]
                 ).to_csv(raw / "desi.csv", index=False)
    out = tmp_path / "a.csv"
    _load("01_source_association").run(raw, out)
    a = pd.read_csv(out, dtype={"catalog_object_id": str})
    desi = a[a.catalog == "DESI DR1 spectroscopy"].iloc[0]
    target = a[a.catalog_object_id == "a"].iloc[0]
    assert desi.object_id == target.object_id and desi.association_status != "ambiguous_new"


def test_decisive_gaia_motion_classifies_star_despite_conflict(tmp_path):
    import json
    mod = _load("05_likelihood_vectors")
    gal = {"rule_id": "LS-MORPH-001", "class": "GALAXY", "kind": "binary_evidence", "raw_score": 0.9,
           "reliability": 1.0, "association_reliability": 1.0, "score": 0.9}
    pm = lambda sig, rel=1.0: {"rule_id": "AST-GAL-002", "class": "STAR", "kind": "continuous_score", "value": sig,
                               "raw_score": sig / (sig + 5), "reliability": rel, "association_reliability": 1.0,
                               "score": rel * sig / (sig + 5)}
    rows = [[gal, pm(40.0)], [gal, pm(4.0)], [gal, pm(40.0, rel=0.5)]]   # decisive / weak / poor RUWE
    ev = tmp_path / "ev.csv"; out = tmp_path / "lk.csv"
    pd.DataFrame({"object_id": ["a", "b", "c"], "evidence_json": [json.dumps(r) for r in rows]}).to_csv(ev, index=False)
    mod.run(ev, out)
    res = pd.read_csv(out)
    assert res.loc[0, "primary_class"] == "STAR" and res.loc[0, "primary_confidence"] >= 0.99
    assert not mod._decisive_motion(rows[1]) and not mod._decisive_motion(rows[2])
    assert not (res.loc[2, "primary_class"] == "STAR" and res.loc[2, "primary_confidence"] >= 0.99)


def test_units_drop_missing_value_sentinels():
    mod = _load("units")
    df = pd.DataFrame({"pan_starrs1_dr2_meanobject__rMeanPSFMag": [-999.0, 20.5],
                       "pan_starrs1_dr2_meanobject__rMeanPSFMagErr": [-999.0, 0.05],
                       "sdss_dr18_photoobj__modelMag_u": [-9999.0, 21.0], "allwise__W1mag": [None, 15.0]})
    h = mod.harmonize(df)
    assert h["std_mag__ps1_r"].isna()[0] and h["std_mag__ps1_r"][1] == 20.5 and h["std_magerr__ps1_r"].isna()[0]
    assert h["std_mag__sdss_u"].isna()[0] and abs(h["std_mag__sdss_u"][1] - 20.96) < 1e-9
    assert abs(h["std_mag__wise_w1"][1] - 17.699) < 1e-9
