"""The low-latitude QSO switches (2.61.3, ``Preprocess/lowlat_qso.py``): off by default, act only below ``V2_LOWLAT_QSO_ABSB``."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "benchmark" / "lowlat_qso"))
_spec = importlib.util.spec_from_file_location("lowlat_qso_under_test", ROOT / "lowlat_qso.py")
LL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LL)

# rotation ICRS -> Galactic, the rows of lowlat_qso.galactic_*: x towards the Centre, y towards l = 90, z the pole
_R = np.array([[-0.0548755604, -0.8734370902, -0.4838350155],
               [0.4941094279, -0.4448296300, 0.7469822445],
               [-0.8676661490, -0.1980763734, 0.4559837762]])  # fmt: skip


def eq(l_deg: float, b_deg: float) -> tuple[float, float]:
    """(ra, dec) of a Galactic position."""
    l, b = math.radians(l_deg), math.radians(b_deg)
    x = _R.T @ np.array([math.cos(b) * math.cos(l), math.cos(b) * math.sin(l), math.sin(b)])
    return math.degrees(math.atan2(x[1], x[0])) % 360.0, math.degrees(math.asin(x[2]))


def frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("V2_LOWLAT_QSO", raising=False)
    monkeypatch.delenv("V2_LOWLAT_QSO_ABSB", raising=False)


def test_the_helper_rotation_round_trips():
    for l, b in ((0.0, 0.0), (195.0, 13.8), (120.0, -40.0), (300.0, 60.0)):
        ra, dec = eq(l, b)
        assert abs(float(LL.galactic_latitude(ra, dec)) - b) < 1e-4
    ra, dec = eq(0.0, 0.0)
    assert float(LL.galactic_centre_distance(ra, dec)) < 0.01  # arccos near 1 amplifies the 1e-10 rounding of the matrix


def test_everything_is_off_by_default():
    ra, dec = eq(150.0, 5.0)
    df = frame([dict(ra=ra, dec=dec, catalogs="AllWISE")])
    assert LL.options() == frozenset()
    assert not LL.qso_forbidden(df).any()
    assert LL.wise_rule_allowed("WISE-AGN-001", df.iloc[0], ra, dec)
    assert LL.wise_rule_allowed("WISE-AGN-R90-001", df.iloc[0], ra, dec)


def test_unknown_and_exclusive_options(monkeypatch):
    monkeypatch.setenv("V2_LOWLAT_QSO", "surveys2,nonsense")
    with pytest.raises(ValueError, match="unknown"):
        LL.options()
    monkeypatch.setenv("V2_LOWLAT_QSO", "surveys2,surveys3")
    with pytest.raises(ValueError, match="exclude"):
        LL.options()
    monkeypatch.setenv("V2_LOWLAT_QSO", " surveys2 , pm ,")
    assert LL.options() == frozenset({"surveys2", "pm"})
    monkeypatch.setenv("V2_LOWLAT_QSO_ABSB", "120")
    with pytest.raises(ValueError):
        LL.max_abs_b()
    monkeypatch.setenv("V2_LOWLAT_QSO_ABSB", "nan")
    with pytest.raises(ValueError):
        LL.max_abs_b()


def test_annotation_catalogues_are_not_surveys():
    s = pd.Series(["AllWISE", "AllWISE|NED", "AllWISE|DESI Legacy Surveys DR10", "SIMBAD|NED", "", None,
                   "AllWISE|DESI Legacy Surveys DR10|Gaia DR3"])  # fmt: skip
    assert LL.n_surveys(s).tolist() == [1, 1, 2, 0, 0, 0, 3]


@pytest.mark.parametrize("opt,need", [("surveys2", 2), ("surveys3", 3)])
def test_survey_count_limit_acts_at_low_latitude_only(monkeypatch, opt, need):
    monkeypatch.setenv("V2_LOWLAT_QSO", opt)
    cats = ["AllWISE", "AllWISE|DESI Legacy Surveys DR10", "AllWISE|DESI Legacy Surveys DR10|Gaia DR3"]
    lo, hi = eq(150.0, 8.0), eq(150.0, 45.0)
    df = frame([dict(ra=lo[0], dec=lo[1], catalogs=c) for c in cats] + [dict(ra=hi[0], dec=hi[1], catalogs=c) for c in cats])
    got = LL.qso_forbidden(df).tolist()
    assert got[:3] == [n < need for n in (1, 2, 3)]
    assert got[3:] == [False, False, False], "the switches leave high latitude alone"


def test_latitude_limit_follows_the_environment(monkeypatch):
    monkeypatch.setenv("V2_LOWLAT_QSO", "surveys2")
    ra, dec = eq(200.0, 12.0)
    df = frame([dict(ra=ra, dec=dec, catalogs="AllWISE")])
    assert LL.qso_forbidden(df).tolist() == [True]  # 12 < 20 (default)
    monkeypatch.setenv("V2_LOWLAT_QSO_ABSB", "10")
    assert LL.qso_forbidden(df).tolist() == [False]
    monkeypatch.setenv("V2_LOWLAT_QSO_ABSB", "15")
    assert LL.qso_forbidden(df).tolist() == [True]
    # the north and the south of the plane alike
    ra2, dec2 = eq(200.0, -12.0)
    assert LL.qso_forbidden(frame([dict(ra=ra2, dec=dec2, catalogs="AllWISE")])).tolist() == [True]


def test_missing_position_or_catalogue_column_is_left_alone(monkeypatch):
    monkeypatch.setenv("V2_LOWLAT_QSO", "surveys2,pm")
    df = frame([dict(ra=np.nan, dec=np.nan, catalogs="AllWISE"), dict(ra="x", dec="y", catalogs="AllWISE")])
    assert LL.qso_forbidden(df).tolist() == [False, False]
    assert LL.qso_forbidden(frame([dict(ra=150.0, dec=2.0)])).tolist() == [False]
    assert len(LL.qso_forbidden(frame([]))) == 0
    ra, dec = eq(200.0, 5.0)
    # no catalogue column: the object counts 0 surveys, so it is held back (fail closed at low latitude)
    assert LL.qso_forbidden(frame([dict(ra=ra, dec=dec)])).tolist() == [True]


def _gaia(**kw):
    base = dict(gaia_dr3__pmra=0.0, gaia_dr3__pmdec=0.0, gaia_dr3__pmra_error=0.1, gaia_dr3__pmdec_error=0.1,
                gaia_dr3__pmra_pmdec_corr=0.0, gaia_dr3__phot_g_mean_mag=18.0)  # fmt: skip
    base.update(kw)
    return base


def test_proper_motion_density_matches_fu_2021_eq10():
    f = LL.log10_fpm0(frame([_gaia()]))[0]
    sx = math.sqrt((1.08 * 0.1) ** 2 + 0.066**2)
    assert f == pytest.approx(-math.log10(2 * math.pi * sx * sx), abs=1e-9)
    # a bright star (G < 13) takes the smaller intrinsic scatter, which makes the density at zero larger
    assert LL.log10_fpm0(frame([_gaia(gaia_dr3__phot_g_mean_mag=11.0)]))[0] > f
    # the density falls with the proper motion: 1 mas/yr at 0.1 mas/yr errors is far outside
    assert LL.log10_fpm0(frame([_gaia(gaia_dr3__pmra=1.0)]))[0] < LL.PM_LOG10_CUT
    # no Gaia columns, no value
    assert math.isnan(LL.log10_fpm0(frame([dict(ra=1.0)]))[0])


def test_proper_motion_switch(monkeypatch):
    monkeypatch.setenv("V2_LOWLAT_QSO", "pm")
    ra, dec = eq(200.0, 8.0)
    hra, hdec = eq(200.0, 50.0)
    still = dict(ra=ra, dec=dec, catalogs="Gaia DR3|AllWISE", **_gaia())
    moving = dict(ra=ra, dec=dec, catalogs="Gaia DR3|AllWISE", **_gaia(gaia_dr3__pmra=3.0, gaia_dr3__pmdec=-2.0))
    no_gaia = dict(ra=ra, dec=dec, catalogs="AllWISE")
    high_moving = dict(ra=hra, dec=hdec, catalogs="Gaia DR3|AllWISE", **_gaia(gaia_dr3__pmra=3.0, gaia_dr3__pmdec=-2.0))
    df = frame([still, moving, no_gaia, high_moving])
    assert LL.qso_forbidden(df).tolist() == [False, True, False, False]


def test_second_survey_for_the_wise_rules(monkeypatch):
    monkeypatch.setenv("V2_LOWLAT_QSO", "wise_second")
    lo, hi = eq(200.0, 8.0), eq(200.0, 50.0)
    for rid in ("WISE-AGN-001", "WISE-AGN-R90-001"):
        allwise_only = pd.Series(dict(catalogs="AllWISE"))
        with_ls = pd.Series(dict(catalogs="AllWISE|DESI Legacy Surveys DR10"))
        annotated = pd.Series(dict(catalogs="AllWISE|NED|SIMBAD"))
        assert not LL.wise_rule_allowed(rid, allwise_only, *lo)
        assert LL.wise_rule_allowed(rid, with_ls, *lo)
        assert not LL.wise_rule_allowed(rid, annotated, *lo), "an annotation catalogue is no second survey"
        assert LL.wise_rule_allowed(rid, allwise_only, *hi), "high latitude is left alone"
    assert LL.wise_rule_allowed("WISE-AGN-001", pd.Series(dict(catalogs="AllWISE")), None, None)


def test_footprint_for_the_stern_rule_only(monkeypatch):
    monkeypatch.setenv("V2_LOWLAT_QSO", "wise_footprint")
    row = pd.Series(dict(catalogs="AllWISE|DESI Legacy Surveys DR10"))
    plane = eq(100.0, 4.0)  # |b| < 10
    near_centre = eq(10.0, 15.0)  # |b| > 10 but within 30 deg of the Centre
    open_sky = eq(150.0, 25.0)
    assert not LL.wise_rule_allowed("WISE-AGN-001", row, *plane)
    assert not LL.wise_rule_allowed("WISE-AGN-001", row, *near_centre)
    assert LL.wise_rule_allowed("WISE-AGN-001", row, *open_sky)
    # R90 has its own footprint check in 04_build_evidence: this switch leaves it alone
    assert LL.wise_rule_allowed("WISE-AGN-R90-001", row, *plane)


def test_region_bootstrap_density():
    import ab_variants as AB  # noqa: E402

    reg = pd.DataFrame(dict(name=list("abcd"), area_deg2=[0.1, 0.1, 0.1, 0.1], all=[0, 0, 0, 8]))
    est, lo, hi = AB.boot_density(reg, "all")
    assert est == pytest.approx(8 / 0.4)
    assert lo < est < hi
    assert lo >= 0.0 and hi <= 80.0  # all in one region of four: the interval is wide, not Poisson-narrow
    assert hi - lo > 40.0
    # deterministic
    assert AB.boot_density(reg, "all") == (est, lo, hi)


def test_catalogues_of_one_survey_count_once():
    """2.61.3 review: a survey's catalogues of the same measurement are one survey (Gaia + its SOS tables, the two ZTF tables,
    DESI spectra + FastSpecFit, SGA-2020 from Legacy Surveys imaging); different telescopes in the same bands count apart."""
    cats = pd.Series([
        "Gaia DR3|Gaia DR3 variability SOS",
        "ZTF light curves|ZTF periodic variables",
        "DESI DR1 spectroscopy|DESI DR1 FastSpecFit",
        "DESI Legacy Surveys DR10|SGA-2020",
        "Pan-STARRS1 DR2 MeanObject|DESI Legacy Surveys DR10|SDSS DR18 PhotoObj",
        "SDSS DR18 PhotoObj|SDSS DR18 spectroscopy",
        "AllWISE|DESI Legacy Surveys DR10|NED",
    ])  # fmt: skip
    assert LL.n_surveys(cats).tolist() == [1, 1, 1, 1, 3, 2, 2]


def test_footprint_switch_leaves_high_latitude_near_the_centre_alone(monkeypatch):
    """2.61.3 review: wise_footprint tested only the R90 footprint, so it acted within 30 deg of the Galactic Centre at any
    latitude; every switch now acts only below V2_LOWLAT_QSO_ABSB."""
    monkeypatch.setenv("V2_LOWLAT_QSO", "wise_footprint")
    row = pd.Series(dict(catalogs="AllWISE|DESI Legacy Surveys DR10"))
    high_near_centre = eq(5.0, 25.0)  # |b| = 25 >= 20, 25.5 deg from the Centre
    assert float(LL.galactic_centre_distance(*high_near_centre)) < 30.0
    assert LL.wise_rule_allowed("WISE-AGN-001", row, *high_near_centre)
    assert not LL.wise_rule_allowed("WISE-AGN-001", row, *eq(5.0, 15.0))  # the same direction below 20 deg
    monkeypatch.setenv("V2_LOWLAT_QSO_ABSB", "30")
    assert not LL.wise_rule_allowed("WISE-AGN-001", row, *high_near_centre)  # inside the range when the range is wider


def test_held_back_qso_is_visible_with_its_reason(tmp_path, monkeypatch):
    """2.61.3 review: an object the switches hold back is UNKNOWN (LOW_CONFIDENCE) with best candidate QSO, keeps a QSO reading
    (LOWLAT_QSO_HELD) and says why in lowlat_qso_hold, which unknown_reason shows; without a switch nothing is added."""
    import json

    spec = importlib.util.spec_from_file_location("s5_lowlat_hold", ROOT / "05_likelihood_vectors.py")
    s5 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s5)
    spec = importlib.util.spec_from_file_location("unknown_reason_lowlat", ROOT.parent / "Classifier" / "unknown_reason.py")
    ur = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ur)
    ev = [{"rule_id": "LS-GBM-001", "class": "QSO", "score": 0.97, "raw_score": 0.97, "kind": "direct_probability"},
          {"rule_id": "WISE-AGN-001", "class": "EXTRAGALACTIC", "score": 0.95, "raw_score": 0.95, "kind": "binary_evidence"},
          {"rule_id": "DSC-001", "class": "QSO", "score": 0.95, "raw_score": 0.95, "kind": "direct_probability"}]  # fmt: skip
    d = pd.DataFrame({"object_id": ["ONE", "TWO", "GAIA"], "ra": [150.10, 150.11, 150.12], "dec": [2.20, 2.21, 2.22],
                      "catalogs": ["DESI Legacy Surveys DR10", "DESI Legacy Surveys DR10|AllWISE", "Gaia DR3|Gaia DR3 variability SOS"],
                      "std_mag__ls_r": [19.0] * 3, "evidence_json": [json.dumps(ev)] * 3})  # fmt: skip
    d.to_csv(tmp_path / "e.csv", index=False)
    monkeypatch.setenv("V2_LOWLAT_QSO_ABSB", "90")  # a high-latitude field, so the sky priors let the evidence say QSO
    s5.run(tmp_path / "e.csv", tmp_path / "off.csv")
    off = pd.read_csv(tmp_path / "off.csv", keep_default_na=False).set_index("object_id")
    assert off.primary_class.tolist() == ["QSO"] * 3 and LL.HOLD_COLUMN not in off
    monkeypatch.setenv("V2_LOWLAT_QSO", "surveys2")
    s5.run(tmp_path / "e.csv", tmp_path / "on.csv")
    on = pd.read_csv(tmp_path / "on.csv", keep_default_na=False).set_index("object_id")
    for oid in ("ONE", "GAIA"):  # one survey each (Gaia + its SOS tables count once)
        r = on.loc[oid]
        assert (r.primary_class, r.classification_status, r.best_candidate_class) == ("UNKNOWN", "LOW_CONFIDENCE", "QSO")
        assert (r.secondary_class, r.secondary_class_reason) == ("QSO", LL.HELD_REASON)
        assert r[LL.HOLD_COLUMN].startswith("QSO label withheld at |b| = ") and "measured by 1 survey, 2 needed" in r[LL.HOLD_COLUMN]
        assert ur.reason(r.to_dict()) == r[LL.HOLD_COLUMN]
    two = on.loc["TWO"]
    assert two.primary_class == "QSO" and two[LL.HOLD_COLUMN] == "" and two.secondary_class == ""
    # Codex review of 2.61.3: a resolved source that the BGS galaxy test accepts must still abstain when its QSO is held
    # (the hold must not make a settled QSO label "unsettled" and so open the BGS galaxy override)
    sure = ev + [{"rule_id": "LS-CKNN-001", "class": "QSO", "score": 0.95, "raw_score": 0.95, "kind": "continuous_score"},
                 {"rule_id": "LS-MORPH-002", "class": "POINT_SOURCE", "score": 0.9, "raw_score": 0.9, "kind": "binary_evidence"},
                 {"rule_id": "WISE-AGN-R90-001", "class": "EXTRAGALACTIC", "score": 0.9, "raw_score": 0.9, "kind": "binary_evidence"}]  # fmt: skip
    d2 = pd.DataFrame({"object_id": ["SURE"], "ra": [150.10], "dec": [2.20], "catalogs": ["DESI Legacy Surveys DR10"],
                       "std_mag__ls_r": [19.0], "evidence_json": [json.dumps(sure)]})  # fmt: skip
    d2.to_csv(tmp_path / "e2.csv", index=False)
    monkeypatch.setattr(s5.BGS, "galaxy_test", lambda frame: np.ones(len(frame), bool))
    monkeypatch.delenv("V2_LOWLAT_QSO")
    s5.run(tmp_path / "e2.csv", tmp_path / "bgs_off.csv")
    r = pd.read_csv(tmp_path / "bgs_off.csv", keep_default_na=False).iloc[0]
    assert r.primary_class == "QSO" and r.primary_confidence >= s5.BGS_KEEP_P  # settled: the BGS override does not apply
    monkeypatch.setenv("V2_LOWLAT_QSO", "surveys2")
    s5.run(tmp_path / "e2.csv", tmp_path / "bgs_on.csv")
    r = pd.read_csv(tmp_path / "bgs_on.csv", keep_default_na=False).iloc[0]
    assert (r.primary_class, r.classification_status, r.secondary_class_reason) == ("UNKNOWN", "LOW_CONFIDENCE", LL.HELD_REASON)


def _ab_fixture(tmp_path, labels_by_variant, missing=()):
    """Regions r1, r2 (one sample quasar each) and one root per variant with the given QSO labels of the quasars' objects."""
    import subprocess

    truth = pd.DataFrame(dict(sample=["huo", "huo"], name=["q1", "q2"], ra=[150.0, 160.0], dec=[2.0, 2.0], l=[100.0] * 2,
                              b=[-12.0] * 2, z=[1.0] * 2, imag=[18.0] * 2, ebv=[0.1] * 2, cls=["qso"] * 2, also_in=[""] * 2))  # fmt: skip
    regions = pd.DataFrame(dict(name=["r1", "r2"], stratum=["b10-15"] * 2, kind=["qso"] * 2, ra=[150.0, 160.0], dec=[2.0, 2.0]))
    truth.to_csv(tmp_path / "truth.csv", index=False)
    regions.to_csv(tmp_path / "regions.csv", index=False)
    specs = []
    for v, labs in labels_by_variant.items():
        for reg, ra, lab in (("r1", 150.0, labs[0]), ("r2", 160.0, labs[1])):
            if (v, reg) in missing:
                continue
            d = tmp_path / v / reg
            d.mkdir(parents=True)
            pd.DataFrame([dict(object_id=f"O_{reg}", ra=ra, dec=2.0, catalogs="A|B|C", primary_class=lab, parent_object_id=np.nan,
                               classification_basis="evidence", classification_status="CLASSIFIED")]).to_csv(d / "objects.csv.gz", index=False)  # fmt: skip
        specs.append(f"{v}={tmp_path / v}")
    script = ROOT.parent / "benchmark" / "lowlat_qso" / "ab_variants.py"
    out = tmp_path / "out"
    run = subprocess.run([sys.executable, str(script), "--variants", *specs, "--regions", str(tmp_path / "regions.csv"),
                          "--truth", str(tmp_path / "truth.csv"), "--out", str(out)], capture_output=True, text=True)  # fmt: skip
    assert run.returncode == 0, run.stderr
    return pd.read_csv(out / "ab_variants.csv").set_index("variant"), json.loads((out / "coverage.json").read_text()), run.stdout


def test_variants_are_compared_on_the_same_regions(tmp_path):
    """2.61.3 review: a region missing from one variant is left out of every variant (not counted as quasars lost)."""
    d, cov, log = _ab_fixture(tmp_path, {"base": ("QSO", "QSO"), "switch": ("QSO", "QSO")}, missing={("switch", "r2")})
    assert cov["regions_excluded"] == ["r2"] and cov["regions_compared"] == 1 and not cov["complete"]
    assert "INCOMPLETE" in log
    assert d.loc["base", "quasars"] == d.loc["switch", "quasars"] == 1
    assert d.loc["switch", "quasars_lost_vs_control"] == 0


def test_variants_without_false_labels(tmp_path):
    """2.61.3 review: no QSO label outside the sample gives zero counts, not an error."""
    d, cov, _ = _ab_fixture(tmp_path, {"base": ("QSO", "STAR"), "switch": ("QSO", "QSO")})
    assert cov["complete"] and cov["regions_compared"] == 2
    assert d.loc["base", "false_all_n"] == 0 and d.loc["base", "recall_qso"] == 1 and d.loc["switch", "recall_qso"] == 2
    assert d.loc["switch", "quasars_lost_vs_control"] == 0


def test_object_table_keeps_metadata_of_labels_a_later_variant_adds(tmp_path):
    """Codex review of 2.61.3: an object only a later variant labels QSO keeps its coordinates and catalogue count."""
    import subprocess

    truth = pd.DataFrame(dict(sample=["huo"], name=["q1"], ra=[150.0], dec=[2.0], l=[100.0], b=[-12.0], z=[1.0], imag=[18.0],
                              ebv=[0.1], cls=["qso"], also_in=[""]))  # fmt: skip
    regions = pd.DataFrame(dict(name=["r1"], stratum=["b10-15"], kind=["qso"], ra=[150.0], dec=[2.0]))
    truth.to_csv(tmp_path / "truth.csv", index=False)
    regions.to_csv(tmp_path / "regions.csv", index=False)
    a = 1 / 3600
    for v, extra in (("base", "STAR"), ("later", "QSO")):  # the neighbour at 30'' is QSO only in the later variant
        d = tmp_path / v / "r1"
        d.mkdir(parents=True)
        pd.DataFrame([dict(object_id="O1", ra=150.0, dec=2.0, catalogs="A|B|C", primary_class="QSO", parent_object_id=np.nan),
                      dict(object_id="O2", ra=150.0 + 30 * a, dec=2.0, catalogs="A|B", primary_class=extra, parent_object_id=np.nan)]
                     ).to_csv(d / "objects.csv.gz", index=False)  # fmt: skip
    out = tmp_path / "out"
    script = ROOT.parent / "benchmark" / "lowlat_qso" / "ab_variants.py"
    run = subprocess.run([sys.executable, str(script), "--variants", f"base={tmp_path / 'base'}", f"later={tmp_path / 'later'}",
                          "--regions", str(tmp_path / "regions.csv"), "--truth", str(tmp_path / "truth.csv"), "--out", str(out)],
                         capture_output=True, text=True)  # fmt: skip
    assert run.returncode == 0, run.stderr
    o = pd.read_csv(out / "qso_labelled_not_sample_by_variant.csv.gz").set_index("object_id")
    assert o.loc["O2", "ra"] == pytest.approx(150.0 + 30 * a) and o.loc["O2", "n_catalogs"] == 2
    assert not o.loc["O2", "base"] and o.loc["O2", "later"]


def test_depth_split_uses_the_common_regions(tmp_path):
    """Codex review of 2.61.3: by_depth.py leaves a region out of every variant when one variant lacks its record."""
    import subprocess

    _ab_fixture(tmp_path, {"base": ("QSO", "QSO"), "switch": ("QSO", "QSO")}, missing={("switch", "r2")})
    script = ROOT.parent / "benchmark" / "lowlat_qso" / "by_depth.py"
    run = subprocess.run([sys.executable, str(script), "--variants", f"base={tmp_path / 'base'}", f"switch={tmp_path / 'switch'}",
                          "--regions", str(tmp_path / "regions.csv"), "--truth", str(tmp_path / "truth.csv"),
                          "--out", str(tmp_path / "depth.csv")], capture_output=True, text=True)  # fmt: skip
    assert run.returncode == 0, run.stderr
    assert "INCOMPLETE" in run.stdout
    d = pd.read_csv(tmp_path / "depth.csv")
    assert int(d.regions.sum()) == 1 and int(d.quasars.sum()) == 1
