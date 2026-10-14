import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _compact():
    spec = importlib.util.spec_from_file_location("v2_compact_t", ROOT / "axes" / "compact.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_radio_pulsar_candidate_rule():
    c = _compact()
    # alpha(150 MHz - 1.4 GHz) = -1.75, compact, 20 % polarised -> candidate
    psr = {
        "nvss__S1.4": 3.0,
        "tgss_adr1__Stotal": 150.0,
        "tgss_adr1__Speak": 130.0,
        "nvss__polFlux": 0.6,
        "nvss__e_polFlux": 0.15,
    }
    r = c.classify(psr)
    assert r["label"] == "PULSAR_CANDIDATE" and r["evidence"][0]["alpha_150_1400"] < -1.5
    assert r["status"] == "RADIO_STEEP_COMPACT_POLARISED"  # 20 %, 4 sigma
    # Polarisation is supporting evidence: a 1-sigma "20 %" is not significant.
    weak = c.classify(dict(psr, **{"nvss__e_polFlux": 0.6}))
    assert (weak["label"], weak["status"]) == ("PULSAR_CANDIDATE", "RADIO_STEEP_COMPACT")
    assert c.classify(dict(psr, **{"nvss__S1.4": 30.0}))["label"] == "UNKNOWN"  # alpha = -0.7: ordinary source
    assert c.classify(dict(psr, **{"tgss_adr1__Speak": 60.0}))["label"] == "UNKNOWN"  # extended (S_tot/S_peak = 2.5)
    assert c.classify(dict(psr, **{"nvss__polFlux": 0.05}))["status"] == "RADIO_STEEP_COMPACT"  # 1.7 %: not polarised
    # Catalogue evidence still wins.
    assert c.classify(dict(psr, catalogs="ATNF Pulsar Catalog"))["label"] == "PULSAR"


def test_radio_collectors_convert_sexagesimal_positions():
    """NVSS / FIRST RAJ2000 are sexagesimal strings in VizieR; they must not become NaN."""
    import pandas as pd

    for name in ("nvss", "first"):
        spec = importlib.util.spec_from_file_location(f"v2_{name}_t", ROOT.parent / "Get_data" / f"{name}.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        df = pd.DataFrame({"RAJ2000": ["00 34 08.71"], "DEJ2000": ["-07 21 53.4"]})
        try:
            ra, dec = m._degrees(df)
            assert abs(ra.iloc[0] - 8.53629) < 1e-4 and abs(dec.iloc[0] + 7.36483) < 1e-4
        except ImportError:  # astropy missing: only the computed-column path can be checked
            pass
        df["_RAJ2000"], df["_DEJ2000"] = [8.5363], [-7.3648]
        ra, dec = m._degrees(df)
        assert ra.iloc[0] == 8.5363 and dec.iloc[0] == -7.3648


def test_ztf_periodic_variable_types():
    spec = importlib.util.spec_from_file_location("v2_var_t", ROOT / "axes" / "variability.py")
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    Z = "ztf_periodic_variables__"
    r = v.classify({Z + "Type": "Mira", Z + "Per": 320.0, Z + "rAmp": 3.1})
    assert (r["label"], r["status"]) == ("MIRA", "ZTF_PERIODIC_VARIABLE")
    assert (
        v.classify({Z + "Type": "Mira", "gaia_lpv_is_cstar": 1, "gaia_dr3__phot_bp_mean_mag": 15.0})["subtype"]
        == "C_STAR_CANDIDATE"
    )
    assert (
        v.classify({Z + "Type": "SR", "gaia_lpv_is_cstar": 1, "gaia_dr3__phot_bp_mean_mag": 15.0})["subtype"]
        == "C_STAR_CANDIDATE"
    )
    assert v.classify({Z + "Type": "RRc"})["subtype"] == "RRC"
    assert v.classify({Z + "Type": "EW"})["label"] == "ECLIPSING"
    # Gaia SOS RR Lyrae fit keeps precedence over ZTF.
    assert v.classify({Z + "Type": "EW", "gaia_rrlyrae_best_classification": "RRab"})["label"] == "RR_LYRAE"
    # ZTF before the broad Gaia classifier.
    assert v.classify({Z + "Type": "SR", "best_class_name": "ECL"})["label"] == "LPV"


def test_gaia_release_switch(monkeypatch):
    import sys

    sys.path.insert(0, str(ROOT.parent / "Get_data"))
    import gaia_release as gr

    assert gr.current().ref_epoch == 2016.0 and gr.table(gr.current(), "gaia_source") == "gaiadr3.gaia_source"
    monkeypatch.setenv("V2_GAIA_RELEASE", "dr4")
    r = gr.current()
    assert (r.ref_epoch, gr.table(r, "vari_summary"), r.designation_prefix) == (
        2017.5,
        "gaiadr4.vari_summary",
        "Gaia DR4",
    )
    assert gr.SLOT_CATALOG == "Gaia DR3"  # downstream column slot is release-independent
    monkeypatch.setenv("V2_GAIA_RELEASE", "DR9")
    import pytest

    with pytest.raises(ValueError):
        gr.current()


def test_gaia_lpv_mira_amplitude():
    spec = importlib.util.spec_from_file_location("v2_var_m", ROOT / "axes" / "variability.py")
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    r = v.classify({"gaia_lpv_amplitude": 1.1, "gaia_lpv_frequency": 1 / 300.0, "best_class_name": "LPV"})
    assert (r["label"], r["status"]) == ("MIRA", "GAIA_DR3_SOS_LPV_LARGE_AMPLITUDE")
    assert (
        v.classify({"gaia_lpv_amplitude": 0.2, "gaia_lpv_frequency": 1 / 60.0, "best_class_name": "LPV"})["label"]
        == "LPV"
    )
    assert (
        v.classify({"gaia_lpv_amplitude": 0.9, "gaia_lpv_frequency": 1 / 50.0, "best_class_name": "LPV"})["label"]
        == "LPV"
    )  # P < 80 d
    mira_c = {
        "gaia_lpv_amplitude": 1.0,
        "gaia_lpv_frequency": 1 / 300.0,
        "gaia_lpv_is_cstar": 1,
        "gaia_dr3__phot_bp_mean_mag": 15.0,
    }
    assert v.classify(mira_c)["subtype"] == "C_STAR_CANDIDATE"
    # Lebzelter+2023 reliability window: faint in BP or outside 7-11 nm -> no C flag.
    assert v.classify(dict(mira_c, gaia_dr3__phot_bp_mean_mag=19.5))["subtype"] is None
    assert v.classify(dict(mira_c, gaia_lpv_median_delta_wl_rp=12.0))["subtype"] is None
    # A period is required, and P < 1000 d (Zhang & Sanders 2023).
    assert v.classify({"gaia_lpv_amplitude": 1.0, "best_class_name": "LPV"})["label"] == "LPV"
    assert (
        v.classify({"gaia_lpv_amplitude": 1.0, "gaia_lpv_frequency": 1 / 1500.0, "best_class_name": "LPV"})["label"]
        == "LPV"
    )


def test_pulsar_candidate_posterior():
    c = _compact()
    base = {"nvss__S1.4": 3.0, "tgss_adr1__Stotal": 150.0, "tgss_adr1__Speak": 130.0}
    plane_pol = c.classify(
        dict(base, **{"nvss__polFlux": 0.6, "nvss__e_polFlux": 0.15, "ra": 266.4, "dec": -28.9})
    )  # Galactic centre
    off = c.classify(dict(base, **{"ra": 192.86, "dec": 27.13}))  # NGP
    assert plane_pol["confidence"] > 0.2 and off["confidence"] < 0.01
    assert plane_pol["label"] == off["label"] == "PULSAR_CANDIDATE"


def test_rule_precision_calibration(tmp_path):
    import json
    import pandas as pd

    spec = importlib.util.spec_from_file_location("v2_cal_t", ROOT / "calibration" / "per_axis.py")
    cal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cal)
    m = {
        "axes": {},
        "rules": {
            "variability": {"ZTF_PERIODIC_VARIABLE|MIRA": {"method": "rule_precision", "n": 67, "precision": 0.9552}}
        },
    }
    path = tmp_path / "m.json"
    path.write_text(json.dumps(m))
    df = pd.DataFrame(
        {
            "variability_class": ["MIRA", "MIRA", "LPV"],
            "variability_confidence": [None, None, None],
            "variability_status": [
                "ZTF_PERIODIC_VARIABLE",
                "GAIA_DR3_SOS_LPV_LARGE_AMPLITUDE",
                "ZTF_PERIODIC_VARIABLE",
            ],
        }
    )
    out = cal.annotate(df, path, axes=("variability",))
    assert out.variability_calibrated_probability.tolist()[0] == 0.9552
    assert out.variability_calibration_method.tolist()[0] == "rule_precision"
    assert out.variability_calibration_method.isna().tolist()[1:] == [True, True]


def test_literature_review_phenomenon_and_gaia_score():
    """2.18.0: HASH grades, SN epoch, Acker identity, Gaia classifier score."""
    s = importlib.util.spec_from_file_location("phen_t", ROOT / "axes" / "phenomenon.py")
    ph = importlib.util.module_from_spec(s)
    s.loader.exec_module(ph)
    hash_row = lambda st: {"catalogs": "HASH PN Catalog", "pn_catalog_status": st}
    assert ph.classify(hash_row("T"))["status"] == "HASH_PN_CATALOG_MATCH"
    assert ph.classify(hash_row("L"))["label"] == "PN"
    assert ph.classify(hash_row("P"))["status"] == "HASH_POSSIBLE_PN"
    assert ph.classify(hash_row("c"))["status"] == "HASH_UNGRADED_ENTRY"  # new candidate
    for mimic in ("HII", "Sy*", "N", "X", "G", "Y*O"):
        assert ph.classify(hash_row(mimic))["label"] == "OTHER_PHENOMENON", mimic
    assert ph.classify(hash_row(None))["label"] == "PN"
    sn = {"catalogs": "ASAS-SN Supernova Catalog", "event_mjd": 58000.0}
    assert ph.classify(dict(sn, obs_mjd=58100.0))["label"] == "SN"
    assert ph.classify(dict(sn, obs_mjd=59500.0))["status"] == "SN_HOST_PAST_EVENT"
    assert ph.classify({"catalogs": "Acker PN Spectroscopy"})["label"] == "PN"
    spec = importlib.util.spec_from_file_location("v2_var_s", ROOT / "axes" / "variability.py")
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    assert (
        v.classify({"best_class_name": "RR", "best_class_score": 0.3})["label"] == "RR_LYRAE"
    )  # no score floor (2.20.0)
    assert v.classify({"best_class_name": "RR", "best_class_score": 0.8})["label"] == "RR_LYRAE"


def test_reannotation_replaces_axis_columns():
    """Re-running the axes on a classified row (blind validation's
    catalog-assisted step) must not duplicate axis columns (2.20.0)."""
    import pandas as pd

    spec = importlib.util.spec_from_file_location("v2_axes_re", ROOT / "control_axes.py")
    ax = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ax)
    row = ax.annotate(pd.DataFrame([{"primary_class": "STAR", "otype": "RR*"}])).iloc[0].to_dict()
    row["otype"] = "Ce*"
    again = ax.annotate(pd.DataFrame([row]))
    assert not again.columns.duplicated().any()
    assert again.variability_class.iloc[0] == "CEPHEID"
